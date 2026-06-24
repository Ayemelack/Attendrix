"""
Custom authentication backends for Attendrix
"""
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from apps.core.models import SecurityLog, ActivityLog
from apps.authentication.models import LoginAttempt, UserSession
import hashlib
import json


User = get_user_model()


class AttendrixBackend(BaseBackend):
    """
    Custom authentication backend with security logging
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user with security logging
        """
        if username is None or password is None:
            return None
        
        # Get client information for logging
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_fingerprint = self._generate_device_fingerprint(request)
        geolocation = self._get_geolocation(ip_address)
        
        # Find user by email
        try:
            user = User.objects.get(email=username.lower())
        except User.DoesNotExist:
            self._log_login_attempt(
                None, None, 'login', 'failed', ip_address,
                user_agent, device_fingerprint, geolocation,
                username, 'User not found'
            )
            return None
        
        # Check if account is locked
        if user.is_account_locked:
            self._log_login_attempt(
                user, user.institution, 'login', 'blocked', ip_address,
                user_agent, device_fingerprint, geolocation,
                username, 'Account locked'
            )
            return None
        
        # Check password
        if user.check_password(password):
            # Successful login
            self._log_login_attempt(
                user, user.institution, 'login', 'success', ip_address,
                user_agent, device_fingerprint, geolocation,
                username, ''
            )
            
            # Reset failed login attempts
            user.reset_failed_login()
            
            # Update last login and activity
            user.last_login = timezone.now()
            user.update_last_active()
            user.save(update_fields=['last_login'])
            
            # Create user session
            self._create_user_session(user, request, ip_address, user_agent, device_fingerprint, geolocation)
            
            # Log activity
            ActivityLog.objects.create(
                user=user,
                institution=user.institution,
                action_type='login',
                action_description='User logged in successfully',
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint,
                geolocation=geolocation,
                severity='low'
            )
            
            return user
        else:
            # Failed login
            user.increment_failed_login()
            
            self._log_login_attempt(
                user, user.institution, 'login', 'failed', ip_address,
                user_agent, device_fingerprint, geolocation,
                username, 'Invalid password'
            )
            
            return None
    
    def get_user(self, user_id):
        """
        Retrieve user by ID
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _generate_device_fingerprint(self, request):
        """Generate device fingerprint from request"""
        fingerprint_data = {
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            'accept_encoding': request.META.get('HTTP_ACCEPT_ENCODING', ''),
            'accept': request.META.get('HTTP_ACCEPT', ''),
        }
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]
    
    def _get_geolocation(self, ip_address):
        """Get geolocation data for IP address"""
        # This would integrate with a geolocation service
        # For now, return None
        return None
    
    def _log_login_attempt(self, user, institution, attempt_type, status, ip_address, 
                          user_agent, device_fingerprint, geolocation, username, failure_reason):
        """Log login attempt for security monitoring"""
        LoginAttempt.objects.create(
            user=user,
            institution=institution,
            attempt_type=attempt_type,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            geolocation=geolocation,
            username_or_email=username,
            failure_reason=failure_reason,
            risk_score=self._calculate_risk_score(user, status, ip_address),
            is_suspicious=self._is_suspicious_attempt(user, status, ip_address)
        )
        
        # Log to security log if suspicious
        if status in ['blocked', 'failed'] and user:
            SecurityLog.objects.create(
                user=user,
                institution=institution,
                event_type='failed_login' if status == 'failed' else 'account_locked',
                event_description=failure_reason,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint,
                geolocation=geolocation,
                risk_score=self._calculate_risk_score(user, status, ip_address),
                metadata={
                    'attempt_type': attempt_type,
                    'failure_reason': failure_reason,
                    'username': username
                }
            )
    
    def _calculate_risk_score(self, user, status, ip_address):
        """Calculate risk score for login attempt"""
        risk_score = 0
        
        if status == 'failed':
            risk_score += 30
        elif status == 'blocked':
            risk_score += 50
        
        if user and user.failed_login_attempts > 3:
            risk_score += user.failed_login_attempts * 10
        
        # Add IP-based risk scoring here
        # risk_score += self._get_ip_risk_score(ip_address)
        
        return min(risk_score, 100)
    
    def _is_suspicious_attempt(self, user, status, ip_address):
        """Determine if login attempt is suspicious"""
        if status == 'blocked':
            return True
        
        if user and user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            return True
        
        # Add more suspicious detection logic here
        return False
    
    def _create_user_session(self, user, request, ip_address, user_agent, device_fingerprint, geolocation):
        """Create user session record"""
        # Create authentication session
        UserSession.objects.create(
            user=user,
            session_key=request.session.session_key or '',
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            geolocation=geolocation,
            expires_at=timezone.now() + timezone.timedelta(hours=settings.SESSION_TIMEOUT_MINUTES / 60)
        )


class JWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication with enhanced security
    """
    
    def get_validated_token(self, raw_token):
        """
        Validate JWT token with additional security checks
        """
        try:
            validated_token = super().get_validated_token(raw_token)
            
            # Additional security checks
            user_id = validated_token[api_settings.USER_ID_CLAIM]
            user = User.objects.get(id=user_id)
            
            # Check if user is still active
            if not user.is_active:
                raise InvalidToken('User account is disabled')
            
            # Check if user is locked
            if user.is_account_locked:
                raise InvalidToken('User account is locked')
            
            # Check if token is blacklisted
            from apps.core.models import RefreshToken
            if RefreshToken.objects.filter(
                user=user,
                token=raw_token.decode(),
                is_active=False
            ).exists():
                raise InvalidToken('Token has been revoked')
            
            return validated_token
            
        except Exception as e:
            # Log security event
            SecurityLog.objects.create(
                event_type='unauthorized_access',
                event_description=f'Invalid JWT token: {str(e)}',
                risk_score=70,
                metadata={
                    'token': raw_token.decode()[:50] + '...' if len(raw_token) > 50 else raw_token.decode(),
                    'error': str(e)
                }
            )
            raise


class InstitutionBackend(BaseBackend):
    """
    Institution-specific authentication backend
    """
    
    def authenticate(self, request, institution_code=None, **kwargs):
        """
        Authenticate institution for multi-tenant access
        """
        if institution_code is None:
            return None
        
        try:
            from apps.institutions.models import Institution
            institution = Institution.objects.get(code=institution_code, is_active=True)
            
            if not institution.is_subscription_active:
                return None
            
            return institution
        except Institution.DoesNotExist:
            return None
    
    def get_institution(self, institution_id):
        """Get institution by ID"""
        try:
            from apps.institutions.models import Institution
            return Institution.objects.get(pk=institution_id, is_active=True)
        except Institution.DoesNotExist:
            return None
