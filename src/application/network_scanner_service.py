import subprocess
import socket
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import logging
from typing import List, Dict, Any

from src.application.network_presence_service import presence_service

logger = logging.getLogger(__name__)

class AdvancedNetworkScanner:
    def __init__(self):
        self.device_cache = {}
        self.scan_status = {
            'is_scanning': False,
            'progress': 0,
            'last_scan_time': None,
            'devices': []
        }
        self.common_ports = {
            22: 'SSH',
            80: 'HTTP',
            443: 'HTTPS',
            3389: 'RDP',
            8080: 'HTTP-Alt',
            445: 'SMB',
            135: 'RPC',
            139: 'NetBIOS',
            53: 'DNS'
        }
        # Very simple MAC to vendor mapping for demonstration
        self.oui_table = {
            '00:50:56': 'VMware',
            '00:0C:29': 'VMware',
            '08:00:27': 'Oracle VirtualBox',
            '00:1A:11': 'Google',
            'B8:27:EB': 'Raspberry Pi Foundation',
            'DC:A6:32': 'Raspberry Pi Foundation',
            '00:14:22': 'Dell',
            '00:24:E8': 'Dell',
            '00:11:11': 'Intel',
            '00:1C:42': 'Parallels',
            'FF:FF:FF': 'Broadcast'
        }

    def _get_hostname(self, ip: str) -> str:
        if ip in self.device_cache and self.device_cache[ip].get('hostname') != 'Unknown':
            return self.device_cache[ip]['hostname']
        try:
            socket.setdefaulttimeout(0.5)
            host, _, _ = socket.gethostbyaddr(ip)
            return host
        except Exception:
            return "Unknown"

    def _get_vendor(self, mac: str) -> str:
        if not mac or mac == 'Unknown':
            return 'Unknown'
        prefix = mac.upper()[:8].replace('-', ':')
        return self.oui_table.get(prefix, 'Unknown Vendor')

    def _ping_host(self, ip: str) -> Dict[str, Any]:
        """Measure latency and guess OS from TTL using a single ping."""
        try:
            # -n 1 (Windows) / -c 1 (Linux), -w 500 (Windows 500ms) / -W 1 (Linux 1s)
            import platform
            is_windows = platform.system().lower() == 'windows'
            cmd = ['ping', '-n', '1', '-w', '500', ip] if is_windows else ['ping', '-c', '1', '-W', '1', ip]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stdout
            
            latency = -1
            ttl = -1
            status = 'Offline'
            
            # Extract time and TTL
            time_match = re.search(r'time[=<]([0-9]+)ms', output, re.IGNORECASE)
            ttl_match = re.search(r'TTL=([0-9]+)', output, re.IGNORECASE)
            
            if time_match and ttl_match:
                latency = int(time_match.group(1))
                ttl = int(ttl_match.group(1))
                status = 'Online'
                
            os_guess = 'Unknown'
            if ttl > 0:
                if ttl <= 64:
                    os_guess = 'Linux/Unix/macOS'
                elif ttl <= 128:
                    os_guess = 'Windows'
                elif ttl <= 255:
                    os_guess = 'Network Equipment (Cisco/Router)'
                    
            return {'status': status, 'latency': latency, 'ttl': ttl, 'os_guess': os_guess}
            
        except Exception:
            return {'status': 'Offline', 'latency': -1, 'ttl': -1, 'os_guess': 'Unknown'}

    def _scan_ports(self, ip: str) -> List[Dict[str, str]]:
        open_ports = []
        for port, service in self.common_ports.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)
            result = sock.connect_ex((ip, port))
            if result == 0:
                open_ports.append({'port': port, 'service': service})
            sock.close()
        return open_ports

    def _analyze_host(self, entry: Dict[str, str], active_ips: Dict[str, Any]) -> Dict[str, Any]:
        ip = entry['ip']
        mac = entry['mac']
        
        # 1. Ping for latency & OS detection
        ping_res = self._ping_host(ip)
        
        # 2. Hostname resolution
        hostname = self._get_hostname(ip)
        
        # 3. Port Scan (only if online)
        open_ports = []
        if ping_res['status'] == 'Online':
            open_ports = self._scan_ports(ip)
            
        # Refine OS guess based on ports if it was Windows/Linux
        os_guess = ping_res['os_guess']
        if ping_res['status'] == 'Online':
            ports_set = {p['port'] for p in open_ports}
            if 3389 in ports_set or 445 in ports_set or 135 in ports_set:
                os_guess = 'Windows'
            elif 22 in ports_set and 3389 not in ports_set:
                os_guess = 'Linux/Unix'
                
        # 4. Vendor lookup
        vendor = self._get_vendor(mac)
        
        # 5. Attendrix Session Correlation
        session = active_ips.get(ip)
        
        device_info = {
            'ip_address': ip,
            'mac_address': mac,
            'hostname': hostname,
            'connection_status': ping_res['status'],
            'latency_ms': ping_res['latency'],
            'os': session.get('os') if session else os_guess,
            'manufacturer': vendor,
            'open_ports': open_ports,
            'device_type': session.get('device_type') if session else 'Unknown',
            'classification': 'Registered Device' if session else 'Unknown Endpoint',
            'associated_user': (session.get('name') or session.get('email') or 'None') if session else 'None',
            'role': session.get('role', 'none') if session else 'none',
            'last_seen': session.get('last_seen', datetime.utcnow().isoformat() + 'Z') if session else datetime.utcnow().isoformat() + 'Z'
        }
        
        # Cache basic info to speed up future scans
        self.device_cache[ip] = {
            'hostname': hostname,
            'mac': mac,
            'vendor': vendor
        }
        
        return device_info

    def run_deep_scan(self, institution_id: str):
        """Asynchronous scan entrypoint."""
        if self.scan_status['is_scanning']:
            return
            
        self.scan_status['is_scanning'] = True
        self.scan_status['progress'] = 0
        
        def _scan():
            try:
                # 1. ARP Discovery
                self.scan_status['progress'] = 10
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=5)
                lines = result.stdout.splitlines()
                
                arp_entries = []
                pattern = re.compile(r'^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9A-Fa-f\-:]+)\s+(\w+)')
                for line in lines:
                    match = pattern.match(line)
                    if match:
                        ip_address = match.group(1)
                        mac_address = match.group(2).replace('-', ':').upper()
                        if not ip_address.startswith(('224.', '239.', '255.')) and not ip_address.endswith('.255'):
                            if mac_address != 'FF:FF:FF:FF:FF:FF':
                                arp_entries.append({'ip': ip_address, 'mac': mac_address})

                self.scan_status['progress'] = 30

                # 2. Get Attendrix Sessions
                try:
                    active_sessions = presence_service.get_presence_list(institution_id)
                    active_ips = {s.get('ip_address'): s for s in active_sessions if s.get('ip_address')}
                except Exception as e:
                    logger.error(f"Failed to fetch active sessions: {e}")
                    active_ips = {}
                    
                self.scan_status['progress'] = 40
                
                # 3. Analyze each host concurrently
                analyzed_devices = []
                total_hosts = len(arp_entries)
                
                if total_hosts > 0:
                    completed = 0
                    with ThreadPoolExecutor(max_workers=15) as executor:
                        futures = {executor.submit(self._analyze_host, entry, active_ips): entry for entry in arp_entries}
                        import concurrent.futures
                        for future in concurrent.futures.as_completed(futures):
                            try:
                                dev_info = future.result()
                                analyzed_devices.append(dev_info)
                            except Exception as exc:
                                logger.error(f"Host analysis failed: {exc}")
                            completed += 1
                            self.scan_status['progress'] = 40 + int((completed / total_hosts) * 55)
                            
                self.scan_status['devices'] = analyzed_devices
                self.scan_status['progress'] = 100
                self.scan_status['last_scan_time'] = datetime.utcnow().isoformat() + 'Z'
                
            except Exception as e:
                logger.error(f"Deep scan failed: {e}")
            finally:
                self.scan_status['is_scanning'] = False

        # Start thread
        thread = threading.Thread(target=_scan)
        thread.daemon = True
        thread.start()

    def get_status(self) -> Dict[str, Any]:
        return self.scan_status

network_scanner_service = AdvancedNetworkScanner()
