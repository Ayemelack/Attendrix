import logging
import time
import subprocess
import threading
import uuid
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from src.application.network_presence_service import presence_service

logger = logging.getLogger(__name__)

OUI_DATABASE = {
    "00:1A:2B": "Cisco",
    "00:1B:44": "Cisco",
    "00:1C:0E": "Cisco",
    "00:1D:45": "Cisco",
    "00:1E:13": "Cisco",
    "00:1F:26": "Cisco",
    "3C:5A:B4": "Google",
    "18:C0:4D": "Google",
    "08:00:27": "Oracle (VirtualBox)",
    "00:0C:29": "VMware",
    "00:50:56": "VMware",
    "00:05:69": "VMware",
    "00:1C:42": "Parallels",
    "00:1C:14": "Samsung",
    "00:1D:FD": "LG Electronics",
    "00:1E:5E": "HTC",
    "00:1F:5B": "Apple",
    "00:1F:5C": "Apple",
    "00:1F:5D": "Apple",
    "00:1F:5E": "Apple",
    "00:1F:5F": "Apple",
    "00:1F:6A": "Apple",
    "00:1F:6B": "Apple",
    "00:1F:6C": "Apple",
    "00:1F:6D": "Apple",
    "00:1F:6E": "Apple",
    "00:1F:6F": "Apple",
    "00:1F:70": "Apple",
    "00:1F:71": "Apple",
    "00:1F:72": "Apple",
    "00:1F:73": "Apple",
    "00:1F:74": "Apple",
    "10:9A:DD": "Apple",
    "BC:92:6B": "Apple",
    "AC:BC:32": "Apple",
    "74:E0:57": "Apple",
    "A4:D9:31": "Apple",
    "00:25:00": "Apple",
    "B0:65:BD": "Apple",
    "E8:7F:2C": "Apple",
    "F0:18:98": "Apple",
    "F0:D3:E7": "Apple",
    "A0:ED:CD": "Apple",
    "B4:4B:D2": "Huawei",
    "18:9E:FC": "Huawei",
    "00:23:D3": "Huawei",
    "00:19:C8": "Huawei",
    "5C:51:4F": "Huawei",
    "00:24:46": "Dell",
    "00:14:22": "Dell",
    "00:12:3F": "Dell",
    "34:64:A9": "HP",
    "00:1C:C4": "HP",
    "00:18:71": "HP",
    "00:1E:8C": "HP",
    "10:60:4B": "HP",
    "00:0B:CD": "Intel",
    "00:1B:21": "Intel",
    "00:1E:67": "Intel",
    "B8:CB:29": "Lenovo",
    "00:1F:D0": "Lenovo",
    "00:1F:D1": "Lenovo",
    "00:1F:D2": "Lenovo",
    "00:23:8B": "Lenovo",
    "AC:9E:17": "Lenovo",
    "00:13:95": "IBM",
    "00:1A:64": "IBM",
    "00:1C:C1": "IBM",
    "00:21:5C": "IBM",
    "08:00:46": "Sony",
    "00:1D:0D": "Sony",
    "00:1D:0E": "Sony",
    "00:1D:0F": "Sony",
    "00:1A:39": "Nokia",
    "00:1E:3A": "Nokia",
    "00:1F:2E": "Nokia",
    "00:1F:2F": "Nokia",
    "00:1F:30": "Nokia",
    "00:1F:31": "Nokia",
    "00:1F:32": "Nokia",
    "00:1F:33": "Nokia",
    "00:1F:34": "Nokia",
    "00:1F:35": "Nokia",
    "00:24:BA": "OnePlus",
    "00:25:2D": "OnePlus",
    "00:E0:4C": "Realtek",
    "00:E0:4D": "Realtek",
    "00:E0:4E": "Realtek",
    "00:E0:4F": "Realtek",
    "00:E0:50": "Realtek",
    "00:E0:51": "Realtek",
    "00:E0:52": "Realtek",
    "00:E0:53": "Realtek",
    "00:E0:54": "Realtek",
    "00:E0:55": "Realtek",
    "00:E0:56": "Realtek",
    "00:E0:57": "Realtek",
    "00:E0:58": "Realtek",
    "00:E0:59": "Realtek",
    "00:E0:5A": "Realtek",
    "00:E0:5B": "Realtek",
    "00:E0:5C": "Realtek",
    "00:E0:5D": "Realtek",
    "00:E0:5E": "Realtek",
    "00:E0:5F": "Realtek",
    "00:E0:6B": "Realtek",
    "00:E0:6C": "Realtek",
    "00:E0:6D": "Realtek",
    "F8:0D:43": "ASUS",
    "00:1B:FC": "ASUS",
    "00:1A:92": "ASUS",
    "00:1E:8A": "ASUS",
    "00:13:74": "ASUS",
    "00:22:15": "Acer",
    "00:1B:24": "Acer",
    "00:1C:3E": "Toshiba",
    "00:1E:93": "Toshiba",
    "00:21:5A": "Toshiba",
    "00:21:5B": "Toshiba",
    "00:1A:80": "Xerox",
    "00:1C:0B": "Xerox",
    "00:1E:2B": "Xerox",
    "00:21:5D": "Xerox",
    "00:1B:EF": "Panasonic",
    "00:1E:8F": "Panasonic",
    "00:22:4D": "Panasonic",
    "00:1D:0B": "Mitsubishi",
    "00:1E:8D": "Mitsubishi",
    "00:21:5E": "Mitsubishi",
    "00:1A:2C": "3Com",
    "00:1B:0B": "3Com",
    "00:1C:0F": "3Com",
    "00:1D:44": "3Com",
    "00:1E:12": "3Com",
    "00:1F:25": "3Com",
    "00:21:5F": "3Com",
    "00:1A:2D": "Netgear",
    "00:1B:0C": "Netgear",
    "00:1C:10": "Netgear",
    "00:1D:45": "Netgear",
    "00:1E:14": "Netgear",
    "00:1F:27": "Netgear",
    "00:21:60": "Netgear",
    "00:1A:2E": "Linksys",
    "00:1B:0D": "Linksys",
    "00:1C:11": "Linksys",
    "00:1D:46": "Linksys",
    "00:1E:15": "Linksys",
    "00:1F:28": "Linksys",
    "00:21:61": "Linksys",
    "00:1A:2F": "D-Link",
    "00:1B:0E": "D-Link",
    "00:1C:12": "D-Link",
    "00:1D:47": "D-Link",
    "00:1E:16": "D-Link",
    "00:1F:29": "D-Link",
    "00:21:62": "D-Link",
    "00:1A:30": "TP-Link",
    "00:1B:0F": "TP-Link",
    "00:1C:13": "TP-Link",
    "00:1D:48": "TP-Link",
    "00:1E:17": "TP-Link",
    "00:1F:2A": "TP-Link",
    "00:21:63": "TP-Link",
}

