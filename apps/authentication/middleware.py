"""
Authentication middleware for Attendrix security
"""
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from rest_framework_simplejwt.exceptions import InvalidToken
from apps.users.models import User
from apps.core.models import SecurityLog, ActivityLog
from apps.authentication.models import UserSession
import logging

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """
    Security middleware for monitoring and protection
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request for security monitoring"""
        
        # Get client information
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check for suspicious patterns
        if self._is_suspicious_request(request, ip_address, user_agent):
            self._log_suspicious_activity(request, ip_address, user_agent)
        
        # Rate limiting check
        if self._is_rate_limited(request, ip_address):
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': 'Too many requests. Please try again later.'
            }, status=429)
        
        # Session validation
        if request.user.is_authenticated:
            if not self._validate_user_session(request):
                logout(request)
                return JsonResponse({
                    'error': 'Session expired',
                    'message': 'Your session has expired. Please login again.'
                }, status=401)
        
        response = self.get_response(request)
        
        # Add security headers
        self._add_security_headers(response)
        
        return response
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    def _is_suspicious_request(self, request, ip_address, user_agent):
        """Check for suspicious request patterns"""
        suspicious_patterns = [
            'sqlmap',
            'nikto',
            'nmap',
            'masscan',
            'dirb',
            'wfuzz',
            'python-requests',
            'curl',
            'wget'
        ]
        
        # Check user agent for suspicious tools
        for pattern in suspicious_patterns:
            if pattern.lower() in user_agent.lower():
                return True
        
        # Check for common attack patterns in URL
        suspicious_urls = [
            '/admin/',
            '/wp-admin/',
            '/phpmyadmin/',
            '/.env',
            '/config.php',
            '/database.php',
            'union select',
            'script alert',
            '<script>',
            'javascript:',
            'eval(',
            'base64_decode'
        ]
        
        request_url = request.get_full_path().lower()
        for pattern in suspicious_urls:
            if pattern in request_url:
                return True
        
        return False
    
    def _log_suspicious_activity(self, request, ip_address, user_agent):
        """Log suspicious activity"""
        SecurityLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            institution=request.user.institution if request.user.is_authenticated else None,
            event_type='suspicious_activity',
            event_description='Suspicious request detected',
            ip_address=ip_address,
            user_agent=user_agent,
            risk_score=60,
            metadata={
                'url': request.get_full_path(),
                'method': request.method,
                'headers': dict(request.headers)
            }
        )
        
        logger.warning(f"Suspicious activity detected from {ip_address}: {request.get_full_path()}")
    
    def _is_rate_limited(self, request, ip_address):
        """Check if request should be rate limited"""
        # Simple in-memory rate limiting
        # In production, use Redis or similar
        
        from django.core.cache import cache
        
        cache_key = f"rate_limit:{ip_address}"
        request_count = cache.get(cache_key, 0)
        
        if request_count >= 100:  # 100 requests per minute
            return True
        
        # Increment counter
        cache.set(cache_key, request_count + 1, 60)  # 1 minute expiry
        return False
    
    def _validate_user_session(self, request):
        """Validate user session"""
        user = request.user
        
        # Check if user is still active
        if not user.is_active:
            return False
        
        # Check if user is locked
        if user.is_account_locked:
            return False
        
        # Check session timeout
        if user.last_active:
            timeout_minutes = getattr(settings, 'SESSION_TIMEOUT_MINUTES', 60)
            if timezone.now() > user.last_active + timezone.timedelta(minutes=timeout_minutes):
                return False
        
        # Update last activity
        user.update_last_active()
        
        return True
    
    def _add_security_headers(self, response):
        """Add security headers to response"""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        if hasattr(settings, 'SECURE_HSTS_SECONDS') and settings.SECURE_HSTS_SECONDS:
            response['Strict-Transport-Security'] = f'max-age={settings.SECURE_HSTS_SECONDS}'


class TenantMiddleware:
    """
    Multi-tenant middleware for institution isolation
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request for tenant isolation"""
        
        # Extract institution from request
        institution = self._get_institution_from_request(request)
        
        if institution:
            # Add institution to request
            request.tenant = institution
            
            # Filter queries by institution
            self._apply_tenant_filtering(request, institution)
        
        response = self.get_response(request)
        
        return response
    
    def _get_institution_from_request(self, request):
        """Extract institution from request"""
        # Try to get institution from JWT token
        if hasattr(request, 'auth') and request.auth:
            user = request.user
            if user and user.is_authenticated and user.institution:
                return user.institution
        
        # Try to get institution from subdomain
        host = request.get_host()
        subdomain = host.split('.')[0] if '.' in host else None
        
        if subdomain:
            from apps.institutions.models import InstitutionDomain
            try:
                domain = InstitutionDomain.objects.get(
                    domain=subdomain,
                    is_active=True
                )
                return domain.institution
            except InstitutionDomain.DoesNotExist:
                pass
        
        # Try to get institution from header
        institution_code = request.META.get('HTTP_X_INSTITUTION_CODE')
        if institution_code:
            from apps.institutions.models import Institution
            try:
                return Institution.objects.get(
                    code=institution_code.upper(),
                    is_active=True
                )
            except Institution.DoesNotExist:
                pass
        
        return None
    
    def _apply_tenant_filtering(self, request, institution):
        """Apply tenant filtering to queries"""
        # This would be implemented using custom query managers
        # For now, we rely on the tenant models to handle filtering
        pass


class AuditMiddleware:
    """
    Audit middleware for comprehensive logging
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request for audit logging"""
        
        # Skip certain requests
        if self._should_skip_logging(request):
            return self.get_response(request)
        
        # Get request information
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Log request
        start_time = timezone.now()
        
        response = self.get_response(request)
        
        # Log response
        duration = (timezone.now() - start_time).total_seconds()
        
        self._log_request_response(request, response, ip_address, user_agent, duration)
        
        return response
    
    def _should_skip_logging(self, request):
        """Check if request should be skipped from logging"""
        skip_paths = [
            '/health/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/robots.txt'
        ]
        
        return any(request.path.startswith(path) for path in skip_paths)
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    def _log_request_response(self, request, response, ip_address, user_agent, duration):
        """Log request and response"""
        user = request.user if request.user.is_authenticated else None
        
        # Only log API requests and important pages
        if request.path.startswith('/api/') or request.path in ['/login/', '/logout/']:
            ActivityLog.objects.create(
                user=user,
                institution=user.institution if user else None,
                action_type='view' if request.method == 'GET' else 'update',
                action_description=f'{request.method} {request.path}',
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                    'duration': duration
                },
                severity='low' if response.status_code < 400 else 'medium'
            )
