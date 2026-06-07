"""
ATTENDRIX SECURITY INFRASTRUCTURE PACKAGE

Comprehensive security modules for multi-tenant distributed attendance system:
- Geolocation Security: GPS validation, geofencing, location proof
- Network Security: VPN/proxy/TOR detection, campus network validation
- Device Fingerprinting: Device identification, emulator detection, device binding
- Session Security: Token rotation, device binding, inactivity timeout
- Attendance Anti-Proxy: Dynamic sessions, expiring tokens, lecturer validation
- Offline Sync Security: Encrypted storage, tamper-proof synchronization
- New Account Isolation: Zero-data isolation for new accounts
- Admin Security: MFA, IP restrictions, action confirmation, audit logging
- Production Hardening: Debug removal, header hardening, error sanitization
"""

# Re-export all symbols from legacy security module
# (captcha, rate limiting, sanitization, audit logging, CSRF, etc.)
from ..security_legacy import *  # noqa: F401, F403

from .geolocation_security import (
    GeolocationValidator,
    LocationProofOfWork,
    GeoFence,
    Location,
)

from .network_security import (
    NetworkSecurityValidator,
    CampusNetworkValidator,
    IPReputation,
)

from .device_fingerprint import (
    DeviceFingerprintAnalyzer,
    DeviceFingerprint,
)

from .session_security import (
    SessionManager,
    SessionToken,
)

from .attendance_anti_proxy import (
    AttendanceSessionManager,
    AttendanceSession,
)

from .offline_sync_security import (
    OfflineSyncSecurityManager,
    OfflineRecord,
)

from .account_isolation import (
    NewAccountIsolationManager,
    NewAccountPolicy,
)

from .admin_security import (
    AdminSecurityManager,
    AdminSession,
    MFAMethod,
)

from .production_hardening import (
    ProductionHardeningManager,
    apply_production_hardening,
)

__all__ = [
    'GeolocationValidator',
    'LocationProofOfWork',
    'GeoFence',
    'Location',
    'NetworkSecurityValidator',
    'CampusNetworkValidator',
    'IPReputation',
    'DeviceFingerprintAnalyzer',
    'DeviceFingerprint',
    'SessionManager',
    'SessionToken',
    'AttendanceSessionManager',
    'AttendanceSession',
    'OfflineSyncSecurityManager',
    'OfflineRecord',
    'NewAccountIsolationManager',
    'NewAccountPolicy',
    'AdminSecurityManager',
    'AdminSession',
    'MFAMethod',
    'ProductionHardeningManager',
    'apply_production_hardening',
]