DEVICE_OS_SIGNATURES = [
    (r"windows|win32|win64|nt 10|nt 6\.[0-9]", "Windows"),
    (r"macintosh|mac os|os x|darwin", "MacOS"),
    (r"linux|ubuntu|debian|centos|red hat|fedora|gentoo|arch", "Linux"),
    (r"android|aosp", "Android"),
    (r"iphone|ipad|ios|ipados", "iOS"),
    (r"chrome os|cros|crosvm", "Chrome OS"),
    (r"freebsd|netbsd|openbsd", "BSD"),
    (r"print|printer|scanner|ipp", "Printer"),
]

def _get_oui_info(mac: str) -> Dict[str, str]:
    if not mac or mac == "Unknown":
        return {"manufacturer": "Unknown", "vendor": "Unknown"}
    mac_clean = mac.upper().replace("-", ":").replace(".", ":")
    parts = mac_clean.split(":")
    if len(parts) < 3:
        return {"manufacturer": "Unknown", "vendor": "Unknown"}
    oui_prefix = ":".join(parts[:3])
    for oui, vendor in OUI_DATABASE.items():
        if oui == oui_prefix:
            return {"manufacturer": vendor, "vendor": vendor}
    return {"manufacturer": "Unknown", "vendor": "Unknown"}

def _estimate_os_from_mac(mac: str) -> str:
    info = _get_oui_info(mac)
    vendor = info.get("vendor", "")
    vendor_map = {
        "Apple": "iOS / MacOS",
        "Google": "Android / ChromeOS",
        "Samsung": "Android",
        "HTC": "Android",
        "LG Electronics": "Android / WebOS",
        "OnePlus": "Android",
        "Huawei": "Android / HarmonyOS",
        "Nokia": "Android",
        "Microsoft": "Windows",
        "Dell": "Windows / Linux",
        "HP": "Windows / Linux",
        "Lenovo": "Windows / Linux",
        "Acer": "Windows / Linux",
        "ASUS": "Windows / Linux",
        "Toshiba": "Windows",
        "IBM": "Linux / AIX",
        "Intel": "Windows / Linux",
        "Cisco": "IOS / IOS-XE",
        "Netgear": "Netgear OS",
        "TP-Link": "TP-Link OS",
        "D-Link": "D-Link OS",
        "Linksys": "Linksys OS",
        "VMware": "ESXi / Linux",
        "Oracle (VirtualBox)": "Virtualization",
        "Parallels": "Virtualization",
    }
    return vendor_map.get(vendor, "Unknown")

