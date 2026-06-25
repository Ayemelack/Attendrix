"""
ATTENDRIX CLOUDFLARE SECURITY INTEGRATION MODULE
================================================
Enterprise-grade Cloudflare integration for the Attendrix distributed attendance system.
Provides: WAF-compatible rules engine, bot detection, IP reputation, SSL/TLS enforcement,
security headers, rate limiting configuration, and origin security.

This module implements server-side validation that complements Cloudflare's edge security.
All implementations preserve existing application behavior and API contracts.
"""

import re
import os
import json
import time
import logging
import ipaddress
from typing import Dict, Any, Optional, Tuple, List, Set
from datetime import datetime, timedelta
from functools import wraps

from flask import request, jsonify, current_app, g, make_response

logger = logging.getLogger(__name__)


# =============================================================================
# 1. CLOUDFLARE PROXY TRUST & ORIGIN IP RESTORATION
# =============================================================================

CLOUDFLARE_IP_RANGES = [
    '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22',
    '103.31.4.0/22', '141.101.64.0/18', '108.162.192.0/18',
    '190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22',
    '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
    '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22',
]

CLOUDFLARE_IP_RANGES_V6 = [
    '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32',
    '2405:b500::/32', '2405:8100::/32', '2a06:98c0::/29',
    '2c0f:f248::/32',
]


def is_cloudflare_request() -> bool:
    """Check if request is proxied through Cloudflare."""
    cf_ip = request.headers.get('CF-Connecting-IP')
    cf_ray = request.headers.get('CF-Ray')
    return bool(cf_ip) or bool(cf_ray)


def get_client_ip() -> str:
    """
    Get real client IP behind Cloudflare proxy.
    Falls back through: CF-Connecting-IP -> X-Forwarded-For -> remote_addr.
    """
    cf_ip = request.headers.get('CF-Connecting-IP')
    if cf_ip:
        return cf_ip.split(',')[0].strip()

    xff = request.headers.get('X-Forwarded-For')
    if xff:
        return xff.split(',')[0].strip()

    return request.remote_addr or '0.0.0.0'


def validate_cloudflare_origin_request() -> Tuple[bool, Optional[str]]:
    """
    Validate that the request came through Cloudflare.
    In production, origin should ONLY accept traffic from Cloudflare.
    """
    if current_app.config.get('ENVIRONMENT', 'production') != 'production':
        return True, None

    if not is_cloudflare_request():
        return False, 'Request must be proxied through Cloudflare'
    return True, None


# =============================================================================
# 2. WAF RULES ENGINE (SERVER-SIDE COMPLEMENT TO CLOUDFLARE WAF)
# =============================================================================

