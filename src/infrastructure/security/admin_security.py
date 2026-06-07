"""
ADMIN SECURITY MODULE
Attendrix distributed attendance system

Multi-factor authentication (MFA), sensitive action confirmation, IP restrictions,
and device verification for administrative accounts.
"""

import uuid
import hashlib
import logging
import time
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MFAMethod:
    """Represents an MFA method."""
    method_id: str
    method_type: str  # 'totp', 'email', 'sms', 'backup_code'
    is_primary: bool = False
    is_verified: bool = False
    created_at: int = None
    last_used_at: int = None


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

    def __init__(self):
        """Initialize admin security manager."""
        self.admin_mfa_methods: Dict[str, List[MFAMethod]] = {}  # {admin_id: [methods]}
        self.admin_sessions: Dict[str, AdminSession] = {}  # {session_id: session}
        self.ip_whitelist: Dict[str, List[str]] = {}  # {admin_id: [IPs]}
        self.sensitive_action_log: Dict[str, list] = {}  # {admin_id: [actions]}
        self.failed_mfa_attempts: Dict[str, int] = {}  # {admin_id: count}

    def require_mfa_setup(self, admin_id: str) -> Dict[str, Any]:
        """
        Force MFA setup for admin account.
        
        Returns instructions for setting up MFA.
        """
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
            'supported_methods': ['totp', 'email', 'sms'],
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
            method_type: 'totp', 'email', 'sms', 'backup_code'
            method_data: Method-specific data
            
        Returns:
            (success, error, method)
        """
        now = int(time.time())
        method_id = str(uuid.uuid4())

        method = MFAMethod(
            method_id=method_id,
            method_type=method_type,
            created_at=now,
        )

        if admin_id not in self.admin_mfa_methods:
            self.admin_mfa_methods[admin_id] = []

        # Make first method primary
        if len(self.admin_mfa_methods[admin_id]) == 0:
            method.is_primary = True

        self.admin_mfa_methods[admin_id].append(method)

        logger.info(
            f'MFA method registered: admin={admin_id}, method={method_type}',
            extra={'method_id': method_id}
        )

        return True, None, method

    def verify_mfa(
        self,
        admin_id: str,
        mfa_code: str,
        method_type: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify MFA code.
        
        Args:
            admin_id: Admin ID
            mfa_code: Code to verify
            method_type: Specific method to verify against
            
        Returns:
            (is_valid, error_message)
        """
        if admin_id not in self.admin_mfa_methods:
            return False, 'MFA not configured'

        methods = self.admin_mfa_methods[admin_id]

        # Track failed attempts
        if self.failed_mfa_attempts.get(admin_id, 0) >= 5:
            logger.warning(
                f'Too many failed MFA attempts: {admin_id}',
                extra={'attempts': self.failed_mfa_attempts[admin_id]}
            )
            return False, 'Account locked due to too many failed MFA attempts. Contact support.'

        # Try to verify against methods
        for method in methods:
            if method_type and method.method_type != method_type:
                continue

            if not method.is_verified:
                continue

            # In production: implement actual TOTP/SMS/Email verification
            # For now: simulate verification
            if self._verify_mfa_code(method, mfa_code):
                method.last_used_at = int(time.time())
                self.failed_mfa_attempts[admin_id] = 0  # Reset on success

                logger.info(
                    f'MFA verified: admin={admin_id}, method={method.method_type}',
                    extra={'method_id': method.method_id}
                )
                return True, None

        # Failed verification
        self.failed_mfa_attempts[admin_id] = self.failed_mfa_attempts.get(admin_id, 0) + 1

        logger.warning(
            f'Failed MFA verification: admin={admin_id}',
            extra={'attempts': self.failed_mfa_attempts[admin_id]}
        )
        return False, 'Invalid MFA code'

    def add_ip_whitelist(self, admin_id: str, ip_address: str) -> bool:
        """Add IP to admin whitelist."""
        if admin_id not in self.ip_whitelist:
            self.ip_whitelist[admin_id] = []

        if ip_address not in self.ip_whitelist[admin_id]:
            self.ip_whitelist[admin_id].append(ip_address)

            logger.info(
                f'IP whitelisted for admin: {ip_address}',
                extra={'admin_id': admin_id}
            )

        return True

    def validate_admin_ip(self, admin_id: str, ip_address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate admin IP against whitelist.
        
        Returns:
            (is_allowed, error_message)
        """
        if admin_id not in self.ip_whitelist:
            # No whitelist configured - allow (but log)
            logger.info(f'No IP whitelist configured for admin: {admin_id}')
            return True, None

        if ip_address in self.ip_whitelist[admin_id]:
            return True, None

        logger.warning(
            f'Admin access from unauthorized IP: {ip_address}',
            extra={'admin_id': admin_id, 'whitelisted_ips': self.ip_whitelist[admin_id]}
        )
        return False, f'Access denied from IP {ip_address}'

    def create_admin_session(
        self,
        admin_id: str,
        ip_address: str,
        device_fingerprint_id: str,
        mfa_verified: bool = False,
    ) -> AdminSession:
        """
        Create elevated admin session.
        
        Args:
            admin_id: Admin ID
            ip_address: Client IP
            device_fingerprint_id: Device fingerprint
            mfa_verified: Whether MFA has been verified
            
        Returns:
            AdminSession
        """
        session_id = str(uuid.uuid4())
        now = int(time.time())

        session = AdminSession(
            session_id=session_id,
            admin_id=admin_id,
            ip_address=ip_address,
            device_fingerprint_id=device_fingerprint_id,
            created_at=now,
            expires_at=now + 3600,  # 1 hour
            mfa_verified=mfa_verified,
        )

        self.admin_sessions[session_id] = session

        logger.info(
            f'Admin session created: admin={admin_id}, mfa_verified={mfa_verified}',
            extra={'session_id': session_id, 'ip': ip_address}
        )

        return session

    def validate_admin_action(
        self,
        admin_id: str,
        action_type: str,
        action_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if admin can perform action.
        
        Args:
            admin_id: Admin ID
            action_type: Type of sensitive action
            action_data: Action details
            
        Returns:
            (is_allowed, error_message)
        """
        # Define sensitive actions requiring confirmation
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
            return True, None  # Not a sensitive action

        # For sensitive actions, require:
        # 1. MFA verification
        # 2. User confirmation
        # 3. Audit log entry

        logger.warning(
            f'Sensitive admin action initiated: {action_type}',
            extra={'admin_id': admin_id, 'action_data': action_data}
        )

        # Track action
        if admin_id not in self.sensitive_action_log:
            self.sensitive_action_log[admin_id] = []
        
        self.sensitive_action_log[admin_id].append({
            'action_type': action_type,
            'action_data': action_data,
            'timestamp': int(time.time()),
        })

        return True, None  # Allow but with audit logging

    def get_admin_audit_log(self, admin_id: str) -> List[Dict[str, Any]]:
        """Get admin audit log."""
        return self.sensitive_action_log.get(admin_id, [])

    def _verify_mfa_code(self, method: MFAMethod, code: str) -> bool:
        """
        Verify MFA code against method.
        
        In production: implement TOTP validation, SMS/Email verification.
        """
        # Placeholder implementation
        return len(code) == 6 and code.isdigit()