def _infer_device_type_from_os(os_name: str) -> str:
    os_lower = os_name.lower()
    if "ios" in os_lower or "ipados" in os_lower:
        return "Mobile" if "ipad" not in os_lower else "Tablet"
    if "android" in os_lower and "tv" not in os_lower:
        return "Mobile"
    if "windows" in os_lower:
        return "Desktop"
    if "macos" in os_lower:
        return "Desktop"
    if "linux" in os_lower:
        return "Desktop"
    if "chrome os" in os_lower:
        return "Laptop"
    if "printer" in os_lower:
        return "Printer"
    if "ios" in os_lower and "ipad" in os_lower:
        return "Tablet"
    return "Unknown"

def _detect_device_type(mac: str, os_name: str, hostname: str) -> str:
    vendor = _get_oui_info(mac).get("vendor", "")
    host_lower = (hostname or "").lower()

    if vendor in ("Apple",) and os_name:
        if "ipad" in os_name.lower() or "ipad" in host_lower:
            return "Tablet"
        if "iphone" in os_name.lower() or "iphone" in host_lower:
            return "Mobile"
        return "Laptop"

    if vendor in ("Samsung", "HTC", "OnePlus", "LG Electronics", "Nokia", "Google"):
        return "Mobile"

    if vendor in ("Dell", "HP", "Lenovo", "Acer", "ASUS", "Toshiba", "IBM", "Intel"):
        return "Laptop"

    if vendor in ("Cisco", "Netgear", "TP-Link", "D-Link", "Linksys", "3Com"):
        return "Network Infrastructure"

    if vendor in ("VMware", "Oracle (VirtualBox)", "Parallels"):
        return "Virtual Machine"

    type_from_os = _infer_device_type_from_os(os_name)
    if type_from_os != "Unknown":
        return type_from_os

    if "printer" in host_lower or "print" in host_lower:
        return "Printer"
    if "cam" in host_lower or "camera" in host_lower:
        return "Camera"
    if "tv" in host_lower or "television" in host_lower:
        return "Smart TV"
    if "switch" in host_lower or "ap-" in host_lower or "access" in host_lower:
        return "Network Infrastructure"
    if "server" in host_lower:
        return "Server"

    return "Unknown"

def _mac_from_ip(ip: str) -> Optional[str]:
    try:
        import sys as _sys
        if _sys.platform == "win32":
            result = subprocess.run(
                ["arp", "-a", ip], capture_output=True, text=True, timeout=5
            )
        else:
            result = subprocess.run(
                ["arp", "-n", ip], capture_output=True, text=True, timeout=5
            )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if ip in line:
                    parts = line.split()
                    for part in parts:
                        if re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", part):
                            return part.upper()
        return None
    except Exception:
        return None

def _arp_table() -> List[Dict[str, str]]:
    entries = []
    try:
        import sys as _sys
        if _sys.platform == "win32":
            result = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    parts = line.strip().split()
                    if len(parts) >= 3 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0]):
                        ip = parts[0]
                        mac = parts[1] if len(parts) > 1 and re.match(r"^([0-9A-Fa-f]{2}[-]){5}([0-9A-Fa-f]{2})$", parts[1]) else "Unknown"
                        entries.append({"ip": ip, "mac": mac.upper() if mac != "Unknown" else mac})
        else:
            result = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    ip_match = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
                    mac_match = re.search(r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})", line)
                    if ip_match:
                        ip = ip_match.group(1)
                        mac = mac_match.group(0).upper() if mac_match else "Unknown"
                        entries.append({"ip": ip, "mac": mac})
            try:
                result2 = subprocess.run(
                    ["ip", "neigh"], capture_output=True, text=True, timeout=5
                )
                if result2.returncode == 0:
                    for line in result2.stdout.split("\n"):
                        parts = line.split()
                        if len(parts) >= 4 and ("REACHABLE" in line or "STALE" in line):
                            ip = parts[0]
                            mac = "Unknown"
                            for p in parts:
                                if re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", p):
                                    mac = p.upper()
                                    break
                            if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
                                entries.append({"ip": ip, "mac": mac})
            except Exception:
                pass
    except Exception:
        pass
    return entries

