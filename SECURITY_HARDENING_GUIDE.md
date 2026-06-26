MAXIMUM SECURITY HARDENING - ATTENDRIX DISTRIBUTED ATTENDANCE SYSTEM
===================================================================

## Overview

This document describes the comprehensive security hardening implemented in Attendrix for:
- Multi-tenant data isolation
- Role-based access control
- Geolocation security
- Device fingerprinting and binding
- Session security with token rotation
- VPN/proxy/TOR detection
- Attendance anti-proxy protection
- New account isolation
- Admin security with MFA
- Production hardening
- Offline sync security

---

## Architecture

### Security Layer Hierarchy

```
┌─ Application Layer (Decorators & Endpoints)
│  └─ Security Decorators (@require_geolocation, @require_valid_session, etc.)
│
├─ Integration Layer (SecurityManager)
│  └─ Central coordinator for all security subsystems
│
└─ Infrastructure Layer (Core Security Modules)
   ├─ GeolocationValidator (GPS, geofencing, location proof)
   ├─ NetworkSecurityValidator (VPN/proxy/TOR detection)
   ├─ DeviceFingerprintAnalyzer (Device identification, emulator detection)
   ├─ SessionManager (Token rotation, device binding)
   ├─ AttendanceSessionManager (Anti-proxy attendance)
   ├─ OfflineSyncSecurityManager (Encrypted offline sync)
   ├─ NewAccountIsolationManager (Zero-data isolation)
   ├─ AdminSecurityManager (MFA, IP restrictions)
   └─ ProductionHardeningManager (Headers, error sanitization)
```

---

## Security Module Details

### 1. GEOLOCATION SECURITY (`geolocation_security.py`)

**Purpose:** Validates attendance locations, prevents spoofing, enforces geofencing.

**Key Classes:**
- `Location`: GPS coordinate with accuracy and timestamp
- `GeoFence`: Circular geographic boundary (center + radius)
- `GeolocationValidator`: Validates attendance locations
- `LocationProofOfWork`: Challenge-response for location spoofing prevention

**Usage Example:**

```python
from src.infrastructure.security import GeolocationValidator, GeoFence, Location

validator = GeolocationValidator()

# Create a geofence (e.g., school campus)
campus = GeoFence(
    center_lat=40.1283,
    center_lon=-88.2434,
    radius_meters=500,  # 500m radius
)

# Validate student location
user_location = Location(
    latitude=40.1285,
    longitude=-88.2435,
    accuracy=10,  # meters
)

is_valid, error, metadata = validator.validate_attendance_location(
    user_location,
    campus,
    allow_buffer=True,
)

if is_valid:
    print("Attendance allowed")
else:
    print(f"Attendance blocked: {error}")
```

**Decorator Usage:**

```python
from src.presentation.decorators import require_geolocation

@app.route('/attendance/record', methods=['POST'])
@require_geolocation(lat=40.1283, lon=-88.2434, radius_m=500)
def record_attendance(location_metadata=None):
    # Automatically validates GPS location
    return {'status': 'recorded'}
```

---

### 2. NETWORK SECURITY (`network_security.py`)

**Purpose:** Detects VPN, proxy, TOR, and datacenter IPs. Validates campus network connection.

**Key Classes:**
- `IPReputation`: IP reputation analysis results
- `NetworkSecurityValidator`: Validates network characteristics
- `CampusNetworkValidator`: Validates campus WiFi connection

**Usage Example:**

```python
from src.infrastructure.security import NetworkSecurityValidator

validator = NetworkSecurityValidator()

# Validate network (block VPN/proxy/TOR)
is_valid, error, reputation = validator.validate_network(
    ip_address='203.0.113.45',
    require_residential=False,
    block_vpn=True,
    block_proxy=True,
    block_tor=True,
)

if is_valid:
    print(f"Network trusted (provider: {reputation.organization})")
else:
    print(f"Network blocked: {error}")

# Campus network validation
campus_validator = CampusNetworkValidator()
is_valid, error, metadata = campus_validator.validate_campus_network(
    ssid='CampusWiFi',  # Must match configured SSID
)
```

