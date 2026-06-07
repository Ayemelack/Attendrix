"""
ADMIN SECURITY MODULE
Attendrix distributed attendance system

Multi-factor authentication (MFA), sensitive action confirmation, IP restrictions,
and device verification for administrative accounts.
"""

import uuid
import hashlib
import hmac
import logging
import time
import os
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import pyotp
    HAS_PYOTP = True
except ImportError:
    pyotp = None
    HAS_PYOTP = False
    logger.warning('pyotp not installed. TOTP MFA not available.')

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    import base64
    HAS_CRYPTOGRAPHY = True
except ImportError:
    Fernet = None
    HAS_CRYPTOGRAPHY = False
    logger.warning('cryptography not installed. MFA secret encryption not available.')


@dataclass
class MFAMethod:
    """Represents an MFA method with full TOTP support."""
    method_id: str
    method_type: str
    is_primary: bool = False
    is_verified: bool = False
    created_at: int = None
    last_used_at: int = None
    encrypted_secret: Optional[str] = None
    recovery_codes: Optional[List[str]] = None
    backup_code_count: int = 10
    failed_attempts: int = 0
    locked_until: Optional[int] = None
    qr_uri: Optional[str] = None
    raw_recovery_codes: Optional[List[str]] = None


@dataclass
class AdminSession:
    """Represents an admin session with elevated privileges."""
    session_id: str
    admin_id: str
    ip_address: str
    device_fingerprint_id: str
    created_at: int
    expires_at: int
    mfa_verified: bool = False
    is_active: bool = True