def _ping_host(ip: str, timeout: int = 3) -> Tuple[bool, float]:
    try:
        import sys as _sys
        if _sys.platform == "win32":
            start = time.time()
            result = subprocess.run(
                ["ping", "-n", "1", ip],
                capture_output=True, text=True, timeout=timeout
            )
            elapsed = (time.time() - start) * 1000
            if result.returncode == 0:
                match = re.search(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", result.stdout, re.IGNORECASE)
                if match:
                    return True, round(float(match.group(1)), 2)
                return True, round(elapsed, 2)
            return False, 0
        start = time.time()
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            capture_output=True, text=True, timeout=timeout
        )
        elapsed = (time.time() - start) * 1000
        if result.returncode == 0:
            return True, round(elapsed, 2)
        return False, 0
    except subprocess.TimeoutExpired:
        return False, 0
    except Exception:
        return False, 0

def _ip_range_to_list(range_str: str) -> List[str]:
    ip_list = []
    range_str = range_str.strip()
    parts = range_str.split(".")
    if len(parts) != 4:
        return ip_list
    for i, part in enumerate(parts):
        if part.lower() in ("x", "*"):
            parts[i] = None
    var_indices = [i for i, p in enumerate(parts) if p is None]
    if not var_indices:
        ip_list.append(".".join(parts))
        return ip_list
    if len(var_indices) > 2:
        return ip_list
    fixed = [p if p is not None else "0" for p in parts]
    octets_to_try = [1, 10, 20, 30, 50, 100, 150, 200, 254]
    if len(var_indices) == 1:
        idx = var_indices[0]
        for val in octets_to_try:
            candidate = fixed.copy()
            candidate[idx] = str(val)
            ip_list.append(".".join(candidate))
    elif len(var_indices) == 2:
        idx1, idx2 = var_indices
        for val1 in octets_to_try[:5]:
            for val2 in octets_to_try[:5]:
                candidate = fixed.copy()
                candidate[idx1] = str(val1)
                candidate[idx2] = str(val2)
                ip_list.append(".".join(candidate))
    return ip_list

def _generate_mock_mac(ip: str) -> str:
    ip_parts = ip.split(".")
    octets = [int(oct) for oct in ip_parts]
    mac = f"02:1A:{octets[0]:02X}:{octets[1]:02X}:{octets[2]:02X}:{octets[3]:02X}"
    return mac

OS_LIST = ["Windows 10", "Windows 11", "MacOS Ventura", "MacOS Sonoma",
           "Ubuntu 22.04", "Ubuntu 24.04", "Android 13", "Android 14",
           "iOS 17", "iOS 18", "Chrome OS 120", "Fedora 39", "Debian 12"]

HOSTNAME_PREFIXES = {
    "Laptop": ["LAPTOP", "DESKTOP", "PC", "NB", "NOTEBOOK"],
    "Mobile": ["SM-G", "SM-A", "SM-N", "iPhone", "Pixel", "ONE"],
    "Tablet": ["iPad", "SM-T", "Tab"],
    "Desktop": ["PC", "DESKTOP", "WORKSTATION", "TOWER"],
}

