from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
from flask import current_app
import bcrypt
import re
import secrets
import logging

from src.domain.entities import UserRole
from src.infrastructure.models import User, UserProfile
from src.infrastructure.security.redis_session_store import redis_token_blacklist

logger = logging.getLogger(__name__)

class PostgresAuthService:
    """Authentication service for PostgreSQL user management and JWT token handling"""

    def __init__(self, user_repository):
        self.user_repository = user_repository

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False

    def register_user(self, email: str, password: str, first_name: str, last_name: str,
                    role: UserRole, institution_id: str, **kwargs) -> Optional[User]:
        try:
            _allowed_extra = {'phone', 'profile_image_url', 'voucher_code', 'student_id'}
            for key in kwargs:
                if key not in _allowed_extra:
                    logger.warning(f"Rejected disallowed registration field: {key}")
                    raise ValueError(f"Unexpected field: {key}")

            email = email.strip().lower()

            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters long")
            if not re.search(r'[A-Z]', password):
                raise ValueError("Password must contain at least one uppercase letter")
            if not re.search(r'[a-z]', password):
                raise ValueError("Password must contain at least one lowercase letter")
            if not re.search(r'[0-9]', password):
                raise ValueError("Password must contain at least one number")
            if not re.search(r'[!@#$%^&*(),.?\":{}|<>_\-]', password):
                raise ValueError("Password must contain at least one special character")

            existing = self.user_repository.get_by_email(email)
            if existing:
                raise ValueError("A user with this email already exists")

            voucher_code = kwargs.get('voucher_code')
            if voucher_code:
                from src.application.voucher_management_service import VoucherManagementService
                from src.infrastructure.pg_repositories.voucher_repository import PostgresVoucherRepository
                voucher_service = VoucherManagementService(PostgresVoucherRepository())
                validation = voucher_service.validate_voucher_for_registration(
                    voucher_code=voucher_code,
                    email=email,
                    requested_role=role,
                    institution_id=institution_id
                )
                if not validation['valid']:
                    raise ValueError(validation['error'])

            password_hash = self.hash_password(password)

            # Create User model
            user = User(
                email=email,
                password_hash=password_hash,
                role=role,
                institution_id=institution_id,
                is_active=True
            )
            
            # Create UserProfile model
            profile = UserProfile(
                first_name=first_name,
                last_name=last_name,
                phone=kwargs.get('phone'),
                profile_image_url=kwargs.get('profile_image_url'),
                student_id=kwargs.get('student_id')
            )
            user.profile = profile
            
            created_user = self.user_repository.create(user)
            
            # Consume voucher if one was used
            if voucher_code:
                from src.application.voucher_management_service import VoucherManagementService
                from src.infrastructure.pg_repositories.voucher_repository import PostgresVoucherRepository
                voucher_service = VoucherManagementService(PostgresVoucherRepository())
                voucher_service.consume_voucher(voucher_code, created_user.id)
                
            return created_user

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            raise

    def _strip_sensitive(self, user: User) -> Dict[str, Any]:
        """Convert user to dict and remove sensitive fields"""
        data = {
            'id': user.id,
            'email': user.email,
            'first_name': user.profile.first_name if user.profile else None,
            'last_name': user.profile.last_name if user.profile else None,
            'role': user.role.value if hasattr(user.role, 'value') else user.role,
            'institution_id': user.institution_id,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'updated_at': user.updated_at.isoformat() if user.updated_at else None,
        }
        return data

    def authenticate_user(self, email: str, password: str, remember_me: bool = False,
                         device_fingerprint: str = None, ip_address: str = None,
                         user_agent: str = None, institution_id: str = None) -> Optional[Dict[str, Any]]:
        try:
            if not email or not password:
                return {'success': False, 'message': 'Invalid email or password'}

            email = email.strip().lower()

            user = self.user_repository.get_by_email(email)

            if not user:
                return {'success': False, 'message': 'Invalid email or password'}

            if institution_id is not None and institution_id != user.institution_id:
                return {'success': False, 'message': 'Invalid email or password'}

            if not self.verify_password(password, user.password_hash):
                return {'success': False, 'message': 'Invalid email or password'}

            if not user.is_active:
                return {'success': False, 'message': 'Account is disabled. Please contact administrator.'}

            # Generate tokens
            access_token = self._generate_access_token(user)
            refresh_token = self._generate_refresh_token(user.id)

            if not access_token or not refresh_token:
                return {'success': False, 'message': 'Authentication failed. Please try again.'}

            # Since last_login is not in User anymore, we don't update it on User.
            # It could be added to UserProfile if needed, but for now we skip.
            self.user_repository.update(user)

            return {
                'success': True,
                'user': self._strip_sensitive(user),
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds()),
                'message': 'Login successful'
            }

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Invalid email or password'}

    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(
                refresh_token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )

            user_id = payload.get('user_id')
            if not user_id:
                return None

            user = self.user_repository.get(user_id)
            if not user or not user.is_active:
                return None

            access_token = self._generate_access_token(user)

            return {
                'access_token': access_token,
                'token_type': 'Bearer',
                'expires_in': int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds())
            }

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            return None

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )

            if redis_token_blacklist.is_blacklisted(payload.get('jti', '')):
                logger.warning(f"Token blacklisted: jti={payload.get('jti', 'none')[:16]}")
                return None

            user = self.user_repository.get(payload.get('user_id'))
            if not user or not user.is_active:
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return None

    def logout_user(self, user_id: str, token: str = None, ip_address: str = None,
                   user_agent: str = None) -> bool:
        try:
            if token:
                try:
                    payload = jwt.decode(
                        token,
                        current_app.config['JWT_SECRET_KEY'],
                        algorithms=['HS256']
                    )
                    jti = payload.get('jti')
                    exp = payload.get('exp', 0)
                    if jti:
                        redis_token_blacklist.blacklist(jti, exp)
                        logger.info(f"Token blacklisted: jti={jti[:16]}")
                except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception) as decode_err:
                    logger.warning(f"Could not decode token for jti blacklist: {decode_err}")

            logger.info(f"User logged out: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            return False

    def change_password(self, user_id: str, current_password: str,
                       new_password: str) -> bool:
        try:
            user = self.user_repository.get(user_id)
            if not user:
                return False

            if not self.verify_password(current_password, user.password_hash):
                return False

            if current_password == new_password:
                return False

            user.password_hash = self.hash_password(new_password)
            self.user_repository.update(user)
            logger.info(f"Password changed for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Password change failed: {str(e)}")
            return False

    def update_profile(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Update user profile fields (non-password)."""
        try:
            user = self.user_repository.get(user_id)
            if not user:
                return False
                
            allowed = {'first_name', 'last_name', 'phone', 'profile_image_url'}
            updated = False
            for k, v in data.items():
                if k in allowed:
                    setattr(user, k, v)
                    updated = True
                    
            if not updated:
                return False
                
            user.updated_at = datetime.utcnow()
            self.user_repository.update(user)
            return True
        except Exception as e:
            logger.error(f"Profile update failed: {str(e)}")
            return False

    def _generate_access_token(self, user: User) -> str:
        payload = {
            'user_id': user.id,
            'jti': secrets.token_hex(16),
            'email': user.email,
            'role': user.role.value if hasattr(user.role, 'value') else user.role,
            'institution_id': user.institution_id,
            'exp': datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

    def _generate_refresh_token(self, user_id: str) -> str:
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES'],
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')