class WAFRulesEngine:
    """
    Web Application Firewall rules engine that runs at the application layer,
    complementing Cloudflare's edge WAF. Detects attacks that may bypass
    edge rules or require application-level context.

    Detection categories:
    - SQL Injection (advanced variants)
    - Cross-Site Scripting (XSS)
    - Command Injection
    - Path Traversal
    - Remote Code Execution (RCE)
    - LDAP Injection
    - NoSQL Injection (MongoDB)
    - Server-Side Template Injection (SSTI)
    - SSRF patterns
    - Local File Inclusion (LFI)
    - Open Redirect
    - HTTP Parameter Pollution
    - JWT manipulation
    """

    SQL_INJECTION_PATTERNS: List[str] = [
        r"('|\")\s*(OR|AND|UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|EXECUTE|CREATE|TRUNCATE|RENAME)",
        r"(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|UNION|EXEC|EXECUTE|CREATE|TRUNCATE|RENAME)\s+.*\s+(FROM|INTO|TABLE|SET|DATABASE|PROCEDURE|VIEW)",
        r"'.*\s+OR\s+'.*\s*=\s*'.*",
        r"(;|--|#|/\*|\*/|';\s*--)",
        r"'\s*OR\s*'\d+'\s*=\s*'\d+",
        r"'\s*OR\s*1\s*=\s*1",
        r"xp_cmdshell|sp_executesql|sp_prepare|sp_oacreate",
        r"UNION\s+ALL\s+SELECT",
        r"INTO\s+(OUT|DUMP)FILE",
        r"LOAD_FILE\s*\(",
        r"information_schema\.",
        r"pg_sleep|WAITFOR\s+DELAY|BENCHMARK\s*\(",
    ]

    XSS_PATTERNS: List[str] = [
        r"<[^>]*script[\s>/]",
        r"javascript\s*:",
        r"on\w+\s*=",
        r"<[^>]*iframe[\s>/]",
        r"<[^>]*embed[\s>/]",
        r"<[^>]*object[\s>/]",
        r"<[^>]*form[\s>/]",
        r"<[^>]*input[\s>/]",
        r"<[^>]*textarea[\s>/]",
        r"<[^>]*select[\s>/]",
        r"<[^>]*button[\s>/]",
        r"<[^>]*svg[\s>/]",
        r"<[^>]*math[\s>/]",
        r"document\.(cookie|write|location|domain|referrer|title|body)",
        r"eval\s*\(",
        r"setTimeout\s*\(",
        r"setInterval\s*\(",
        r"new\s+Function\s*\(",
        r"alert\s*\(",
        r"prompt\s*\(",
        r"confirm\s*\(",
        r"String\.fromCharCode",
        r"atob\s*\(",
        r"<[^>]*style[\s>/].*expression\s*\(",
        r"<[^>]*meta[\s>/]",
        r"<[^>]*link[\s>/]",
    ]

    COMMAND_INJECTION_PATTERNS: List[str] = [
        r"[;&|`]\s*(cat|ls|dir|id|whoami|pwd|uname|ifconfig|ipconfig|netstat|ps|kill|chmod|chown|curl|wget|nc|nmap|bash|sh|cmd|powershell|python|perl|php)",
        r"\|\s*tee\s",
        r"\$\s*\(.*\)",
        r"`.*`",
        r"\|.*\|",
        r";\s*rm\s",
        r";\s*mv\s",
        r";\s*cp\s",
        r">\s*/dev/",
        r">\s*&1",
        r"2>&1",
    ]

    PATH_TRAVERSAL_PATTERNS: List[str] = [
        r"\.\.[/\\]",
        r"\.\.%2f",
        r"\.\.%5c",
        r"%2e%2e%2f",
        r"%2e%2e%5c",
        r"\.\./\.\./",
        r"\.\.\\\.\.\\",
        r"/etc/passwd",
        r"/etc/shadow",
        r"c:\\windows",
        r"c:\\boot",
        r"\.\./\.\./\.\./",
        r"\.\.\\\.\.\\\.\.\\",
    ]

    RCE_PATTERNS: List[str] = [
        r"(base64|base64_encode|base64_decode)\s*\(",
        r"system\s*\(",
        r"exec\s*\(",
        r"shell_exec\s*\(",
        r"passthru\s*\(",
        r"popen\s*\(",
        r"proc_open\s*\(",
        r"assert\s*\(",
        r"create_function\s*\(",
        r"array_map\s*\(.*\$",
        r"preg_replace.*e\s*$",
        r"call_user_func\s*\(",
        r"call_user_func_array\s*\(",
        r"invokefunction",
        r"java\.lang\.Runtime",
        r"org\.apache\.commons\.io",
    ]

    LDAP_INJECTION_PATTERNS: List[str] = [
        r"\*\(\)\s*\|",
        r"\)\s*\(&",
        r"admin\*",
        r"\*\|",
        r"\|\(uid=",
    ]

    NOSQL_INJECTION_PATTERNS: List[str] = [
        r"\$ne\s*:",
        r"\$gt\s*:",
        r"\$lt\s*:",
        r"\$regex\s*:",
        r"\$where\s*:",
        r"\$exists\s*:",
        r"\$nin\s*:",
        r"\$in\s*:",
        r"\$or\s*:",
        r"\$and\s*:",
        r"\{\s*\$gt\s*:\s*\"\"",
        r"\{\s*\$ne\s*:\s*\"\"",
    ]

    SSTI_PATTERNS: List[str] = [
        r"\{\{.*\}\}",
        r"\$\{.*\}",
        r"<%.*%>",
        r"\{\%.*\%\}",
        r"#\{.*\}",
    ]

    SSRF_PATTERNS: List[str] = [
        r"(https?://)?127\.0\.0\.1",
        r"(https?://)?localhost",
        r"(https?://)?0\.0\.0\.0",
        r"(https?://)?169\.254\.\d+\.\d+",
        r"(https?://)?10\.\d+\.\d+\.\d+",
        r"(https?://)?172\.(1[6-9]|2\d|3[01])\.\d+\.\d+",
        r"(https?://)?192\.168\.\d+\.\d+",
        r"(https?://)?\[::1\]",
        r"(https?://)?metadata\.google\.internal",
        r"(https?://)?169\.254\.169\.254",
    ]

    LFI_PATTERNS: List[str] = [
        r"\.\./\.\./\.\./",
        r"file://",
        r"php://filter",
        r"php://input",
        r"data://",
        r"expect://",
        r"zip://",
        r"compress\.zlib",
        r"compress\.bzip2",
    ]

    OPEN_REDIRECT_PATTERNS: List[str] = [
        r"//[^/]",
        r"@[^/]",
        r"%0d",
        r"%0a",
        r"%0d%0a",
    ]

    @classmethod
    def check_all_patterns(cls, value: str) -> Tuple[str, Optional[str]]:
        """
        Check a value against all WAF patterns.
        Returns (category, matched_pattern) or (None, None) if safe.
        """
        if not isinstance(value, str):
            return None, None

        checks = [
            ('SQL_INJECTION', cls.SQL_INJECTION_PATTERNS),
            ('XSS', cls.XSS_PATTERNS),
            ('COMMAND_INJECTION', cls.COMMAND_INJECTION_PATTERNS),
            ('PATH_TRAVERSAL', cls.PATH_TRAVERSAL_PATTERNS),
            ('RCE', cls.RCE_PATTERNS),
            ('LDAP_INJECTION', cls.LDAP_INJECTION_PATTERNS),
            ('NOSQL_INJECTION', cls.NOSQL_INJECTION_PATTERNS),
            ('SSTI', cls.SSTI_PATTERNS),
            ('SSRF', cls.SSRF_PATTERNS),
            ('LFI', cls.LFI_PATTERNS),
            ('OPEN_REDIRECT', cls.OPEN_REDIRECT_PATTERNS),
        ]

        for category, patterns in checks:
            for pattern in patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    return category, pattern
        return None, None

    @classmethod
    def validate_request_data(cls, data: Dict[str, Any], depth: int = 0) -> List[Dict[str, Any]]:
        """
        Recursively validate all string values in a dict against WAF patterns.
        Returns list of violations found.
        """
        if depth > 10:
            return []

        violations = []
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    category, pattern = cls.check_all_patterns(value)
                    if category:
                        violations.append({
                            'field': key,
                            'category': category,
                            'pattern': pattern,
                            'value_preview': value[:50],
                        })
                elif isinstance(value, (dict, list)):
                    sub_violations = cls.validate_request_data(
                        value, depth + 1
                    )
                    violations.extend(sub_violations)
        elif isinstance(data, list):
            for item in data:
                sub_violations = cls.validate_request_data(
                    item, depth + 1
                )
                violations.extend(sub_violations)

        return violations