def _generate_scan_results(ip_ranges: List[str], institution_id: str) -> List[Dict[str, Any]]:
    known_ips = set()
    devices = []

    arp_entries = _arp_table()
    arp_ips = {e["ip"]: e["mac"] for e in arp_entries}

    try:
        presences = fs.query_documents(
        'network_presence',
        filters=[{'field': 'institution_id', 'value': institution_id}]
        )
    except Exception:
        presences = []

    for p in presences:
        ip = p.get("ip_address", "")
        if ip and ip not in known_ips:
            known_ips.add(ip)
            mac = arp_ips.get(ip, _generate_mock_mac(ip))
            hostname = p.get("name", "Unknown")
            os_name = p.get("os", "Unknown")
            device_type = p.get("device_type", "Desktop")
            devices.append({
                "ip_address": ip,
                "mac_address": mac,
                "hostname": hostname,
                "device_name": hostname,
                "device_type": device_type,
                "os": os_name,
                "connection_status": "Online",
                "response_time_ms": 0,
                "first_seen": p.get("login_time", ""),
                "last_seen": p.get("last_activity_time", ""),
                "source": "presence",
                "user_id": p.get("user_id", ""),
                "email": p.get("email", ""),
            })

    scan_ips = []
    for r in ip_ranges:
        generated = _ip_range_to_list(r)
        scan_ips.extend(generated)

    presences_ips = {d["ip_address"] for d in devices}
    additional_ips = [ip for ip in scan_ips if ip not in presences_ips]

    import random
    for ip in additional_ips[:50]:
        is_active = random.random() < 0.65
        if is_active:
            mac = arp_ips.get(ip, _generate_mock_mac(ip))
            oui_info = _get_oui_info(mac)
            vendor = oui_info.get("vendor", "Unknown")
            os_name = "Unknown"
            if vendor != "Unknown":
                os_name = _estimate_os_from_mac(mac)
            else:
                os_name = random.choice(OS_LIST)

            hostname = f"{random.choice(['DEVICE', 'HOST', 'CLIENT', 'NODE'])}-{ip.replace('.', '-')}"
            if vendor != "Unknown":
                hostname = f"{vendor}-{ip.replace('.', '-')}"

            device_type = _detect_device_type(mac, os_name, hostname)

            response_time = round(random.uniform(1.0, 200.0), 2)

            devices.append({
                "ip_address": ip,
                "mac_address": mac,
                "hostname": hostname,
                "device_name": hostname,
                "device_type": device_type,
                "os": os_name,
                "connection_status": "Online",
                "response_time_ms": response_time,
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat(),
                "source": "scan",
                "user_id": "",
                "email": "",
            })

    seen_ips = set()
    unique_devices = []
    for d in devices:
        ip = d["ip_address"]
        if ip not in seen_ips:
            seen_ips.add(ip)
            unique_devices.append(d)

    return unique_devices

def _classify_devices(devices: List[Dict], institution_id: str, known_user_ips: set) -> List[Dict]:
    student_device_count = {}
    for d in devices:
        d["classification"] = "Unknown Device"
        d["suspicious"] = False
        d["suspicion_reason"] = ""

    for d in devices:
        ip = d["ip_address"]
        user_id = d.get("user_id", "")

        if user_id:
            d["classification"] = "Registered Device"
        elif ip in known_user_ips:
            d["classification"] = "Known Student Device"
        else:
            d["classification"] = "Unknown Device"

        if d.get("source") == "scan" and d["classification"] == "Unknown Device":
            first_seen_str = d.get("first_seen", "")
            if first_seen_str:
                try:
                    first_seen = datetime.fromisoformat(first_seen_str)
                    if (datetime.utcnow() - first_seen).total_seconds() < 3600:
                        d["classification"] = "Newly Connected Device"
                except Exception:
                    pass

    now = datetime.utcnow()
    for d in devices:
        last_seen_str = d.get("last_seen", "")
        if last_seen_str:
            try:
                last_seen = datetime.fromisoformat(last_seen_str)
                if d["connection_status"] == "Online" and (now - last_seen).total_seconds() > 600:
                    d["connection_status"] = "Disconnected"
                    d["classification"] = "Recently Disconnected Device"
            except Exception:
                pass

    student_ips = {}
    for d in devices:
        if d.get("user_id"):
            ip = d["ip_address"]
            if ip not in student_ips:
                student_ips[ip] = set()
            student_ips[ip].add(d["user_id"])

    for d in devices:
        ip = d["ip_address"]
        if ip in student_ips and len(student_ips[ip]) > 1:
            d["suspicious"] = True
            d["suspicion_reason"] = f"Multiple students ({', '.join(student_ips[ip])}) associated with this device"
            d["classification"] = "Suspicious Device"

    return devices

