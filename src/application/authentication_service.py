import logging
import warnings
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from src.domain.entities import User, UserRole
from src.application.auth_service import auth_service as _active_auth_service

logger = logging.getLogger(__name__)

warnings.warn(
    "src.application.authentication_service is deprecated and will be removed in a future release. "
    "Use src.application.auth_service instead.",
    DeprecationWarning,
    stacklevel=2
)


class AuthenticationService:
    """DEPRECATED: Delegates to src.application.auth_service.AuthenticationService.
    
    This class is kept only for backward compatibility with legacy test scripts.
    New code should import from src.application.auth_service directly.
    """
    
    def __init__(self, firebase_service=None):
        logger.warning("AuthenticationService (deprecated) instantiated - use auth_service from src.application.auth_service")
        self._delegate = _active_auth_service
        self.firebase_service = firebase_service
    
    def authenticate_user(self, email: str, password: str, remember_me: bool = False,
                         device_fingerprint: Optional[str] = None,
                         ip_address: Optional[str] = None,
                         user_agent: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self._delegate.authenticate_user(email, password, remember_me,
                                                device_fingerprint, ip_address, user_agent)
    
    def register_user(self, email: str, password: str, first_name: str, last_name: str,
                      role: UserRole, institution_id: str, voucher_code: str,
                      student_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self._delegate.register_user(email, password, first_name, last_name,
                                            role, institution_id, voucher_code=voucher_code)
    
    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        return self._delegate.get_user_by_token(token)
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        return self._delegate.verify_password(password, password_hash)
    
    def _hash_password(self, password: str) -> str:
        return self._delegate.hash_password(password)
    
    def _generate_access_token(self, user_data: Dict[str, Any]) -> str:
        return self._delegate._generate_access_token(user_data)
    
    def _generate_refresh_token(self, user_id: str, remember_me: bool) -> str:
        return self._delegate._generate_refresh_token(user_id, remember_me)