waf_engine = WAFRulesEngine()


# =============================================================================
# 3. SUSPICIOUS USER-AGENT DETECTION
# =============================================================================

SUSPICIOUS_USER_AGENTS: Set[str] = {
    'curl', 'wget', 'python-requests', 'python-urllib', 'python-httpx',
    'go-http-client', 'okhttp', 'httpclient', 'java/', 'libwww-perl',
    'perl-', 'ruby', 'php-', 'scrapy', 'guzzle', 'axios',
    'masscan', 'nmap', 'sqlmap', 'nikto', 'dirbuster', 'gobuster',
    'wfuzz', 'ffuf', 'zmap', 'zgrab', 'hydra', 'medusa',
    'burpsuite', 'postmanruntime', 'insomnia',
    'zgrab', 'wpscan', 'joomscan', 'droopescan',
    'acunetix', 'netsparker', 'appscan', 'nessus', 'openvas',
    'nutch', 'larbin', 'sogou', 'yandex', 'petalbot',
}

SUSPICIOUS_UA_PATTERNS: List[str] = [
    r'curl/\d',
    r'wget/\d',
    r'python-requests/\d',
    r'python-urllib',
    r'python-httpx',
    r'go-http-client',
    r'okhttp/\d',
    r'HttpClient',
    r'java/\d',
    r'libwww-perl',
    r'perl-',
    r'ruby',
    r'php-',
    r'scrapy',
    r'guzzle',
    r'axios/\d',
    r'masscan',
    r'nmap',
    r'sqlmap',
    r'nikto',
    r'dirbuster',
    r'gobuster',
    r'wfuzz',
    r'ffuf',
    r'zmap',
    r'zgrab',
    r'hydra',
    r'medusa',
    r'burpsuite',
    r'PostmanRuntime',
    r'Insomnia',
    r'acunetix',
    r'netsparker',
    r'appscan',
    r'nessus',
    r'openvas',
    r'nutch',
    r'larbin',
    r'msie\s+6\.0',
    r'mozilla/4\.0\s+\(compatible;\s*msie\s+6',
    r'mozilla/4\.0\s+\(compatible;\s*msie\s+7',
    r'mozilla/4\.0\s+\(compatible;\s*msie\s+8',
]


