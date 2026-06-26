"""
SESSION SECURITY MODULE
Attendrix distributed attendance system

Token rotation, session expiration, device binding, inactivity timeout, and re-authentication.
"""

import time
import uuid
import hashlib
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class SessionToken:
    """Represents a secure session token."""
    token_id: str
    user_id: str
    device_fingerprint_id: str
    issued_at: int  # Unix timestamp
    expires_at: int  # Unix timestamp
    last_activity: int  # Unix timestamp
    rotation_count: int = 0
    is_valid: bool = True
    institution_id: str = None
    ip_address: str = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_expired(self) -> bool:
        return int(time.time()) > self.expires_at

    @property
    def is_inactive(self, timeout_seconds: int = 900) -> bool:
        return (int(time.time()) - self.last_activity) > timeout_seconds


class SessionManager:
    """Manages secure session tokens with rotation and binding."""

    def __init__(self, token_ttl_seconds: int = 3600, inactivity_timeout_seconds: int = 900):
        """
        Initialize session manager.
        
        Args:
            token_ttl_seconds: Token lifetime (default: 1 hour)
            inactivity_timeout_seconds: Inactivity timeout (default: 15 minutes)
        """
        self.token_ttl = token_ttl_seconds
        self.inactivity_timeout = inactivity_timeout_seconds
        self.sessions: Dict[str, SessionToken] = {}  # In production: use Redis/database
        self.token_history: Dict[str, list] = {}  # Track rotations per user

    def create_session(
        self,
        user_id: str,
        device_fingerprint_id: str,
        institution_id: str,
        ip_address: str,
    ) -> SessionToken:
        """
        Create a new secure session.
        
        Args:
            user_id: User ID
            device_fingerprint_id: Device fingerprint ID
            institution_id: Institution ID for multi-tenancy
            ip_address: Client IP address
            
        Returns:
            SessionToken
        """
        now = int(time.time())
        token_id = self._generate_token_id()

        session = SessionToken(
            token_id=token_id,
            user_id=user_id,
            device_fingerprint_id=device_fingerprint_id,
            issued_at=now,
            expires_at=now + self.token_ttl,
            last_activity=now,
            institution_id=institution_id,
            ip_address=ip_address,
        )

        self.sessions[token_id] = session
        
        # Track for rotation history
        if user_id not in self.token_history:
            self.token_history[user_id] = []
        self.token_history[user_id].append(token_id)

        logger.info(
            f'Session created: user={user_id}, device={device_fingerprint_id}, institution={institution_id}',
            extra={'token_id': token_id, 'ip': ip_address}
        )

        return session

    def validate_session(
        self,
        token_id: str,
        device_fingerprint_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[SessionToken]]:
        """
        Validate session token.
        
        Args:
            token_id: Token to validate
            device_fingerprint_id: Expected device (for binding)
            ip_address: Expected IP (optional, for strict binding)
            
        Returns:
            (is_valid, error_message, session_token)
        """
        if token_id not in self.sessions:
            return False, 'Session not found', None

        session = self.sessions[token_id]

        # Check if valid flag
        if not session.is_valid:
            return False, 'Session invalidated', session

        # Check expiration
        if session.is_expired:
            logger.warning(f'Expired session: {token_id}', extra={'user_id': session.user_id})
            return False, 'Session expired. Please log in again.', session

        # Check device binding
        if device_fingerprint_id and session.device_fingerprint_id != device_fingerprint_id:
            logger.warning(
                f'Device mismatch: expected={session.device_fingerprint_id}, got={device_fingerprint_id}',
                extra={'user_id': session.user_id, 'token_id': token_id}
            )
            return False, 'Session device mismatch. Please re-authenticate.', session

        # Check IP binding (optional, stricter security)
        if ip_address and session.ip_address and session.ip_address != ip_address:
            logger.warning(
                f'IP mismatch: expected={session.ip_address}, got={ip_address}',
                extra={'user_id': session.user_id, 'token_id': token_id}
            )
            # Don't block immediately for IP mismatch (e.g., mobile network switch)
            # But log for security audit

        return True, None, session

    def rotate_token(
        self,
        old_token_id: str,
        device_fingerprint_id: str,
        ip_address: str,
    ) -> Tuple[bool, Optional[str], Optional[SessionToken]]:
        """
        Rotate session token (issue new token, invalidate old).
        
        Args:
            old_token_id: Current token to rotate
            device_fingerprint_id: Device fingerprint (must match old session)
            ip_address: Current IP address
            
        Returns:
            (success, error_message, new_session_token)
        """
        is_valid, error, old_session = self.validate_session(
            old_token_id,
            device_fingerprint_id,
        )

        if not is_valid:
            return False, error, None

        # Create new session
        new_session = self.create_session(
            user_id=old_session.user_id,
            device_fingerprint_id=device_fingerprint_id,
            institution_id=old_session.institution_id,
            ip_address=ip_address,
        )
        new_session.rotation_count = old_session.rotation_count + 1

        # Invalidate old session
        old_session.is_valid = False
        self.sessions[old_token_id] = old_session

        logger.info(
            f'Token rotated: user={old_session.user_id}, rotation_count={new_session.rotation_count}',
            extra={'old_token': old_token_id, 'new_token': new_session.token_id}
        )

        return True, None, new_session

    def check_inactivity(self, token_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if session is inactive and needs re-authentication.
        
        Args:
            token_id: Token to check
            
        Returns:
            (is_active, message)
        """
        if token_id not in self.sessions:
            return False, 'Session not found'

        session = self.sessions[token_id]
        now = int(time.time())
        time_since_activity = now - session.last_activity

        if time_since_activity > self.inactivity_timeout:
            logger.warning(
                f'Inactive session: {time_since_activity}s > {self.inactivity_timeout}s',
                extra={'user_id': session.user_id, 'token_id': token_id}
            )
            return False, f'Session inactive for {time_since_activity}s. Please re-authenticate.'

        return True, None

    def update_activity(self, token_id: str) -> bool:
        """Update session last activity timestamp."""
        if token_id not in self.sessions:
            return False

        self.sessions[token_id].last_activity = int(time.time())
        return True

    def invalidate_session(self, token_id: str) -> bool:
        """Explicitly invalidate a session (logout)."""
        if token_id not in self.sessions:
            return False

        session = self.sessions[token_id]
        session.is_valid = False
        self.sessions[token_id] = session

        logger.info(
            f'Session invalidated: user={session.user_id}',
            extra={'token_id': token_id}
        )
        return True

    def invalidate_user_sessions(self, user_id: str, except_token_id: Optional[str] = None) -> int:
        """
        Invalidate all sessions for a user (e.g., password change, suspicious activity).
        
        Args:
            user_id: User ID
            except_token_id: Token to keep valid (optional)
            
        Returns:
            Number of sessions invalidated
        """
        count = 0
        for token_id, session in list(self.sessions.items()):
            if session.user_id == user_id and token_id != except_token_id:
                session.is_valid = False
                self.sessions[token_id] = session
                count += 1

        logger.warning(
            f'Invalidated {count} sessions for user {user_id}',
            extra={'user_id': user_id, 'count': count}
        )
        return count

    def get_session_info(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Get session information for logging/audit."""
        if token_id not in self.sessions:
            return None

        session = self.sessions[token_id]
        return {
            'user_id': session.user_id,
            'institution_id': session.institution_id,
            'device_fingerprint_id': session.device_fingerprint_id,
            'issued_at': datetime.fromtimestamp(session.issued_at).isoformat(),
            'expires_at': datetime.fromtimestamp(session.expires_at).isoformat(),
            'last_activity': datetime.fromtimestamp(session.last_activity).isoformat(),
            'rotation_count': session.rotation_count,
            'is_valid': session.is_valid,
            'is_expired': session.is_expired,
            'time_remaining_seconds': max(0, session.expires_at - int(time.time())),
            'time_since_activity_seconds': int(time.time()) - session.last_activity,
        }

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions from store."""
        count = 0
        for token_id in list(self.sessions.keys()):
            if self.sessions[token_id].is_expired:
                del self.sessions[token_id]
                count += 1

        if count > 0:
            logger.info(f'Cleaned up {count} expired sessions')

        return count

    def _generate_token_id(self) -> str:
        """Generate secure random token ID."""
        raw_token = f"{uuid.uuid4()}{int(time.time())}{uuid.uuid4()}"
        return hashlib.sha256(raw_token.encode()).hexdigest()