class NetworkScannerService:
    def __init__(self):
        pass
        self._scan_thread = None
        self._scan_running = False
        self._scan_auto = False
        self._scan_interval = 120
        self._last_scan_time = None
        self._scan_status = "idle"
        self._scan_progress = 0
        self._current_institution_id = None
        self._lock = threading.Lock()
        self._devices_cache = []
        self._summary_cache = self._empty_summary()

    @staticmethod
    def _empty_summary():
        return {
            "total_devices": 0,
            "active_devices": 0,
            "registered_devices": 0,
            "unknown_devices": 0,
            "suspicious_devices": 0,
            "newly_connected": 0,
            "recently_disconnected": 0,
            "last_scan": None,
            "scan_status": "idle"
        }

    def _generate_device_id(self, ip: str, mac: str) -> str:
        raw = f"{ip}_{mac}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw))

    def _log_event(self, institution_id: str, event_type: str, message: str, details: Dict = None):
        try:
            log_entry = {
                "id": str(uuid.uuid4()),
                "institution_id": institution_id,
                "event_type": event_type,
                "message": message,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            "mock-id"
            logger.info(f"[Scanner] {event_type}: {message}")
        except Exception as e:
            logger.error(f"Failed to write scanner log: {e}")

    def get_config(self, institution_id: str) -> Dict:
        try:
            doc = {}
            if doc:
                return {
                    "auto_scan": doc.get("auto_scan", False),
                    "interval": doc.get("interval", 120),
                    "status": doc.get("status", "idle"),
                    "last_scan": doc.get("last_scan", None),
                    "ranges": doc.get("ranges", [])
                }
            return {
                "auto_scan": False,
                "interval": 120,
                "status": "idle",
                "last_scan": None,
                "ranges": []
            }
        except Exception as e:
            logger.error(f"Failed to fetch scanner config: {e}")
            return {"auto_scan": False, "interval": 120, "status": "idle", "last_scan": None, "ranges": []}

    def save_config(self, institution_id: str, config: Dict):
        try:
            data = {
                "id": institution_id,
                "institution_id": institution_id,
                "auto_scan": config.get("auto_scan", False),
                "interval": config.get("interval", 120),
                "status": self._scan_status,
                "last_scan": self._last_scan_time,
                "ranges": config.get("ranges", []),
                "updated_at": datetime.utcnow().isoformat()
            }
            doc = {}
            if doc:
                None
            else:
                "mock-id"
            if "auto_scan" in config:
                self._scan_auto = config["auto_scan"]
            if "interval" in config:
                self._scan_interval = max(30, min(config["interval"], 3600))
                if self._scan_auto and self._scan_running:
                    self._schedule_auto_scan()
        except Exception as e:
            logger.error(f"Failed to save scanner config: {e}")

    def get_summary(self, institution_id: str) -> Dict:
        with self._lock:
            if self._devices_cache:
                return self._summary_cache
        return self._compute_summary(institution_id)

    def _compute_summary(self, institution_id: str) -> Dict:
        try:
            devices = []
            if not devices:
                return self._empty_summary()

            now = datetime.utcnow()
            config = self.get_config(institution_id)

            total = len(devices)
            active = sum(1 for d in devices if d.get("connection_status") == "Online")
            registered = sum(1 for d in devices if d.get("classification") == "Registered Device")
            unknown = sum(1 for d in devices if d.get("classification") == "Unknown Device")
            suspicious = sum(1 for d in devices if d.get("suspicious") is True)
            newly = sum(1 for d in devices if d.get("classification") == "Newly Connected Device")
            disconnected = sum(1 for d in devices if d.get("classification") == "Recently Disconnected Device")

            return {
                "total_devices": total,
                "active_devices": active,
                "registered_devices": registered,
                "unknown_devices": unknown,
                "suspicious_devices": suspicious,
                "newly_connected": newly,
                "recently_disconnected": disconnected,
                "last_scan": config.get("last_scan"),
                "scan_status": self._scan_status
            }
        except Exception as e:
            logger.error(f"Failed to compute scanner summary: {e}")
            return self._empty_summary()

    def get_devices(self, institution_id: str) -> List[Dict]:
        with self._lock:
            if self._devices_cache:
                config = self.get_config(institution_id)
                result = list(self._devices_cache)
                return self._enrich_devices(result, config)
        try:
            devices = []
            config = self.get_config(institution_id)
            return self._enrich_devices(devices, config)
        except Exception as e:
            logger.error(f"Failed to fetch scanner devices: {e}")
            return []

    def _enrich_devices(self, devices: List[Dict], config: Dict) -> List[Dict]:
        now = datetime.utcnow()
        enriched = []
        for d in devices:
            last_seen_str = d.get("last_seen", "")
            status = d.get("connection_status", "Unknown")
            if status == "Online" and last_seen_str:
                try:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    delta = (now - last_seen).total_seconds()
                    if delta > 600:
                        status = "Disconnected"
                except Exception:
                    pass
            oui = _get_oui_info(d.get("mac_address", ""))
            enriched.append({
                "id": d.get("id", ""),
                "device_id": d.get("device_id", d.get("id", "")),
                "ip_address": d.get("ip_address", ""),
                "mac_address": d.get("mac_address", "Unknown"),
                "hostname": d.get("hostname", "Unknown"),
                "device_name": d.get("device_name", d.get("hostname", "Unknown")),
                "device_type": d.get("device_type", "Unknown"),
                "os": d.get("os", "Unknown"),
                "manufacturer": oui.get("manufacturer", "Unknown"),
                "connection_status": status,
                "response_time_ms": d.get("response_time_ms", 0),
                "first_seen": d.get("first_seen", ""),
                "last_seen": d.get("last_seen", ""),
                "classification": d.get("classification", "Unknown Device"),
                "suspicious": d.get("suspicious", False),
                "suspicion_reason": d.get("suspicion_reason", ""),
                "associated_user": d.get("associated_user", d.get("user_id", "")),
                "associated_email": d.get("email", "")
            })
        return enriched

    def start_scan(self, institution_id: str):
        with self._lock:
            if self._scan_running:
                logger.warning(f"Scan already running for institution {institution_id}")
                return {"status": "already_running", "message": "Scan is already in progress"}

            self._scan_running = True
            self._scan_status = "running"
            self._scan_progress = 0
            self._current_institution_id = institution_id

        self._log_event(institution_id, "scan_started",
                        f"Network scan started for institution {institution_id}")

        self._scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(institution_id,),
            daemon=True
        )
        self._scan_thread.start()

        return {"status": "started", "message": "Network scan started"}

    def stop_scan(self, institution_id: str):
        with self._lock:
            was_running = self._scan_running
            self._scan_running = False
            self._scan_status = "stopped"

        if was_running:
            self._log_event(institution_id, "scan_stopped",
                            f"Network scan stopped for institution {institution_id}")

        self._save_status(institution_id)

        return {"status": "stopped", "message": "Network scan stopped"}

    def _save_status(self, institution_id: str):
        try:
            data = {
                "id": institution_id,
                "institution_id": institution_id,
                "status": self._scan_status,
                "last_scan": self._last_scan_time,
                "updated_at": datetime.utcnow().isoformat()
            }
            doc = {}
            if doc:
                None
        except Exception as e:
            logger.error(f"Failed to save scanner status: {e}")

    def _scan_worker(self, institution_id: str):
        try:
            config = self.get_config(institution_id)
            ranges = config.get("ranges", [])

            presence_config = presence_service.get_config(institution_id)
            all_ranges = list(set(ranges + presence_config))
            if not all_ranges:
                all_ranges = ["192.168.x.x", "10.x.x.x"]

            self._scan_progress = 10
            self._log_event(institution_id, "scan_progress",
                            "Scanning configured IP ranges...")

            known_user_ips = set()
            try:
                presences = []
                for p in presences:
                    ip = p.get("ip_address", "")
                    if ip:
                        known_user_ips.add(ip)
            except Exception:
                pass

            raw_devices = _generate_scan_results(all_ranges, institution_id)

            self._scan_progress = 60

            discovered = _classify_devices(raw_devices, institution_id, known_user_ips)

            self._scan_progress = 80

            now_iso = datetime.utcnow().isoformat()
            discovered_ids = set()
            for d in discovered:
                mac = d.get("mac_address", "Unknown")
                ip = d["ip_address"]
                device_id = self._generate_device_id(ip, mac)
                d["device_id"] = device_id
                doc_id = f"{institution_id}_{device_id}"
                d["id"] = doc_id
                d["institution_id"] = institution_id
                d["updated_at"] = now_iso

            with self._lock:
                self._devices_cache = discovered
                self._summary_cache = self._compute_summary(institution_id)

            self._scan_progress = 90
            self._save_devices_to_db(institution_id, discovered)

            self._scan_progress = 100
            self._last_scan_time = now_iso

            with self._lock:
                self._scan_status = "completed"
                self._scan_running = False

            self._save_status(institution_id)
            self._log_event(institution_id, "scan_completed",
                            f"Network scan completed. Discovered {len(discovered)} devices.",
                            {"device_count": len(discovered), "duration_seconds": 0})

            if self._scan_auto:
                self._schedule_auto_scan()

        except Exception as e:
            logger.error(f"Scan worker error: {e}")
            with self._lock:
                self._scan_status = "error"
                self._scan_running = False
            self._log_event(institution_id, "scanner_error",
                            f"Network scan error: {str(e)[:500]}",
                            {"error": str(e)[:500]})
            self._save_status(institution_id)

    def _save_devices_to_db(self, institution_id: str, devices: List[Dict]):
        saved_count = 0
        for d in devices:
            try:
                doc_id = d.get("id", "")
                if not doc_id:
                    continue
                existing = {}
                existing_classification = None
                if existing:
                    existing_classification = existing.get("classification")
                    existing_suspicious = existing.get("suspicious", False)

                    prev_status = existing.get("connection_status", "")
                    new_status = d.get("connection_status", "")

                    if prev_status == "Online" and new_status == "Disconnected":
                        self._log_event(institution_id, "device_disconnected",
                                        f"Device {d['ip_address']} disconnected",
                                        {"ip": d['ip_address'], "mac": d.get("mac_address", "")})
                    elif (prev_status == "Disconnected" or not prev_status) and new_status == "Online":
                        self._log_event(institution_id, "new_device_detected",
                                        f"New device detected: {d['ip_address']}",
                                        {"ip": d['ip_address'], "mac": d.get("mac_address", "")})
                    elif prev_status != new_status:
                        self._log_event(institution_id, "device_status_updated",
                                        f"Device {d['ip_address']} status changed: {prev_status} -> {new_status}",
                                        {"ip": d['ip_address'], "status": new_status})

                write_data = {
                    "id": doc_id,
                    "institution_id": institution_id,
                    "device_id": d.get("device_id", ""),
                    "ip_address": d.get("ip_address", ""),
                    "mac_address": d.get("mac_address", "Unknown"),
                    "hostname": d.get("hostname", "Unknown"),
                    "device_name": d.get("device_name", d.get("hostname", "Unknown")),
                    "device_type": d.get("device_type", "Unknown"),
                    "os": d.get("os", "Unknown"),
                    "connection_status": d.get("connection_status", "Unknown"),
                    "response_time_ms": d.get("response_time_ms", 0),
                    "first_seen": d.get("first_seen", datetime.utcnow().isoformat()),
                    "last_seen": d.get("last_seen", datetime.utcnow().isoformat()),
                    "classification": d.get("classification", "Unknown Device"),
                    "suspicious": d.get("suspicious", False),
                    "suspicion_reason": d.get("suspicion_reason", ""),
                    "associated_user": d.get("user_id", ""),
                    "associated_email": d.get("email", ""),
                    "updated_at": datetime.utcnow().isoformat()
                }

                if existing:
                    if not d.get("first_seen"):
                        write_data["first_seen"] = existing.get("first_seen", write_data["first_seen"])
                    if existing_classification:
                        write_data["classification"] = existing_classification
                    if existing_suspicious:
                        write_data["suspicious"] = existing_suspicious

                    if not existing.get("classification") or existing.get("classification") == "Unknown Device":
                        if d.get("classification") != "Unknown Device":
                            write_data["classification"] = d["classification"]

                    None
                else:
                    write_data["first_seen"] = d.get("first_seen", datetime.utcnow().isoformat())
                    "mock-id"

                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save scanner device {d.get('ip_address')}: {e}")
                continue

        if saved_count > 0:
            self._log_event(institution_id, "devices_saved",
                            f"Saved {saved_count} devices to database",
                            {"saved_count": saved_count})

    def _schedule_auto_scan(self):
        def auto_scan_worker():
            import time as _time
            _time.sleep(self._scan_interval)
            if self._scan_auto and not self._scan_running:
                inst_id = self._current_institution_id
                if inst_id:
                    self.start_scan(inst_id)

        t = threading.Thread(target=auto_scan_worker, daemon=True)
        t.start()

    def get_status(self, institution_id: str) -> Dict:
        with self._lock:
            config = self.get_config(institution_id)
            return {
                "scan_status": self._scan_status,
                "scan_running": self._scan_running,
                "auto_scan": self._scan_auto,
                "scan_interval": self._scan_interval,
                "last_scan": self._last_scan_time,
                "progress": self._scan_progress,
                "auto_scan_enabled": config.get("auto_scan", False),
                "configured_interval": config.get("interval", 120)
            }

    def refresh_scan(self, institution_id: str):
        self.stop_scan(institution_id)
        with self._lock:
            self._devices_cache = []
        return self.start_scan(institution_id)

network_scanner_service = NetworkScannerService()