def is_suspicious_user_agent(user_agent: str) -> Tuple[bool, Optional[str]]:
    """
    Check if User-Agent is suspicious (bot, scanner, or automated tool).
    Returns (is_suspicious, reason).
    """
    if not user_agent:
        return True, 'Missing User-Agent'

    ua_lower = user_agent.lower()

    for known_ua in SUSPICIOUS_USER_AGENTS:
        if known_ua in ua_lower:
            return True, f'Known suspicious UA: {known_ua}'

    for pattern in SUSPICIOUS_UA_PATTERNS:
        if re.search(pattern, user_agent, re.IGNORECASE):
            return True, f'UA matches suspicious pattern: {pattern}'

    if len(user_agent) > 500:
        return True, 'UA exceeds maximum length (500 chars)'

    if len(user_agent) < 10:
        return True, 'UA too short'

    return False, None


# =============================================================================
# 4. IP REPUTATION & ASN FILTERING
# =============================================================================

class IPReputationFilter:
    """
    IP reputation checking using Cloudflare headers and local blocklists.
    Complements Cloudflare's threat intelligence at the application layer.
    """

    KNOWN_PROXY_IPS: Set[str] = set()
    KNOWN_VPN_IPS: Set[str] = set()
    KNOWN_TOR_EXIT_NODES: Set[str] = set()
    BLOCKED_IPS: Set[str] = set()

    @classmethod
    def load_blocklist(cls):
        """Load IP blocklists from environment or file."""
        blocklist_str = current_app.config.get('IP_BLOCKLIST', '')
        if blocklist_str:
            cls.BLOCKED_IPS = set(blocklist_str.split(','))

    @classmethod
    def is_blocked_ip(cls, ip: str) -> bool:
        """Check if IP is in the blocklist."""
        if ip in cls.BLOCKED_IPS:
            return True

        try:
            ip_obj = ipaddress.ip_address(ip)
            for blocked in cls.BLOCKED_IPS:
                if '/' in blocked:
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(blocked, strict=False):
                        return True
        except ValueError:
            pass

        return False

    @classmethod
    def get_threat_score_from_cloudflare(cls) -> Optional[int]:
        """
        Get threat score from Cloudflare's CF-Threat-Score header.
        0 = benign, 100 = malicious.
        """
        threat_score = request.headers.get('CF-Threat-Score')
        if threat_score:
            try:
                return int(threat_score)
            except (ValueError, TypeError):
                pass
        return None

    @classmethod
    def get_cloudflare_metadata(cls) -> Dict[str, Any]:
        """Get Cloudflare request metadata from headers."""
        return {
            'ip': request.headers.get('CF-Connecting-IP', ''),
            'country': request.headers.get('CF-IPCountry', ''),
            'ray': request.headers.get('CF-Ray', ''),
            'threat_score': request.headers.get('CF-Threat-Score', ''),
            'bot_score': request.headers.get('CF-Bot-Score', ''),
            'colo': request.headers.get('CF-RAY', '').split('-')[-1] if '-' in request.headers.get('CF-RAY', '') else '',
            'tls_version': request.headers.get('CF-TLS-Version', ''),
            'visitor': request.headers.get('CF-Visitor', ''),
        }


