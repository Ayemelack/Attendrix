"""
NETWORK SECURITY MODULE
Attendrix distributed attendance system

VPN/proxy/TOR detection, datacenter IP identification, and network anomaly detection.
"""

import logging
from typing import Tuple, Optional, Dict, Any, List
from flask import request, current_app
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IPReputation:
    """IP reputation analysis results."""
    ip_address: str
    is_vpn: bool = False
    is_proxy: bool = False
    is_tor: bool = False
    is_datacenter: bool = False
    is_residential: bool = False
    threat_level: str = 'low'  # low, medium, high
    organization: str = None
    country: str = None


class NetworkSecurityValidator:
    """Validates network connections for suspicious activity."""
    
    # Known VPN provider ASNs/CIDRs (simplified for demonstration)
    VPN_PROVIDERS = {
        'nordvpn', 'expressvpn', 'surfshark', 'mullvadvpn', 'protonvpn',
        'cyberghost', 'ipvanish', 'Private Internet Access', 'windscribe'
    }
    
    # Known datacenter providers
    DATACENTER_PROVIDERS = {
        'AWS', 'Google Cloud', 'Microsoft Azure', 'DigitalOcean', 'Linode',
        'Vultr', 'Hetzner', 'OVH', 'Alibaba', 'Tencent', 'AWS', 'GCP'
    }
    
    # TOR exit nodes (would be fetched from Tor directory in production)
    TOR_EXIT_NODES = set()  # populated from Tor consensus

    def __init__(self):
        """Initialize network security validator."""
        self.cache = {}  # Simple in-memory cache for IP reputation

    def validate_network(
        self,
        ip_address: Optional[str] = None,
        require_residential: bool = False,
        block_vpn: bool = False,
        block_proxy: bool = False,
        block_tor: bool = False,
    ) -> Tuple[bool, Optional[str], IPReputation]:
        """
        Validate network characteristics.
        
        Args:
            ip_address: IP to validate (uses request IP if None)
            require_residential: Only allow residential IPs
            block_vpn: Block VPN connections
            block_proxy: Block proxy connections
            block_tor: Block TOR connections
            
        Returns:
            (is_valid, error_message, reputation)
        """
        ip = ip_address or self._get_client_ip()
        
        # Check cache
        if ip in self.cache:
            reputation = self.cache[ip]
        else:
            reputation = self._analyze_ip_reputation(ip)
            self.cache[ip] = reputation

        # Check policy violations
        if block_vpn and reputation.is_vpn:
            logger.warning(
                f'VPN access blocked: {ip}',
                extra={'ip': ip, 'provider': reputation.organization}
            )
            return False, 'VPN access not permitted. Please disable VPN to continue.', reputation

        if block_proxy and reputation.is_proxy:
            logger.warning(f'Proxy access blocked: {ip}')
            return False, 'Proxy access not permitted.', reputation

        if block_tor and reputation.is_tor:
            logger.warning(f'TOR access blocked: {ip}')
            return False, 'TOR network access is not permitted.', reputation

        if require_residential and reputation.is_datacenter:
            logger.warning(
                f'Datacenter IP rejected (residential required): {ip}',
                extra={'ip': ip, 'provider': reputation.organization}
            )
            return False, 'This operation requires a residential connection.', reputation

        if reputation.threat_level == 'high':
            logger.warning(
                f'High threat IP detected: {ip} (threat_level=high)',
                extra={'ip': ip, 'threat_level': reputation.threat_level}
            )
            return False, 'Your network has been flagged as suspicious. Please contact support.', reputation

        return True, None, reputation

    def _analyze_ip_reputation(self, ip: str) -> IPReputation:
        """
        Analyze IP reputation (production: integrate with MaxMind, Abuseipdb, etc.).
        For now, implement basic detection logic.
        """
        reputation = IPReputation(ip_address=ip)

        # In production, call external IP reputation API
        # For now, implement basic heuristics
        
        # Detect common VPN/proxy patterns
        organization = self._get_ip_organization(ip)
        if organization:
            reputation.organization = organization
            
            org_lower = organization.lower()
            if any(vpn in org_lower for vpn in self.VPN_PROVIDERS):
                reputation.is_vpn = True
                reputation.threat_level = 'medium'
            
            if any(dc in org_lower for dc in self.DATACENTER_PROVIDERS):
                reputation.is_datacenter = True

        # Check if TOR node
        if ip in self.TOR_EXIT_NODES:
            reputation.is_tor = True
            reputation.threat_level = 'high'

        # Detect proxy patterns (would use external detection)
        if self._looks_like_proxy(ip):
            reputation.is_proxy = True
            reputation.threat_level = 'medium'

        # Assume residential if not datacenter/vpn/proxy
        if not (reputation.is_datacenter or reputation.is_vpn or reputation.is_proxy):
            reputation.is_residential = True

        return reputation

    def _get_client_ip(self) -> str:
        """Get client IP from request, handling proxies."""
        if request:
            # Check for Cloudflare header (if behind Cloudflare)
            if 'CF-Connecting-IP' in request.headers:
                return request.headers['CF-Connecting-IP']
            
            # Check for X-Forwarded-For (standard reverse proxy)
            if 'X-Forwarded-For' in request.headers:
                return request.headers['X-Forwarded-For'].split(',')[0].strip()
            
            # Direct connection IP
            return request.remote_addr or '127.0.0.1'
        
        return '127.0.0.1'

    def _get_ip_organization(self, ip: str) -> Optional[str]:
        """Get ISP/organization for IP (would call MaxMind/IP2Location in production)."""
        # This would integrate with GeoIP database
        # For now, return None (would be implemented with proper library)
        return None

    def _looks_like_proxy(self, ip: str) -> bool:
        """Heuristic check for proxy IPs (would use external API)."""
        # This would call proxy detection API
        return False

    def get_network_metadata(self, ip_address: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed network metadata for logging."""
        ip = ip_address or self._get_client_ip()
        reputation = self._analyze_ip_reputation(ip)
        
        return {
            'ip': ip,
            'is_vpn': reputation.is_vpn,
            'is_proxy': reputation.is_proxy,
            'is_tor': reputation.is_tor,
            'is_datacenter': reputation.is_datacenter,
            'threat_level': reputation.threat_level,
            'organization': reputation.organization,
        }


class CampusNetworkValidator:
    """Validates connection to campus network (WiFi/LAN)."""
    
    def __init__(self):
        """Initialize campus network validator."""
        pass

    def validate_campus_network(
        self,
        mac_address: Optional[str] = None,
        ssid: Optional[str] = None,
        signal_strength: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate connection to authorized campus network.
        
        Args:
            mac_address: WiFi MAC address
            ssid: Network SSID
            signal_strength: Signal strength (-dBm)
            
        Returns:
            (is_valid, error_message, metadata)
        """
        metadata = {
            'mac_address': mac_address,
            'ssid': ssid,
            'signal_strength': signal_strength,
        }

        # In production:
        # - Validate MAC against known campus access points
        # - Verify SSID matches expected network
        # - Check signal strength (if too strong, might be spoofed)
        # - Validate network certificate pinning

        # For now, return valid if SSID matches known networks
        known_ssids = current_app.config.get('CAMPUS_NETWORK_SSIDS', [])
        
        if ssid and known_ssids:
            if ssid in known_ssids:
                return True, None, metadata
            else:
                return False, f'Not connected to authorized campus network ({ssid})', metadata

        # If no SSID validation configured, allow
        return True, None, metadata
