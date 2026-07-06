
import uuid
import bcrypt
import jwt
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

from src.infrastructure.pg_repositories import pg_repos
from src.infrastructure.models import User, UserProfile
from src.infrastructure.security.forensic_logging import forensic_logger
from config.settings import get_config

logger = logging.getLogger(__name__)
config = get_config()

class AuthenticationService:
    def __init__(self):
        pass

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False

    def register_user(self, email: str, password: str, first_name: str, last_name: str,
                     role: Any, institution_id: str,
                     phone: str = None, voucher_code: str = None, student_id: str = None) -> Dict[str, Any]:
                     
        if pg_repos.user.get_by_email(email):
            raise ValueError(f"Email {email} is already registered")

        password_hash = self.hash_password(password)
        user_id = str(uuid.uuid4())
        
        from src.domain.entities import UserRole
        role_enum = role if isinstance(role, UserRole) else UserRole(role)
        user_data = {
            'id': user_id,
            'institution_id': institution_id,
            'email': email,
            'password_hash': password_hash,
            'role': role_enum,
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        
        user_obj = User(**user_data)
        pg_repos.user.create(user_obj)
        
        from src.infrastructure.models import UserProfile
        profile_data = {
            'user_id': user_id,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'created_at': datetime.utcnow()
        }
        pg_repos.user_profile.create(UserProfile(**profile_data))
        
        return {
            'id': user_id,
            'email': email,
            'role': user_data['role'],
            'first_name': first_name,
            'last_name': last_name,
            'institution_id': institution_id
        }

    def _strip_sensitive(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        result = user_data.copy()
        if 'password_hash' in result:
            del result['password_hash']
        return result

    def _increment_failed_attempts(self, user_data: Dict[str, Any]) -> int:
        return 1

    def _reset_failed_attempts(self, user_id: str):
        pass

    def _check_account_locked(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def _check_password_expired(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def authenticate_user(self, email: str, password: str, remember_me: bool = False,
                         ip_address: str = None, user_agent: str = None,
                         device_fingerprint: str = None, institution_id: str = None) -> Dict[str, Any]:
        
        user = pg_repos.user.get_by_email(email)
        if not user:
            return {'success': False, 'error': 'Invalid credentials', 'code': 'invalid_credentials'}
            
        if not self.verify_password(password, user.password_hash):
            return {'success': False, 'error': 'Invalid credentials', 'code': 'invalid_credentials'}
            
        if not user.is_active:
            return {'success': False, 'error': 'Account inactive', 'code': 'account_inactive'}
            
        profile = pg_repos.user_profile.get_by(user_id=user.id)
        if isinstance(profile, list):
            profile = profile[0] if profile else None
        
        user_data = {
            'id': user.id,
            'email': user.email,
            'role': user.role.value if hasattr(user.role, 'value') else user.role,
            'institution_id': user.institution_id,
            'first_name': profile.first_name if profile else '',
            'last_name': profile.last_name if profile else ''
        }
        
        token = self._generate_access_token(user_data)
        refresh_token = self._generate_refresh_token(user.id)
        
        user.last_login = datetime.utcnow()
        pg_repos.user.update(user)
        
        return {
            'success': True,
            'user': user_data,
            'token': token,
            'refresh_token': refresh_token
        }

    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(refresh_token, config.SECRET_KEY, algorithms=['HS256'])
            if payload.get('type') != 'refresh':
                return None
            user = pg_repos.user.get_by_id(payload.get('user_id'))
            if not user or not user.is_active:
                return None
            user_data = {
                'id': user.id,
                'email': user.email,
                'role': user.role.value if hasattr(user.role, 'value') else user.role,
                'institution_id': user.institution_id
            }
            return {
                'token': self._generate_access_token(user_data),
                'user': user_data
            }
        except Exception:
            return None

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=['HS256'])
            if payload.get('type') != 'access':
                return None
            return payload
        except Exception:
            return None

    def logout_user(self, user_id: str, token: str = None, ip_address: str = None,
                   user_agent: str = None) -> bool:
        return True

    def change_password(self, user_id: str, current_password: str,
                       new_password: str, ip_address: str = None,
                       user_agent: str = None) -> bool:
        user = pg_repos.user.get_by_id(user_id)
        if not user or not self.verify_password(current_password, user.password_hash):
            return False
        new_hash = self.hash_password(new_password)
        pg_repos.user.update(user_id, {'password_hash': new_hash})
        return True

    def reset_password(self, email: str) -> Optional[str]:
        return "mock_reset_link"

    def verify_email(self, email: str) -> Optional[str]:
        return "mock_verification_link"

    def update_profile(self, user_id: str, data: Dict[str, Any]) -> bool:
        pg_repos.user.update(user_id, data)
        return True

    def _generate_access_token(self, user_data: Dict[str, Any]) -> str:
        payload = {
            'user_id': user_data['id'],
            'email': user_data['email'],
            'role': user_data['role'],
            'institution_id': user_data['institution_id'],
            'type': 'access',
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, config.SECRET_KEY, algorithm='HS256')

    def _generate_refresh_token(self, user_id: str) -> str:
        payload = {
            'user_id': user_id,
            'type': 'refresh',
            'exp': datetime.utcnow() + timedelta(days=7),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, config.SECRET_KEY, algorithm='HS256')

    def _log_security_event(self, user_id: str, institution_id: str, event_type: str,
                           description: str, risk_score: int = 0, ip_address: str = None,
                           user_agent: str = None):
        pass


class DeviceFingerprintService:
    def __init__(self):
        pass

    def create_fingerprint(self, user_id: str, user_agent: str, ip_address: str,
                          canvas_hash: str = None, webgl_hash: str = None,
                          audio_hash: str = None, fonts_hash: str = None,
                          screen_resolution: str = None, timezone: str = None,
                          language: str = None, cpu_cores: int = None,
                          device_memory: int = None, hardware_concurrency: int = None,
                          plugins: List[str] = None) -> Dict[str, Any]:
        return {'id': str(uuid.uuid4()), 'is_trusted': True}

    def is_trusted_device(self, user_id: str, fingerprint_hash: str) -> bool:
        return True

    def _generate_device_token(self, user_id: str, device_fingerprint: str) -> str:
        return "device_token"

    def _register_device(self, user_id: str, device_fingerprint: str, user_agent: str = None) -> bool:
        return True

    def trust_device(self, fingerprint_id: str) -> bool:
        return True

auth_service = AuthenticationService()
device_fingerprint_service = DeviceFingerprintService()