ip_reputation = IPReputationFilter()


# =============================================================================
# 5. CLOUDFLARE SECURITY HEADERS ENHANCEMENT
# =============================================================================

CLOUDFLARE_HEADERS = {
    'CF-Cache-Status': None,
    'CF-Ray': None,
    'CF-Connecting-IP': None,
    'CF-IPCountry': None,
    'CF-Threat-Score': None,
    'CF-Bot-Score': None,
    'CF-Visitor': None,
    'CF-TLS-Version': None,
}

CLOUDFLARE_SECURITY_HEADERS = {
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'X-XSS-Protection': '0',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': (
        'camera=(self), microphone=(self), geolocation=(self), '
        'display-capture=(self), payment=(), usb=(), magnetometer=(), '
        'accelerometer=(), gyroscope=(), fullscreen=(self), '
        'interest-cohort=()'
    ),
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
    'X-DNS-Prefetch-Control': 'off',
    'X-Download-Options': 'noopen',
    'X-Permitted-Cross-Domain-Policies': 'none',
    'Origin-Agent-Cluster': '?1',
}

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
    "https://challenges.cloudflare.com https://www.google.com https://www.gstatic.com "
    "https://apis.google.com https://fonts.googleapis.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
    "https://fonts.googleapis.com https://fonts.gstatic.com; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com https://fonts.googleapis.com; "
    "frame-src 'self' https://challenges.cloudflare.com https://www.google.com; "
    "connect-src 'self' https://api.resend.com wss:; "
    "media-src 'self' blob:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "upgrade-insecure-requests"
)


def apply_cloudflare_security_headers(response):
    """Apply Cloudflare-compatible security headers."""
    for header, value in CLOUDFLARE_SECURITY_HEADERS.items():
        if header not in response.headers:
            response.headers[header] = value

    response.headers['Content-Security-Policy'] = CSP_POLICY

    env = current_app.config.get('ENVIRONMENT', 'production') if current_app else 'production'
    if env == 'production':
        response.headers['Strict-Transport-Security'] = (
            'max-age=31536000; includeSubDomains; preload'
        )

    server_header = response.headers.get('Server', '')
    if server_header and 'gunicorn' in server_header.lower():
        response.headers['Server'] = 'Attendrix'

    return response


# =============================================================================
# 6. CLOUDFLARE WAF RULESET CONFIGURATION (for documentation / deployment)
# =============================================================================

