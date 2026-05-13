import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import current_app
import jwt
import bcrypt

from src.domain.entities import User, UserRole

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Complete authentication service rebuilt from scratch"""
    
    def __init__(self, firebase_service):
        self.firebase_service = firebase_service
        self.session_timeout_hours = 24
        self.max_remember_me_days = 30
        
        # Store Flask app context for JWT encoding
        try:
            from flask import current_app
            self._app = current_app
        except ImportError:
            # Handle case where current_app is not available (during import)
            self._app = None
    
    def authenticate_user(self, email: str, password: str, remember_me: bool = False,
                        device_fingerprint: Optional[str] = None,
                        ip_address: Optional[str] = None,
                        user_agent: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Authenticate user with clean role-based routing"""
        try:
            # Get user from database
            users = self.firebase_service.query_documents(
                'users',
                filters=[{'field': 'email', 'value': email}]
            )
            
            if not users:
                logger.warning(f"User not found: {email}")
                return None
            
            user_data = users[0]
            
            # Verify password
            if not self._verify_password(password, user_data['password_hash']):
                logger.warning(f"Invalid password for user: {email}")
                return None
            
            # Check if user is active
            if not user_data['is_active']:
                logger.warning(f"Inactive user attempted login: {email}")
                return None
            
            # Update last login
            self.firebase_service.update_document('users', user_data['id'], {
                'last_login': datetime.utcnow().isoformat(),
                'ip_address': ip_address,
                'user_agent': user_agent
            })
            
            # Generate tokens
            access_token = self._generate_access_token(user_data)
            refresh_token = self._generate_refresh_token(user_data['id'], remember_me)
            
            # Create persistent session if remember me is checked
            session_id = None
            if remember_me and device_fingerprint:
                session_id = self._create_persistent_session(user_data['id'], device_fingerprint.substring(0, 32)  # Limit to 32 chars
            
            # Verify device fingerprint if biometric enrollment exists
            biometric_verification = self._verify_device_biometric(user_data['id'], device_fingerprint)
            if biometric_verification['verified']:
                logger.info(f"Biometric verification passed for user {email} with trust score {biometric_verification['trust_score']}")
            elif biometric_verification['enrolled']:
                logger.warning(f"Biometric verification failed for user {email} - low similarity score {biometric_verification['similarity_score']}")
            else:
                logger.info(f"No biometric enrollment found for user {email}")
            
            # Return clean user data with correct role
            return {
                'user': {
                    'id': user_data['id'],
                    'email': user_data['email'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'role': user_data['role'],  # Use actual role from database
                    'institution_id': user_data['institution_id']
                },
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': self.session_timeout_hours * 3600,
                'session_id': session_id,
                'remember_me': remember_me
            }
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None
    
    def register_user(self, email: str, password: str, first_name: str, last_name: str,
                   role: UserRole, institution_id: str, voucher_code: str, 
                   student_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Professional user registration with mandatory voucher validation"""
        try:
            # VOUCHER IS MANDATORY
            if not voucher_code:
                return {'error': 'Voucher code is required for registration'}
            
            # Use professional voucher management service
            from src.application.voucher_management_service import VoucherManagementService
            voucher_service = VoucherManagementService(self.firebase_service)
            
            # Validate voucher comprehensively
            validation_result = voucher_service.validate_voucher_for_registration(
                voucher_code=voucher_code,
                email=email,
                requested_role=role,
                institution_id=institution_id
            )
            
            if not validation_result['valid']:
                return {
                    'error': validation_result['error'],
                    'error_code': validation_result.get('error_code', 'VALIDATION_FAILED')
                }
            
            # Use validated voucher details
            validated_voucher = validation_result
            email = validated_voucher.get('email_binding', email)  # Use bound email if exists
            role = validated_voucher['role']
            institution_id = validated_voucher['institution_id']
            
            # Check if user already exists
            existing_users = self.firebase_service.query_documents(
                'users',
                filters=[{'field': 'email', 'value': email}]
            )
            
            if existing_users:
                return {'error': 'User with this email already exists'}
            
            # Hash password
            password_hash = self._hash_password(password)
            
            # Create user
            user_id = self.firebase_service.create_user(email, password, f"{first_name} {last_name}")
            
            user_data = {
                'id': user_id,
                'email': email,
                'password_hash': password_hash,
                'first_name': first_name,
                'last_name': last_name,
                'role': role.value,  # Store role value
                'institution_id': institution_id,
                'student_id': student_id,  # Store student ID if provided
                'is_active': True,
                'email_verified': False,
                'created_at': datetime.utcnow().isoformat()
            }
            
            self.firebase_service.create_document('users', user_data, user_id)
            
            # Consume voucher after successful registration
            voucher_service.consume_voucher(voucher_code, user_id)
            
            logger.info(f"User registered successfully: {email}")
            return {
                'user': user_data,
                'message': 'Registration successful'
            }
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return {'error': 'Registration failed'}
    
    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user from JWT token"""
        try:
            payload = jwt.decode(token, 
                             current_app.config['JWT_SECRET_KEY'], 
                             algorithms=['HS256'])
            
            # Check if token is expired
            if datetime.utcnow() > datetime.fromtimestamp(payload['exp']):
                return None
            
            # Get user from database
            user_data = self.firebase_service.get_document('users', payload['user_id'])
            if not user_data or not user_data['is_active']:
                return None
            
            return user_data
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def _hash_password(self, password: str) -> str:
        """Hash password"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def _generate_access_token(self, user_data: Dict[str, Any]) -> str:
        """Generate JWT access token"""
        payload = {
            'user_id': user_data['id'],
            'email': user_data['email'],
            'role': user_data['role'],
            'institution_id': user_data['institution_id'],
            'exp': datetime.utcnow() + timedelta(hours=self.session_timeout_hours),
            'iat': datetime.utcnow()
        }
        # Use stored app context or fallback
        app = self._app if self._app else None
        if app is None:
            raise RuntimeError("Flask app context not available for JWT encoding")
        
        return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256').decode('utf-8')
    
    def _generate_refresh_token(self, user_id: str, remember_me: bool) -> str:
        """Generate refresh token with extended expiry for persistent sessions"""
        expiry_hours = self.session_timeout_hours * 7 if remember_me else self.session_timeout_hours
        
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=expiry_hours),
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        # Use stored app context or fallback
        app = self._app if self._app else None
        if app is None:
            raise RuntimeError("Flask app context not available for JWT encoding")
        
        return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256').decode('utf-8')
    
    def _create_persistent_session(self, user_id: str, device_fingerprint: Optional[str] = None) -> str:
        """Create persistent session record"""
        import secrets
        session_id = secrets.token_hex(16)
        
        session_data = {
            'id': session_id,
            'user_id': user_id,
            'device_fingerprint': device_fingerprint,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(days=self.max_remember_me_days)).isoformat(),
            'last_accessed': datetime.utcnow().isoformat()
        }
        
        self.firebase_service.create_document('persistent_sessions', session_data, session_id)
        return session_id