---

### 3. DEVICE FINGERPRINTING (`device_fingerprint.py`)

**Purpose:** Identifies devices, detects emulators, prevents shared device abuse, enables device binding.

**Key Classes:**
- `DeviceFingerprint`: Device identification data
- `DeviceFingerprintAnalyzer`: Generates and validates fingerprints

**Usage Example:**

```python
from src.infrastructure.security import DeviceFingerprintAnalyzer

analyzer = DeviceFingerprintAnalyzer()

# Generate fingerprint from User-Agent and device data
fingerprint = analyzer.generate_fingerprint(
    user_agent='Mozilla/5.0 (Linux; Android 12; Pixel 6)',
    device_data={
        'model': 'Pixel 6',
        'isRooted': False,
        'screenResolution': '1080x2340',
    }
)

# Validate device
user_id = 'student_123'
is_valid, error, metadata = analyzer.validate_device(
    user_id,
    fingerprint,
    require_non_emulator=True,
    require_non_rooted=True,
)

if is_valid:
    print("Device trusted")
else:
    print(f"Device blocked: {error}")

# Detect device changes
is_same_device, warning, metadata = analyzer.detect_device_change(
    user_id,
    fingerprint,
    similarity_threshold=0.85,
)
```

---

### 4. SESSION SECURITY (`session_security.py`)

**Purpose:** Token rotation, device binding, inactivity timeout, session expiration.

**Key Classes:**
- `SessionToken`: Secure session token
- `SessionManager`: Manages token lifecycle

**Usage Example:**

```python
from src.infrastructure.security import SessionManager

manager = SessionManager(
    token_ttl_seconds=3600,  # 1 hour
    inactivity_timeout_seconds=900,  # 15 minutes
)

# Create session
session = manager.create_session(
    user_id='student_123',
    device_fingerprint_id='fp_abc123',
    institution_id='school_001',
    ip_address='203.0.113.45',
)

# Validate session
is_valid, error, session = manager.validate_session(
    token_id=session.token_id,
    device_fingerprint_id='fp_abc123',  # Must match
    ip_address='203.0.113.45',  # Optional strict binding
)

# Rotate token (issue new, invalidate old)
success, error, new_session = manager.rotate_token(
    old_token_id=session.token_id,
    device_fingerprint_id='fp_abc123',
    ip_address='203.0.113.45',
)

# Check inactivity
is_active, message = manager.check_inactivity(session.token_id)
```

---

### 5. ATTENDANCE ANTI-PROXY PROTECTION (`attendance_anti_proxy.py`)

**Purpose:** Prevents students from recording attendance for others. Uses dynamic sessions, expiring tokens, and location validation.

**Key Classes:**
- `AttendanceSession`: Secure attendance session
- `AttendanceSessionManager`: Manages attendance sessions

**Usage Example:**

```python
from src.infrastructure.security import AttendanceSessionManager

manager = AttendanceSessionManager(session_duration_seconds=600)

# Lecturer creates session
session = manager.create_session(
    lecturer_id='lecturer_001',
    class_id='class_comp101',
    institution_id='school_001',
    location_proof_required=True,
    expected_location_lat=40.1283,
    expected_location_lon=-88.2434,
)

print(f"QR Token: {session.qr_token}")
print(f"Session expires in: {session.time_remaining_seconds}s")

# Student records attendance
success, error, record = manager.record_attendance(
    session_id=session.session_id,
    user_id='student_123',
    device_fingerprint_id='fp_abc123',
    location_data={'latitude': 40.1285, 'longitude': -88.2435},
)

if success:
    print("Attendance recorded")
else:
    print(f"Attendance failed: {error}")

# Lecturer closes session
success, error = manager.close_session(
    session_id=session.session_id,
    lecturer_id='lecturer_001',
)
```