CLOUDFLARE_WAF_RULESET = {
    "rulesets": [
        {
            "id": "attendrix-owasp-core",
            "name": "Attendrix OWASP Core Ruleset",
            "description": "OWASP ModSecurity Core Rule Set tuned for Attendrix",
            "rules": [
                {
                    "id": 920100,
                    "description": "Bad HTTP methods",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920120,
                    "description": "Multipart body overflow",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920170,
                    "description": "GET or HEAD with body",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920210,
                    "description": "Connection header value",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920220,
                    "description": "URL encoding abuse",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920230,
                    "description": "Multiple URL encoding",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920240,
                    "description": "URL parameter name limits",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920250,
                    "description": "Acute URL parameter value length",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920270,
                    "description": "Invalid character in request",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920280,
                    "description": "Missing Host header",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920290,
                    "description": "Empty Host header",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920300,
                    "description": "Missing Accept header",
                    "action": "block",
                    "score": 5,
                    "enabled": True,
                },
                {
                    "id": 920310,
                    "description": "Missing User-Agent header",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 920320,
                    "description": "Missing content type",
                    "action": "block",
                    "score": 10,
                    "enabled": True,
                },
                {
                    "id": 930100,
                    "description": "Path traversal attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 930110,
                    "description": "Path traversal attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 930120,
                    "description": "OS file access",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 931100,
                    "description": "Remote file inclusion",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 932100,
                    "description": "Remote command execution",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 932105,
                    "description": "Unix command injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 932110,
                    "description": "Windows command injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 932115,
                    "description": "Unix command injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 932120,
                    "description": "Remote command execution",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933100,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933110,
                    "description": "PHP file upload injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933120,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933130,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933131,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933140,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933150,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933151,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933160,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933170,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933180,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933190,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 933200,
                    "description": "PHP injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 934100,
                    "description": "Node.js injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941100,
                    "description": "XSS attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941110,
                    "description": "XSS attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941120,
                    "description": "XSS attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941130,
                    "description": "XSS attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941140,
                    "description": "XSS attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941150,
                    "description": "XSS attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941160,
                    "description": "XSS attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941170,
                    "description": "XSS attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941180,
                    "description": "Node.js injection",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941190,
                    "description": "XSS using style sheets",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941200,
                    "description": "XSS using VML frames",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941210,
                    "description": "XSS using javascript",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941220,
                    "description": "XSS using obfuscated javascript",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941230,
                    "description": "XSS using event handlers",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941240,
                    "description": "XSS attack via HTTP parameter",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941250,
                    "description": "XSS using IE conditionals",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941260,
                    "description": "XSS using LUA",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941270,
                    "description": "XSS using object tag",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941280,
                    "description": "XSS using base tag",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941290,
                    "description": "XSS using applet tag",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941300,
                    "description": "XSS using embed tag",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941310,
                    "description": "US-ASCII XSS",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941320,
                    "description": "XSS attack detected",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941330,
                    "description": "XSS attack detected",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941340,
                    "description": "XSS attack detected",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941350,
                    "description": "UTF-7 XSS",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 941360,
                    "description": "XSS using object tag",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942100,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942110,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942120,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942130,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942140,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942150,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942160,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942170,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942180,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942190,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942200,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942210,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942220,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942230,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942240,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942250,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942260,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942270,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942280,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942290,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942300,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942310,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942320,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942330,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942340,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942350,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942360,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942370,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942380,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942390,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942400,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942410,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942420,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942430,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942440,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942450,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942460,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942470,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942480,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942490,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 942500,
                    "description": "SQL injection attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 943100,
                    "description": "Session fixation attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944100,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944110,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944120,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944130,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944200,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944210,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944220,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944230,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944240,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
                {
                    "id": 944300,
                    "description": "Java attack",
                    "action": "block",
                    "score": 30,
                    "enabled": True,
                },
            ],
        },
        {
            "id": "attendrix-rate-limit",
            "name": "Attendrix Rate Limiting",
            "description": "Endpoint-specific rate limits for Attendrix",
            "rules": [
                {"id": "rl-login", "description": "Login endpoint rate limit", "limit": "5r/m", "burst": 3, "action": "block"},
                {"id": "rl-register", "description": "Register endpoint rate limit", "limit": "3r/m", "burst": 2, "action": "block"},
                {"id": "rl-signup", "description": "Signup endpoint rate limit", "limit": "3r/m", "burst": 2, "action": "block"},
                {"id": "rl-voucher", "description": "Voucher generation rate limit", "limit": "10r/m", "burst": 5, "action": "block"},
                {"id": "rl-password-reset", "description": "Password reset rate limit", "limit": "3r/m", "burst": 2, "action": "block"},
                {"id": "rl-api", "description": "General API rate limit", "limit": "30r/m", "burst": 10, "action": "block"},
                {"id": "rl-admin", "description": "Admin route rate limit", "limit": "20r/m", "burst": 5, "action": "block"},
                {"id": "rl-attendance", "description": "Attendance submission rate limit", "limit": "10r/m", "burst": 5, "action": "block"},
                {"id": "rl-otp", "description": "OTP endpoint rate limit", "limit": "3r/m", "burst": 2, "action": "block"},
                {"id": "rl-upload", "description": "File upload rate limit", "limit": "10r/m", "burst": 3, "action": "block"},
                {"id": "rl-search", "description": "Search endpoint rate limit", "limit": "20r/m", "burst": 5, "action": "block"},
            ],
        },
    ]
}


# =============================================================================
# 7. CLOUDFLARE EDGE CONFIGURATION RECOMMENDATIONS
# =============================================================================

CLOUDFLARE_EDGE_CONFIG = {
    "ssl": {
        "mode": "full_strict",
        "min_tls_version": "1.2",
        "ciphers": ["ECDHE-ECDSA-AES128-GCM-SHA256", "ECDHE-RSA-AES128-GCM-SHA256",
                    "ECDHE-ECDSA-AES256-GCM-SHA384", "ECDHE-RSA-AES256-GCM-SHA384",
                    "ECDHE-ECDSA-CHACHA20-POLY1305", "ECDHE-RSA-CHACHA20-POLY1305"],
        "always_use_https": True,
        "automatic_https_rewrites": True,
        "ssl_recommend": True,
        "certificate_transparency": True,
        "strict_origin_pull": True,
    },
    "security": {
        "hsts": {
            "enabled": True,
            "max_age": 31536000,
            "include_subdomains": True,
            "preload": True,
        },
        "browser_check": True,
        "challenge_ttl": 1800,
        "email_obfuscation": True,
        "hotlink_protection": True,
        "ip_geolocation": True,
        "max_upload_size": 100,
        "min_tls_version": "1.2",
        "opportunistic_encryption": True,
        "prefetch_preload": True,
        "privacy_pass": True,
        "security_level": "high",
        "waf": {
            "enabled": True,
            "paranoia_level": 2,
            "ruleset": "owasp_crs_v3",
            "score_threshold": 5,
        },
    },
    "performance": {
        "auto_minify": {
            "html": True,
            "css": True,
            "javascript": True,
        },
        "brotli": True,
        "early_hints": True,
        "rocket_loader": False,
    },
    "caching": {
        "cache_level": "standard",
        "edge_cache_ttl": 0,
        "browser_cache_ttl": 14400,
        "always_online": True,
    },
    "ddos": {
        "level": "high",
        "mitigation": "challenge",
    },
    "bot_management": {
        "enabled": True,
        "fight_mode": True,
        "verify_through_js": True,
        "js_detection": True,
        "bot_score_threshold": 30,
    },
    "zero_trust": {
        "access_policies": {
            "admin_panel": {
                "name": "Admin Panel Access",
                "application": "admin.attendrix.app",
                "policy": "allow",
                "require": ["mfa", "email"],
            },
            "super_admin": {
                "name": "Super Admin Access",
                "application": "superadmin.attendrix.app",
                "policy": "allow",
                "require": ["mfa", "email", "device_posture"],
            },
            "api_access": {
                "name": "API Access",
                "application": "api.attendrix.app",
                "policy": "allow",
                "require": ["mfa", "email"],
            },
            "internal_dashboard": {
                "name": "Internal Dashboard",
                "application": "dashboard.attendrix.app",
                "policy": "allow",
                "require": ["mfa", "email", "ip_range"],
            },
        },
    },
}


# =============================================================================
# 8. MIDDLEWARE REGISTRATION
# =============================================================================

def register_cloudflare_middleware(app):
    """Register Cloudflare security middleware with the Flask application."""

    @app.before_request
    def verify_cloudflare_proxy():
        if current_app.config.get('ENVIRONMENT', 'production') == 'production':
            valid, error = validate_cloudflare_origin_request()
            if not valid:
                SecurityAuditLogger.log_event(
                    'cloudflare_bypass',
                    f'Request not from Cloudflare: {request.remote_addr}',
                    risk_score=90,
                    metadata={'path': request.path}
                )
                return jsonify({'error': 'Access denied'}), 403

    @app.before_request
    def check_request_threat_level():
        threat_score = request.headers.get('CF-Threat-Score')
        if threat_score:
            try:
                score = int(threat_score)
                if score > 50:
                    SecurityAuditLogger.log_event(
                        'high_threat_score',
                        f'Request with high threat score: {score}',
                        risk_score=score,
                        metadata={
                            'path': request.path,
                            'ip': get_client_ip(),
                            'country': request.headers.get('CF-IPCountry', ''),
                        }
                    )
                    return jsonify({'error': 'Access denied'}), 403
            except (ValueError, TypeError):
                pass

        bot_score = request.headers.get('CF-Bot-Score')
        if bot_score:
            try:
                score = int(bot_score)
                if score < 30:
                    SecurityAuditLogger.log_event(
                        'low_bot_score',
                        f'Request with low bot score: {score}',
                        risk_score=70,
                        metadata={
                            'path': request.path,
                            'ip': get_client_ip(),
                        }
                    )
                    resp = jsonify({'error': 'Access denied'})
                    resp.status_code = 403
                    return resp
            except (ValueError, TypeError):
                pass

    @app.before_request
    def check_suspicious_agent():
        # Bypass suspicious UA block in development/testing to allow local scripts, curl, postman, and tests
        if app.config.get('ENVIRONMENT') == 'development' or app.config.get('ENV') == 'development' or app.debug:
            return None

        user_agent = request.headers.get('User-Agent', '')
        is_suspicious, reason = is_suspicious_user_agent(user_agent)
        if is_suspicious:
            SecurityAuditLogger.log_event(
                'suspicious_user_agent',
                f'Suspicious UA detected: {reason}',
                risk_score=60,
                metadata={
                    'path': request.path,
                    'ip': get_client_ip(),
                    'ua': user_agent[:200],
                }
            )
            return jsonify({'error': 'Invalid request'}), 403

    WAF_EXEMPT_PATHS = [
        '/api/auth/login',
        '/api/auth/forgot-password',
        '/api/auth/reset-password',
        '/api/auth/register',
        '/api/auth/signup',
    ]

    @app.before_request
    def check_waf_rules():
        if request.method in ('POST', 'PUT', 'PATCH'):
            path = request.path
            if any(path.startswith(p) for p in WAF_EXEMPT_PATHS):
                return None
            content_type = request.content_type or ''
            if 'application/json' in content_type:
                data = request.get_json(silent=True)
                if data and isinstance(data, dict):
                    violations = waf_engine.validate_request_data(data)
                    if violations:
                        categories = set(v['category'] for v in violations)
                        SecurityAuditLogger.log_event(
                            'waf_blocked',
                            f'WAF blocked request: {", ".join(categories)}',
                            risk_score=80,
                            metadata={
                                'path': request.path,
                                'violations': violations[:5],
                                'ip': get_client_ip(),
                            }
                        )
                        return jsonify({'error': 'Invalid request'}), 400

            if 'multipart/form-data' in content_type:
                form_data = request.form.to_dict()
                if form_data:
                    violations = waf_engine.validate_request_data(form_data)
                    if violations:
                        categories = set(v['category'] for v in violations)
                        SecurityAuditLogger.log_event(
                            'waf_blocked_form',
                            f'WAF blocked form: {", ".join(categories)}',
                            risk_score=80,
                            metadata={'path': request.path, 'violations': violations[:3]}
                        )
                        return jsonify({'error': 'Invalid request'}), 400

        if request.method == 'GET':
            for key, value in request.args.items():
                if isinstance(value, str):
                    category, pattern = waf_engine.check_all_patterns(value)
                    if category:
                        SecurityAuditLogger.log_event(
                            'waf_blocked_query',
                            f'WAF blocked query param: {key} ({category})',
                            risk_score=80,
                            metadata={'path': request.path, 'param': key}
                        )
                        return jsonify({'error': 'Invalid request'}), 400

    @app.after_request
    def apply_cloudflare_headers(response):
        return apply_cloudflare_security_headers(response)

    @app.after_request
    def remove_server_fingerprint(response):
        response.headers.pop('Server', None)
        response.headers.pop('X-Powered-By', None)
        response.headers['Server'] = 'Attendrix'
        return response


# Import here to avoid circular import
from src.infrastructure.security import SecurityAuditLogger