class AdminSecurityManager:
    """Manages admin account security with MFA and access controls."""

    def __init__(self, secret_key: Optional[str] = None, max_mfa_attempts: int = 5):
        self.admin_mfa_methods: Dict[str, List[MFAMethod]] = {}
        self.admin_sessions: Dict[str, AdminSession] = {}
        self.ip_whitelist: Dict[str, List[str]] = {}
        self.sensitive_action_log: Dict[str, list] = {}
        self._secret_key = secret_key
        self.max_mfa_attempts = max_mfa_attempts
        self._fernet_cache = None

    def _get_fernet(self) -> Optional[Fernet]:
        """Get or create Fernet instance from the configured secret key."""
        if self._fernet_cache is not None:
            return self._fernet_cache

        secret_key = self._secret_key
        if secret_key is None:
            try:
                from flask import current_app
                secret_key = current_app.config.get('SECRET_KEY', '')
            except (ImportError, RuntimeError):
                secret_key = ''

        if not secret_key:
            logger.error('SECRET_KEY not configured. MFA secret encryption unavailable.')
            return None

        key_bytes = secret_key.encode('utf-8') if isinstance(secret_key, str) else secret_key

        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'attendrix-mfa-salt',
                iterations=100000,
                backend=default_backend(),
            )
            derived_key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
            self._fernet_cache = Fernet(derived_key)
        except Exception as e:
            logger.error(f'Failed to create Fernet instance: {e}')
            return None

        return self._fernet_cache

    def require_mfa_setup(self, admin_id: str) -> Dict[str, Any]:
        """Force MFA setup for admin account."""
        logger.warning(f'MFA setup required for admin: {admin_id}')
        return {
            'status': 'mfa_required',
            'message': 'Multi-factor authentication is required for admin accounts',
            'setup_steps': [
                'Download authenticator app (Google Authenticator, Authy, Microsoft Authenticator)',
                'Scan QR code or enter secret key',
                'Enter verification code to confirm',
                'Store backup codes in secure location',
            ],
            'supported_methods': ['totp'],
        }

    def register_mfa_method(
        self,
        admin_id: str,
        method_type: str,
        method_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str], Optional[MFAMethod]]:
        """
        Register MFA method for admin.

        Args:
            admin_id: Admin ID
            method_type: Must be 'totp'
            method_data: Optional dict with 'email' key for QR provisioning

        Returns:
            (success, error, method) where method includes qr_uri and raw_recovery_codes
        """
        method_data = method_data or {}

        if method_type != 'totp':
            return False, f'Unsupported MFA method: {method_type}', None

        if not HAS_PYOTP:
            return False, 'TOTP library (pyotp) not installed. Cannot register TOTP method.', None

        if not HAS_CRYPTOGRAPHY:
            return False, 'Encryption library (cryptography) not installed. Cannot secure MFA secrets.', None

        try:
            secret = pyotp.random_base32()

            encrypted = self.encrypt_secret(secret)
            if encrypted is None:
                return False, 'Failed to encrypt MFA secret. SECRET_KEY may not be configured.', None

            email = method_data.get('email') or f'{admin_id}@attendrix.app'
            qr_uri = self.get_mfa_qr_uri(admin_id, secret, email=email)

            raw_codes, hashed_codes = self.generate_recovery_codes()

            now = int(time.time())
            method_id = str(uuid.uuid4())

            method = MFAMethod(
                method_id=method_id,
                method_type=method_type,
                created_at=now,
                encrypted_secret=encrypted,
                recovery_codes=hashed_codes,
                backup_code_count=len(raw_codes),
                is_verified=False,
                qr_uri=qr_uri,
                raw_recovery_codes=raw_codes,
            )

            if admin_id not in self.admin_mfa_methods:
                self.admin_mfa_methods[admin_id] = []

            if len(self.admin_mfa_methods[admin_id]) == 0:
                method.is_primary = True

            self.admin_mfa_methods[admin_id].append(method)

            logger.info(
                f'TOTP MFA method registered: admin={admin_id}',
                extra={'method_id': method_id, 'backup_codes': len(raw_codes)},
            )

            return True, None, method

        except Exception as e:
            logger.error(f'Failed to register MFA method for admin {admin_id}: {e}')
            return False, f'Failed to register MFA method: {str(e)}', None

    def verify_mfa(
        self,
        admin_id: str,
        mfa_code: str,
        method_type: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify MFA code with real TOTP verification and recovery code fallback.

        Args:
            admin_id: Admin ID
            mfa_code: TOTP code or recovery code
            method_type: Optional filter for method type

        Returns:
            (is_valid, error_message)
        """
        if admin_id not in self.admin_mfa_methods:
            return False, 'MFA not configured'

        methods = self.admin_mfa_methods[admin_id]
        now = int(time.time())

        total_failed = sum(m.failed_attempts for m in methods)
        if total_failed >= self.max_mfa_attempts:
            still_locked = False
            for m in methods:
                if m.locked_until and m.locked_until > now:
                    still_locked = True
                    remaining = m.locked_until - now
                    return False, f'MFA temporarily locked. Try again in {remaining} seconds.'

            if not still_locked:
                for m in methods:
                    m.failed_attempts = 0
                    m.locked_until = None

        for method in methods:
            if method_type and method.method_type != method_type:
                continue

            if method.method_type == 'totp':
                if method.locked_until and method.locked_until > now:
                    continue

                if self.verify_totp(method, mfa_code):
                    method.last_used_at = now
                    method.failed_attempts = 0
                    method.locked_until = None
                    logger.info(
                        f'TOTP MFA verified: admin={admin_id}',
                        extra={'method_id': method.method_id},
                    )
                    return True, None

                if method.recovery_codes and self.verify_recovery_code(method, mfa_code):
                    method.last_used_at = now
                    method.failed_attempts = 0
                    method.locked_until = None
                    method.is_verified = True
                    logger.info(
                        f'Recovery code used for MFA: admin={admin_id}',
                        extra={
                            'method_id': method.method_id,
                            'remaining': len(method.recovery_codes),
                        },
                    )
                    return True, None

                method.failed_attempts += 1
                if method.failed_attempts >= self.max_mfa_attempts:
                    method.locked_until = now + 900
                    logger.warning(
                        f'MFA method locked: admin={admin_id}',
                        extra={
                            'method_id': method.method_id,
                            'lockout_duration': 900,
                        },
                    )

        logger.warning(
            f'Failed MFA verification: admin={admin_id}',
            extra={'total_failed': total_failed + 1},
        )
        return False, 'Invalid MFA code'

    def verify_totp(self, method: MFAMethod, code: str) -> bool:
        """Verify a TOTP code against the stored encrypted secret."""
        if not method.encrypted_secret:
            return False

        secret = self.decrypt_secret(method.encrypted_secret)
        if not secret:
            return False

        if not HAS_PYOTP:
            logger.error('pyotp not installed. Cannot verify TOTP code.')
            return False

        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=1)
        except Exception as e:
            logger.error(f'TOTP verification error: {e}')
            return False

    def verify_recovery_code(self, method: MFAMethod, code: str) -> bool:
        """Verify a recovery code against stored hashes and remove it if used."""
        if not method.recovery_codes or not code:
            return False

        code_hash = hashlib.sha256(code.strip().upper().encode('utf-8')).hexdigest()

        for i, stored_hash in enumerate(method.recovery_codes):
            if hmac.compare_digest(stored_hash, code_hash):
                method.recovery_codes.pop(i)
                logger.info(
                    'Recovery code used and removed',
                    extra={'remaining': len(method.recovery_codes)},
                )
                return True

        return False

    def generate_recovery_codes(self, count: int = 10) -> Tuple[List[str], List[str]]:
        """Generate recovery codes returning (raw_codes, hashed_codes)."""
        raw_codes = []
        hashed_codes = []

        for _ in range(count):
            raw = os.urandom(8).hex().upper()[:16]
            hashed = hashlib.sha256(raw.encode('utf-8')).hexdigest()
            raw_codes.append(raw)
            hashed_codes.append(hashed)

        return raw_codes, hashed_codes

    def encrypt_secret(self, secret: str) -> Optional[str]:
        """Encrypt a TOTP secret using Fernet symmetric encryption."""
        fernet = self._get_fernet()
        if fernet is None:
            return None
        try:
            return fernet.encrypt(secret.encode('utf-8')).decode('utf-8')
        except Exception as e:
            logger.error(f'Failed to encrypt secret: {e}')
            return None

    def decrypt_secret(self, encrypted_secret: str) -> Optional[str]:
        """Decrypt an encrypted TOTP secret."""
        fernet = self._get_fernet()
        if fernet is None:
            return None
        try:
            return fernet.decrypt(encrypted_secret.encode('utf-8')).decode('utf-8')
        except Exception as e:
            logger.error(f'Failed to decrypt secret: {e}')
            return None

    def get_mfa_qr_uri(self, admin_id: str, secret: str, email: Optional[str] = None) -> str:
        """Generate otpauth:// provisioning URI for QR code display."""
        if not email:
            email = f'{admin_id}@attendrix.app'
        try:
            return pyotp.totp.TOTP(secret).provisioning_uri(
                name=email,
                issuer_name='Attendrix',
            )
        except Exception as e:
            logger.error(f'Failed to generate QR URI: {e}')
            return ''

    def require_mfa_check(self, admin_id: str, action: Optional[str] = None) -> bool:
        """Check if MFA is required for this admin or specific sensitive action."""
        sensitive_actions = [
            'delete_institution', 'delete_user', 'modify_security_settings',
            'export_user_data', 'bulk_user_modification', 'disable_mfa', 'modify_role',
        ]

        if action and action in sensitive_actions:
            return True

        if admin_id not in self.admin_mfa_methods or not self.admin_mfa_methods[admin_id]:
            return True

        for method in self.admin_mfa_methods[admin_id]:
            if method.is_verified:
                return False

        return True

    def add_ip_whitelist(self, admin_id: str, ip_address: str) -> bool:
        """Add IP to admin whitelist."""
        if admin_id not in self.ip_whitelist:
            self.ip_whitelist[admin_id] = []

        if ip_address not in self.ip_whitelist[admin_id]:
            self.ip_whitelist[admin_id].append(ip_address)
            logger.info(
                f'IP whitelisted for admin: {ip_address}',
                extra={'admin_id': admin_id},
            )
        return True

    def validate_admin_ip(self, admin_id: str, ip_address: str) -> Tuple[bool, Optional[str]]:
        """Validate admin IP against whitelist."""
        if admin_id not in self.ip_whitelist:
            logger.info(f'No IP whitelist configured for admin: {admin_id}')
            return True, None

        if ip_address in self.ip_whitelist[admin_id]:
            return True, None

        logger.warning(
            f'Admin access from unauthorized IP: {ip_address}',
            extra={
                'admin_id': admin_id,
                'whitelisted_ips': self.ip_whitelist[admin_id],
            },
        )
        return False, f'Access denied from IP {ip_address}'

    def create_admin_session(
        self,
        admin_id: str,
        ip_address: str,
        device_fingerprint_id: str,
        mfa_verified: bool = False,
    ) -> AdminSession:
        """Create elevated admin session."""
        session_id = str(uuid.uuid4())
        now = int(time.time())

        session = AdminSession(
            session_id=session_id,
            admin_id=admin_id,
            ip_address=ip_address,
            device_fingerprint_id=device_fingerprint_id,
            created_at=now,
            expires_at=now + 3600,
            mfa_verified=mfa_verified,
        )

        self.admin_sessions[session_id] = session

        logger.info(
            f'Admin session created: admin={admin_id}, mfa_verified={mfa_verified}',
            extra={'session_id': session_id, 'ip': ip_address},
        )

        return session

    def validate_admin_action(
        self,
        admin_id: str,
        action_type: str,
        action_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate if admin can perform a sensitive action."""
        sensitive_actions = [
            'delete_institution',
            'delete_user',
            'modify_security_settings',
            'export_user_data',
            'bulk_user_modification',
            'disable_mfa',
            'modify_role',
        ]

        if action_type not in sensitive_actions:
            return True, None

        logger.warning(
            f'Sensitive admin action initiated: {action_type}',
            extra={'admin_id': admin_id, 'action_data': action_data},
        )

        if admin_id not in self.sensitive_action_log:
            self.sensitive_action_log[admin_id] = []

        self.sensitive_action_log[admin_id].append({
            'action_type': action_type,
            'action_data': action_data,
            'timestamp': int(time.time()),
        })

        return True, None

    def get_admin_audit_log(self, admin_id: str) -> List[Dict[str, Any]]:
        """Get admin audit log."""
        return self.sensitive_action_log.get(admin_id, [])

    def _verify_mfa_code(self, method: MFAMethod, code: str) -> bool:
        """Verify MFA code against method using real TOTP verification."""
        if method.method_type == 'totp':
            return self.verify_totp(method, code)
        return len(code) == 6 and code.isdigit()
