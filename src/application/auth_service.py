from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
from flask import current_app
import bcrypt
import re
import secrets
import logging

from src.domain.entities import User, UserRole, DeviceFingerprint, SecurityLog
from src.infrastructure.firebase_service import firebase_service

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Authentication service for user management and JWT token handling"""

    def __init__(self):
        self.firebase_service = firebase_service

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False

    def register_user(self, email: str, password: str, first_name: str, last_name: str,
                    role: UserRole, institution_id: str, **kwargs) -> Optional[User]:
        try:
            email = email.strip().lower()

            # Defense-in-depth: server-side password strength validation
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

            existing = self.firebase_service.query_documents(
                'users',
                filters=[{'field': 'email', 'value': email}]
            )
            if existing:
                raise ValueError("A user with this email already exists")

            voucher_code = kwargs.get('voucher_code')
            if voucher_code:
                from src.application.voucher_management_service import VoucherManagementService
                voucher_service = VoucherManagementService(self.firebase_service)
                validation = voucher_service.validate_voucher_for_registration(
                    voucher_code=voucher_code,
                    email=email,
                    requested_role=role,
                    institution_id=institution_id
                )
                if not validation['valid']:
                    raise ValueError(validation['error'])

            password_hash = self.hash_password(password)

            firebase_uid = self.firebase_service.create_user(
                email=email,
                password=password,
                display_name=f"{first_name} {last_name}"
            )

            custom_claims = {
                'role': role.value,
                'institution_id': institution_id
            }
            self.firebase_service.set_custom_claims(firebase_uid, custom_claims)

            user = User(
                id=firebase_uid,
                institution_id=institution_id,
                email=email,
                password_hash=password_hash,
                first_name=first_name,
                last_name=last_name,
                role=role,
                phone=kwargs.get('phone'),
                profile_image_url=kwargs.get('profile_image_url'),
                is_active=kwargs.get('is_active', True),
                email_verified=kwargs.get('email_verified', False),
                phone_verified=kwargs.get('phone_verified', False),
                last_login=kwargs.get('last_login'),
                created_at=kwargs.get('created_at'),
                updated_at=kwargs.get('updated_at')
            )

            user_data = {
                'id': user.id,
                'institution_id': user.institution_id,
                'email': user.email,
                'password_hash': user.password_hash,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role.value,
                'phone': user.phone,
                'profile_image_url': user.profile_image_url,
                'is_active': user.is_active,
                'email_verified': user.email_verified,
                'phone_verified': user.phone_verified,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat()
            }

            self.firebase_service.create_document('users', user_data, user.id)

            if voucher_code:
                voucher_service.consume_voucher(voucher_code, user.id)

            logger.info(f"User registered successfully: {email}")
            return user

        except ValueError as e:
            logger.warning(f"Registration validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"User registration failed: {str(e)}")
            if 'firebase_uid' in locals():
                self.firebase_service.delete_user(firebase_uid)
            raise e

    def _strip_sensitive(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive fields from user data before returning to client"""
        return {k: v for k, v in user_data.items() if k not in ['password_hash']}

    def authenticate_user(self, email: str, password: str, remember_me: bool = False,
                         device_fingerprint: str = None, ip_address: str = None,
                         user_agent: str = None) -> Optional[Dict[str, Any]]:
        try:
            if not email or not password:
                return {'success': False, 'message': 'Invalid email or password'}

            email = email.strip().lower()

            users = self.firebase_service.query_documents(
                'users',
                filters=[{'field': 'email', 'value': email}]
            )

            if not users:
                return {'success': False, 'message': 'Invalid email or password'}

            user_data = users[0]

            stored_hash = user_data.get('password_hash')
            if not stored_hash or not self.verify_password(password, stored_hash):
                self._log_security_event(
                    user_data['id'],
                    user_data['institution_id'],
                    'login_failed',
                    'Invalid password',
                    ip_address,
                    user_agent
                )
                return {'success': False, 'message': 'Invalid email or password'}

            if not user_data.get('is_active', True):
                return {'success': False, 'message': 'Account is disabled. Please contact administrator.'}

            if device_fingerprint and remember_me:
                self._register_device(user_data['id'], device_fingerprint, user_agent)

            self.firebase_service.update_document('users', user_data['id'], {
                'last_login': datetime.utcnow().isoformat()
            })

            access_token = self._generate_access_token(user_data)
            refresh_token = self._generate_refresh_token(user_data['id'])

            if not access_token or not refresh_token:
                return {'success': False, 'message': 'Authentication failed. Please try again.'}

            self._log_security_event(
                user_data['id'],
                user_data['institution_id'],
                'login_success',
                'User logged in successfully',
                ip_address,
                user_agent
            )

            return {
                'success': True,
                'user': self._strip_sensitive(user_data),
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds()),
                'message': 'Login successful'
            }

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
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

            user_data = self.firebase_service.get_document('users', user_id)
            if not user_data or not user_data.get('is_active'):
                return None

            access_token = self._generate_access_token(user_data)

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

            user_data = self.firebase_service.get_document('users', payload.get('user_id'))
            if not user_data or not user_data.get('is_active'):
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return None

    def logout_user(self, user_id: str, ip_address: str = None,
                   user_agent: str = None) -> bool:
        try:
            self._log_security_event(
                user_id,
                None,
                'logout',
                'User logged out',
                ip_address,
                user_agent
            )
            logger.info(f"User logged out: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            return False

    def change_password(self, user_id: str, current_password: str,
                       new_password: str) -> bool:
        try:
            user_data = self.firebase_service.get_document('users', user_id)
            if not user_data:
                return False

            if not self.verify_password(current_password, user_data['password_hash']):
                return False

            new_password_hash = self.hash_password(new_password)

            self.firebase_service.update_document('users', user_id, {
                'password_hash': new_password_hash,
                'updated_at': datetime.utcnow().isoformat()
            })

            self.firebase_service.update_user(user_id, password=new_password)
            logger.info(f"Password changed for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Password change failed: {str(e)}")
            return False

    def reset_password(self, email: str) -> Optional[str]:
        try:
            return self.firebase_service.reset_password(email)
        except Exception as e:
            logger.error(f"Password reset failed: {str(e)}")
            return None

    def verify_email(self, email: str) -> Optional[str]:
        try:
            return self.firebase_service.verify_email(email)
        except Exception as e:
            logger.error(f"Email verification failed: {str(e)}")
            return None

    def update_profile(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Update user profile fields (non-password)."""
        try:
            allowed = {'first_name', 'last_name', 'phone', 'avatar_url'}
            update = {k: v for k, v in data.items() if k in allowed}
            if not update:
                return False
            update["updated_at"] = datetime.utcnow().isoformat()
            self.firebase_service.update_document("users", user_id, update)
            return True
        except Exception as e:
            logger.error(f"Profile update failed: {str(e)}")
            return False


    def _generate_access_token(self, user_data: Dict[str, Any]) -> str:
        payload = {
            'user_id': user_data['id'],
            'email': user_data['email'],
            'role': user_data['role'],
            'institution_id': user_data['institution_id'],
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

    def _log_security_event(self, user_id: str, institution_id: str, event_type: str,
                           description: str, ip_address: str = None,
                           user_agent: str = None, risk_score: int = 0):
        try:
            security_log = SecurityLog(
                user_id=user_id,
                institution_id=institution_id,
                event_type=event_type,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                risk_score=risk_score
            )

            log_data = {
                'id': security_log.id,
                'user_id': security_log.user_id,
                'institution_id': security_log.institution_id,
                'event_type': security_log.event_type,
                'description': security_log.description,
                'ip_address': security_log.ip_address,
                'user_agent': security_log.user_agent,
                'geolocation_lat': security_log.geolocation_lat,
                'geolocation_lng': security_log.geolocation_lng,
                'risk_score': security_log.risk_score,
                'is_resolved': security_log.is_resolved,
                'resolved_by': security_log.resolved_by,
                'resolved_at': security_log.resolved_at.isoformat() if security_log.resolved_at else None,
                'created_at': security_log.created_at.isoformat()
            }

            self.firebase_service.create_document('security_logs', log_data)
        except Exception as e:
            logger.error(f"Failed to log security event: {str(e)}")


class DeviceFingerprintService:
    """Service for device fingerprinting and security"""

    def __init__(self):
        self.firebase_service = firebase_service

    def create_fingerprint(self, user_id: str, user_agent: str, ip_address: str,
                          screen_resolution: str = None, timezone: str = None,
                          language: str = None) -> str:
        try:
            import hashlib

            fingerprint_data = f"{user_agent}_{ip_address}_{screen_resolution}_{timezone}_{language}"
            fingerprint_hash = hashlib.sha256(fingerprint_data.encode()).hexdigest()

            existing_fingerprints = self.firebase_service.query_documents(
                'device_fingerprints',
                filters=[
                    {'field': 'user_id', 'value': user_id},
                    {'field': 'fingerprint_hash', 'value': fingerprint_hash}
                ]
            )

            if existing_fingerprints:
                self.firebase_service.update_document(
                    'device_fingerprints',
                    existing_fingerprints[0]['id'],
                    {'last_seen': datetime.utcnow().isoformat()}
                )
                return existing_fingerprints[0]['id']

            device_fingerprint = DeviceFingerprint(
                user_id=user_id,
                fingerprint_hash=fingerprint_hash,
                user_agent=user_agent,
                ip_address=ip_address,
                screen_resolution=screen_resolution,
                timezone=timezone,
                language=language
            )

            fingerprint_data = {
                'id': device_fingerprint.id,
                'user_id': device_fingerprint.user_id,
                'fingerprint_hash': device_fingerprint.fingerprint_hash,
                'user_agent': device_fingerprint.user_agent,
                'ip_address': device_fingerprint.ip_address,
                'screen_resolution': device_fingerprint.screen_resolution,
                'timezone': device_fingerprint.timezone,
                'language': device_fingerprint.language,
                'is_trusted': device_fingerprint.is_trusted,
                'last_seen': device_fingerprint.last_seen.isoformat(),
                'created_at': device_fingerprint.created_at.isoformat()
            }

            self.firebase_service.create_document('device_fingerprints', fingerprint_data)
            logger.info(f"Device fingerprint created for user: {user_id}")
            return device_fingerprint.id

        except Exception as e:
            logger.error(f"Failed to create device fingerprint: {str(e)}")
            return None

    def is_trusted_device(self, user_id: str, fingerprint_hash: str) -> bool:
        try:
            fingerprints = self.firebase_service.query_documents(
                'device_fingerprints',
                filters=[
                    {'field': 'user_id', 'value': user_id},
                    {'field': 'fingerprint_hash', 'value': fingerprint_hash},
                    {'field': 'is_trusted', 'value': True}
                ]
            )
            return len(fingerprints) > 0
        except Exception as e:
            logger.error(f"Failed to check trusted device: {str(e)}")
            return False

    def _generate_device_token(self, user_id: str, device_fingerprint: str) -> str:
        try:
            return secrets.token_urlsafe(32)
        except Exception as e:
            logger.error(f"Failed to generate device token: {str(e)}")
            return None

    def _register_device(self, user_id: str, device_fingerprint: str, user_agent: str = None) -> bool:
        try:
            existing_devices = self.firebase_service.query_documents(
                'device_fingerprints',
                filters=[
                    {'field': 'user_id', 'value': user_id},
                    {'field': 'fingerprint_hash', 'value': device_fingerprint}
                ]
            )

            if existing_devices:
                self.firebase_service.update_document(
                    'device_fingerprints',
                    existing_devices[0]['id'],
                    {'last_used': datetime.utcnow().isoformat(), 'user_agent': user_agent, 'is_trusted': True}
                )

                trusted_device_data = {
                    'id': f"trusted_{user_id}_{device_fingerprint[:8]}",
                    'user_id': user_id,
                    'device_fingerprint': device_fingerprint,
                    'browser_info': user_agent,
                    'first_login_date': datetime.utcnow().isoformat(),
                    'last_active_date': datetime.utcnow().isoformat(),
                    'trust_status': 'trusted',
                    'session_token': self._generate_device_token(user_id, device_fingerprint)
                }

                existing_trusted = self.firebase_service.query_documents(
                    'trusted_devices',
                    filters=[
                        {'field': 'user_id', 'value': user_id},
                        {'field': 'device_fingerprint', 'value': device_fingerprint}
                    ]
                )

                if existing_trusted:
                    self.firebase_service.update_document('trusted_devices', existing_trusted[0]['id'], trusted_device_data)
                else:
                    self.firebase_service.create_document('trusted_devices', trusted_device_data)

                return True
            else:
                device_data = {
                    'user_id': user_id,
                    'fingerprint': device_fingerprint,
                    'user_agent': user_agent,
                    'is_trusted': True,
                    'created_at': datetime.utcnow().isoformat(),
                    'last_used': datetime.utcnow().isoformat()
                }
                self.firebase_service.create_document('device_fingerprints', device_data)
                logger.info(f"New device registered for user: {user_id}")

            return True
        except Exception as e:
            logger.error(f"Failed to register device: {str(e)}")
            return False

    def trust_device(self, fingerprint_id: str) -> bool:
        try:
            self.firebase_service.update_document(
                'device_fingerprints',
                fingerprint_id,
                {'is_trusted': True}
            )
            logger.info(f"Device trusted: {fingerprint_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to trust device: {str(e)}")
            return False


auth_service = AuthenticationService()
device_fingerprint_service = DeviceFingerprintService()