---

### 6. OFFLINE SYNC SECURITY (`offline_sync_security.py`)

**Purpose:** Secure offline sync with tamper detection and encryption.

**Key Classes:**
- `OfflineRecord`: Queued record for sync
- `OfflineSyncSecurityManager`: Manages offline queue

**Usage Example:**

```python
from src.infrastructure.security import OfflineSyncSecurityManager

manager = OfflineSyncSecurityManager()

# Queue record for offline sync
record_id = manager.queue_offline_record(
    user_id='student_123',
    institution_id='school_001',
    record_type='attendance',
    data={
        'timestamp': 1709312400,
        'session_id': 'session_abc123',
    }
)

# Validate record (anti-tampering)
is_valid, error = manager.validate_offline_record(record_id)

if is_valid:
    print("Record integrity verified")
    manager.mark_sync_attempted(record_id)
    # Sync to server...
    manager.mark_sync_successful(record_id)
else:
    print(f"Record tampering detected: {error}")
```

---

### 7. NEW ACCOUNT ISOLATION (`account_isolation.py`)

**Purpose:** Ensures new accounts see zero data for first 24 hours.

**Key Classes:**
- `NewAccountPolicy`: Isolation policy
- `NewAccountIsolationManager`: Enforces isolation

**Usage Example:**

```python
from src.infrastructure.security import NewAccountIsolationManager

manager = NewAccountIsolationManager()

# Register new account
policy = manager.register_new_account(
    user_id='student_new_001',
    institution_id='school_001',
    role='student',
)

# Check if query is allowed
is_allowed, error = manager.enforce_isolation_on_query(
    user_id='student_new_001',
    query_type='statistics',  # Will be blocked for 24 hours
)

if not is_allowed:
    print(f"Query blocked: {error}")

# Get safe dashboard for isolated account
dashboard = manager.get_isolated_dashboard_data(
    user_id='student_new_001',
    role='student',
)
# Returns empty attendance, statistics, colleagues, etc.
```

---

### 8. ADMIN SECURITY (`admin_security.py`)

**Purpose:** Multi-factor authentication, IP whitelisting, sensitive action audit logging.

**Key Classes:**
- `AdminSecurityManager`: Manages admin security
- `MFAMethod`: MFA method configuration
- `AdminSession`: Admin session

**Usage Example:**

```python
from src.infrastructure.security import AdminSecurityManager

manager = AdminSecurityManager()

# Register MFA method for admin
success, error, method = manager.register_mfa_method(
    admin_id='admin_001',
    method_type='totp',  # Time-based one-time password
)

# Whitelist admin IP
manager.add_ip_whitelist('admin_001', '203.0.113.1')

# Verify MFA code
is_valid, error = manager.verify_mfa(
    admin_id='admin_001',
    mfa_code='123456',
)

# Create admin session
session = manager.create_admin_session(
    admin_id='admin_001',
    ip_address='203.0.113.1',
    device_fingerprint_id='fp_admin123',
    mfa_verified=True,
)

# Validate admin IP
is_allowed, error = manager.validate_admin_ip(
    admin_id='admin_001',
    ip_address='203.0.113.1',
)

# Audit sensitive action
is_allowed, error = manager.validate_admin_action(
    admin_id='admin_001',
    action_type='delete_user',
    action_data={'user_id': 'student_123'},
)
```

---

### 9. PRODUCTION HARDENING (`production_hardening.py`)

**Purpose:** Removes debug info, hardens HTTP headers, sanitizes errors.

**Key Classes:**
- `ProductionHardeningManager`: Manages hardening

**Security Headers Applied:**
- `X-Frame-Options`: DENY (prevent clickjacking)
- `X-Content-Type-Options`: nosniff (prevent MIME sniffing)
- `Strict-Transport-Security`: max-age=31536000 (force HTTPS)
- `Content-Security-Policy`: Strict CSP
- `Referrer-Policy`: strict-origin-when-cross-origin
- `Permissions-Policy`: Restrict browser features

