import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
import hashlib

from src.domain.entities import User, UserRole

logger = logging.getLogger(__name__)


class PersistentAuthService:
    """Enhanced authentication service with persistent login functionality"""
    
    def __init__(self, firebase_service):
        self.firebase_service = firebase_service
        self.session_timeout_hours = 24  # 24 hours
        self.max_remember_me_days = 30  # 30 days
    
    def authenticate_user_with_remember(self, email: str, password: str, 
                                     remember_me: bool = False, 
                                     device_fingerprint: Optional[str] = None,
                                     ip_address: Optional[str] = None,
                                     user_agent: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Authenticate user with optional persistent login"""
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
            
            # Update last login and device info
            update_data = {
                'last_login': datetime.utcnow().isoformat(),
                'ip_address': ip_address,
                'user_agent': user_agent
            }
            
            if device_fingerprint:
                update_data['device_fingerprint'] = device_fingerprint
            
            self.firebase_service.update_document('users', user_data['id'], update_data)
            
            # Generate tokens
            access_token = self._generate_access_token(user_data)
            refresh_token = self._generate_refresh_token(user_data['id'], remember_me)
            
            # Create persistent session if remember me is checked
            session_id = None
            if remember_me:
                session_id = self._create_persistent_session(user_data['id'], device_fingerprint)
            
            # Log successful login
            self._log_security_event(
                user_data['id'],
                user_data['institution_id'],
                'login_success',
                'User logged in successfully',
                ip_address,
                user_agent
            )
            
            return {
                'user': user_data,
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
    
    def validate_persistent_session(self, session_id: str, device_fingerprint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Validate persistent session"""
        try:
            # Get session from database
            sessions = self.firebase_service.query_documents(
                'persistent_sessions',
                filters=[{'field': 'session_id', 'value': session_id}]
            )
            
            if not sessions:
                return None
            
            session_data = sessions[0]
            
            # Check if session is expired (30 days)
            created_at = datetime.fromisoformat(session_data['created_at'])
            if datetime.utcnow() > created_at + timedelta(days=self.max_remember_me_days):
                return None
            
            # Check device fingerprint if provided
            if device_fingerprint and session_data.get('device_fingerprint') != device_fingerprint:
                return None
            
            # Get user data
            user_data = self.firebase_service.get_document('users', session_data['user_id'])
            if not user_data or not user_data['is_active']:
                return None
            
            return {
                'user': user_data,
                'valid': True,
                'session_id': session_id
            }
            
        except Exception as e:
            logger.error(f"Session validation error: {str(e)}")
            return None
    
    def logout_user(self, session_id: Optional[str] = None) -> bool:
        """Logout user and invalidate persistent sessions"""
        try:
            if session_id:
                # Mark specific session as logged out
                self.firebase_service.update_document('persistent_sessions', session_id, {
                    'logged_out_at': datetime.utcnow().isoformat()
                })
            
            # Invalidate all user's persistent sessions
            if session_id:
                user_sessions = self.firebase_service.query_documents(
                    'persistent_sessions',
                    filters=[
                        {'field': 'user_id', 'value': session_id},
                        {'field': 'logged_out_at', 'value': None}  # Only active sessions
                    ]
                )
                
                for session in user_sessions:
                    self.firebase_service.update_document('persistent_sessions', session['id'], {
                        'logged_out_at': datetime.utcnow().isoformat()
                    })
            
            logger.info("User logged out successfully")
            return True
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        import bcrypt
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def _generate_access_token(self, user_data: Dict[str, Any]) -> str:
        """Generate JWT access token"""
        import jwt
        payload = {
            'user_id': user_data['id'],
            'email': user_data['email'],
            'role': user_data['role'],
            'institution_id': user_data['institution_id'],
            'exp': datetime.utcnow() + timedelta(hours=self.session_timeout_hours),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, 
                       current_app.config['JWT_SECRET_KEY'], 
                       algorithm='HS256')
    
    def _generate_refresh_token(self, user_id: str, remember_me: bool) -> str:
        """Generate refresh token with extended expiry for persistent sessions"""
        import jwt
        expiry_hours = self.session_timeout_hours * 7 if remember_me else self.session_timeout_hours
        
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=expiry_hours),
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        return jwt.encode(payload, 
                       current_app.config['JWT_SECRET_KEY'], 
                       algorithm='HS256')
    
    def _create_persistent_session(self, user_id: str, device_fingerprint: Optional[str] = None) -> str:
        """Create persistent session record"""
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
    
    def _log_security_event(self, user_id: str, institution_id: str, event_type: str, 
                        description: str, ip_address: Optional[str] = None, 
                        user_agent: Optional[str] = None):
        """Log security events"""
        try:
            security_data = {
                'user_id': user_id,
                'institution_id': institution_id,
                'event_type': event_type,
                'description': description,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'created_at': datetime.utcnow().isoformat()
            }
            
            self.firebase_service.create_document('security_logs', security_data)
            
        except Exception as e:
            logger.error(f"Failed to log security event: {str(e)}")