**Sensitive Headers Removed:**
- Server
- X-Powered-By
- X-AspNet-Version
- X-Generator

**Usage (Automatic):**

```python
from src.infrastructure.security import apply_production_hardening

app = Flask(__name__)
apply_production_hardening(app)  # Applied automatically
```

---

## Integration with Flask

### Setup in app.py

```python
from flask import Flask
from src.infrastructure.security.integration import init_security

app = Flask(__name__)

# Initialize all security systems
security_manager = init_security(app)

# Configure app
app.config.update(
    ENVIRONMENT='production',
    SESSION_TTL_SECONDS=3600,
    SESSION_INACTIVITY_TIMEOUT=900,
    ATTENDANCE_SESSION_DURATION=600,
    REQUIRE_RESIDENTIAL_NETWORK=False,  # Set to True if needed
    CAMPUS_NETWORK_SSIDS=['CampusWiFi', 'CampusWiFi-5G'],  # Optional
)
```

### Using Security Decorators

```python
from flask import Blueprint
from src.presentation.decorators import (
    require_geolocation,
    require_non_vpn,
    require_trusted_device,
    require_valid_session,
    require_admin_mfa,
    enforce_new_account_isolation,
)

bp = Blueprint('attendance', __name__)

@bp.route('/attendance/record', methods=['POST'])
@require_valid_session(rotate_token=True)
@require_trusted_device()
@require_non_vpn()
@require_geolocation(lat=40.1283, lon=-88.2434, radius_m=500)
def record_attendance():
    """Record attendance with full security checks."""
    return {'status': 'recorded'}

@bp.route('/admin/users/delete/<user_id>', methods=['DELETE'])
@require_valid_session()
@require_admin_mfa()
def delete_user(user_id):
    """Delete user (requires admin MFA)."""
    return {'status': 'deleted'}
```

---

## Security Configuration

### Environment Variables

```bash
# Session security
SESSION_TTL_SECONDS=3600          # Token lifetime (1 hour)
SESSION_INACTIVITY_TIMEOUT=900    # Inactivity timeout (15 minutes)

# Attendance sessions
ATTENDANCE_SESSION_DURATION=600   # Attendance session duration (10 minutes)

# Network security
REQUIRE_RESIDENTIAL_NETWORK=false  # Require residential IP
CAMPUS_NETWORK_SSIDS=CampusWiFi,CampusWiFi-5G

# Production hardening
ENVIRONMENT=production            # Set to production for hardening
```

### Configuration in settings.py

```python
class ProductionConfig:
    # Security configuration
    SESSION_TTL_SECONDS = 3600
    SESSION_INACTIVITY_TIMEOUT = 900
    ATTENDANCE_SESSION_DURATION = 600
    REQUIRE_RESIDENTIAL_NETWORK = False
    
    # MFA requirements
    ADMIN_MFA_REQUIRED = True
    NEW_ACCOUNT_ISOLATION_PERIOD = 86400  # 24 hours
```

---

## Best Practices

### 1. New Accounts
- Always register new accounts with `NewAccountIsolationManager`
- Allow 24 hours before full access to prevent data leakage
- Notify users of gradual feature unlock

### 2. Admin Actions
- Require MFA for all admin accounts
- Whitelist admin IPs
- Audit all sensitive operations
- Require confirmation for destructive actions

### 3. Session Management
- Always rotate tokens on privilege escalation
- Implement inactivity timeout
- Bind sessions to devices
- Log all session changes

### 4. Geolocation
- Validate GPS accuracy (< 100m is safe)
- Use geofencing for attendance (50m buffer warning)
- Require location proof for sensitive operations
- Log location violations

### 5. Device Security
- Check for emulators on sensitive operations
- Detect rooted/jailbroken devices
- Track device fingerprints
- Block shared devices from sensitive actions

### 6. Network Security
- Block VPN connections during attendance
- Require residential IPs for sensitive operations
- Validate campus network SSID
- Track IP changes

### 7. Offline Sync
- Always validate checksum on sync
- Detect tampering immediately
- Log retry attempts
- Enforce strict schema validation

---

## Testing

### Unit Tests

```python
# tests/test_security_geolocation.py
from src.infrastructure.security import GeolocationValidator, GeoFence, Location

def test_geolocation_inside_fence():
    validator = GeolocationValidator()
    fence = GeoFence(40.1283, -88.2434, 500)
    
    location = Location(40.1285, -88.2435)
    is_valid, error, metadata = validator.validate_attendance_location(location, fence)
    
    assert is_valid == True
    assert error is None

def test_device_fingerprint_validation():
    analyzer = DeviceFingerprintAnalyzer()
    
    fp1 = analyzer.generate_fingerprint(
        user_agent='Mozilla/5.0 (Linux; Android 12)',
        device_data={'model': 'Pixel 6'},
    )
    
    is_valid, error, metadata = analyzer.validate_device(
        'user_123',
        fp1,
        require_non_emulator=True,
    )
    
    assert is_valid == True
```

### Integration Tests

```python
def test_full_attendance_workflow(client):
    # Lecturer creates session
    response = client.post('/api/attendance/create_session', json={
        'class_id': 'class_123',
    })
    session_id = response.json['session_id']
    
    # Student records attendance with geolocation
    response = client.post('/api/attendance/record', json={
        'session_id': session_id,
        'latitude': 40.1285,
        'longitude': -88.2435,
    }, headers={
        'X-Session-Token': token,
        'User-Agent': user_agent,
    })
    
    assert response.status_code == 200
    assert response.json['status'] == 'recorded'
```

---

## Logging & Monitoring

All security events are logged with structured context:

```python
logger.warning(
    'VPN access blocked',
    extra={
        'user_id': 'student_123',
        'ip': '203.0.113.45',
        'vpn_provider': 'NordVPN',
    }
)
```

**Monitor these security events:**
- VPN/Proxy/TOR access attempts
- Emulator/rooted device usage
- Device changes/mismatches
- Failed MFA attempts
- New account isolation violations
- Geolocation boundary violations
- Session token rotation anomalies
- Admin sensitive action attempts
- Offline sync tampering

---

## Deployment Checklist

- [ ] Verify `ENVIRONMENT=production`
- [ ] Confirm all env vars set (secrets, keys)
- [ ] Enable MFA for all admin accounts
- [ ] Whitelist admin IPs
- [ ] Configure geofences for institutions
- [ ] Set campus network SSIDs
- [ ] Enable geolocation requirement on login
- [ ] Disable debug mode
- [ ] Verify security headers in production
- [ ] Set up monitoring for security events
- [ ] Configure offline sync for mobile apps
- [ ] Test VPN blocking
- [ ] Test device fingerprinting
- [ ] Test session rotation
- [ ] Test attendance anti-proxy

---

## Troubleshooting

### "VPN access not permitted"
- User is behind VPN
- Add user IP to whitelist if legitimate
- Check `block_vpn` configuration

### "Session expired"
- Token TTL exceeded (default 1 hour)
- User was inactive (default 15 minutes)
- Reset session with login

### "Device mismatch"
- User changed devices
- User shares device
- Browser cached old fingerprint
- Check device change history

### "Geolocation failed"
- GPS not enabled on device
- GPS accuracy too poor (> 100m)
- User outside geofence
- Verify campus coordinates

---

## Support & Documentation

For issues, check:
1. Security module docstrings (`src/infrastructure/security/*.py`)
2. Decorator implementation (`src/presentation/decorators/security_decorators.py`)
3. Integration tests (if available)
4. Logs for specific security event context

---

**Last Updated:** 2026-06-06
**Version:** 1.0
**Status:** Production Ready
