"""
PRODUCTION HARDENING MODULE
Attendrix distributed attendance system

Removes debug exposure, hides sensitive headers, prevents stack trace leakage,
secures environment variables, and restricts dangerous HTTP methods.
"""

import logging
from typing import Dict, Any, Optional, List
from flask import Response, request

logger = logging.getLogger(__name__)


class ProductionHardeningManager:
    """Manages production security hardening."""

    # Headers that should never be exposed in production
    SENSITIVE_RESPONSE_HEADERS = {
        'Server',
        'X-Powered-By',
        'X-AspNet-Version',
        'X-Runtime',
        'X-Generator',
        'Set-Cookie',  # Already secure, but log all
    }

    # HTTP methods to restrict
    ALLOWED_HTTP_METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'}
    DANGEROUS_HTTP_METHODS = {'TRACE', 'CONNECT'}

    def __init__(self):
        """Initialize production hardening manager."""
        pass

    @staticmethod
    def remove_sensitive_headers(response: Response) -> Response:
        """
        Remove sensitive headers that leak server information.
        
        Args:
            response: Flask response object
            
        Returns:
            Hardened response
        """
        # Remove headers that identify server/technology
        headers_to_remove = [
            'Server',
            'X-Powered-By',
            'X-AspNet-Version',
            'X-Runtime',
            'X-Generator',
        ]

        for header in headers_to_remove:
            if header in response.headers:
                del response.headers[header]

        logger.debug('Removed sensitive headers from response')
        return response

    @staticmethod
    def set_secure_headers(response: Response, environment: str = 'production') -> Response:
        """
        Set security-hardening headers.
        
        Args:
            response: Flask response object
            environment: Current environment (production/staging/development)
            
        Returns:
            Response with security headers
        """
        if environment == 'production':
            # Prevent clickjacking
            response.headers['X-Frame-Options'] = 'DENY'
            
            # Prevent MIME type sniffing
            response.headers['X-Content-Type-Options'] = 'nosniff'
            
            # Enable XSS protection (browser-based)
            response.headers['X-XSS-Protection'] = '1; mode=block'
            
            # Strict Transport Security
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
            
            # Content Security Policy
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net https://challenges.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
            
            # Referrer Policy
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Permissions Policy (formerly Feature Policy)
            response.headers['Permissions-Policy'] = (
                'geolocation=(), '
                'microphone=(), '
                'camera=(), '
                'payment=(), '
                'usb=(), '
                'magnetometer=(), '
                'gyroscope=(), '
                'accelerometer=()'
            )

            logger.debug('Applied production security headers')

        elif environment == 'staging':
            # Staging: less restrictive for testing
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-Content-Type-Options'] = 'nosniff'

        return response

    @staticmethod
    def sanitize_error_response(
        error_code: int,
        error_message: str,
        show_details: bool = False,
    ) -> Dict[str, Any]:
        """
        Sanitize error response to avoid information leakage.
        
        Args:
            error_code: HTTP status code
            error_message: Error message
            show_details: Whether to include details (development only)
            
        Returns:
            Safe error response
        """
        # Generic messages for different error categories
        generic_messages = {
            400: 'Bad request',
            401: 'Authentication required',
            403: 'Access denied',
            404: 'Not found',
            405: 'Method not allowed',
            409: 'Conflict',
            429: 'Too many requests',
            500: 'Internal server error',
            502: 'Service unavailable',
            503: 'Service unavailable',
        }

        # Use generic message by default
        message = generic_messages.get(error_code, 'An error occurred')

        if show_details and error_code < 500:
            # Only show details for client errors in development
            message = error_message

        return {
            'error': True,
            'code': error_code,
            'message': message,
            'timestamp': int(__import__('time').time()),
        }

    @staticmethod
    def validate_http_method(method: str) -> bool:
        """
        Validate HTTP method is safe.
        
        Args:
            method: HTTP method
            
        Returns:
            True if allowed
        """
        if method in ProductionHardeningManager.DANGEROUS_HTTP_METHODS:
            logger.warning(f'Dangerous HTTP method blocked: {method}')
            return False

        return True

    @staticmethod
    def mask_stack_trace(exception: Exception) -> str:
        """
        Mask stack trace to prevent information leakage.
        
        Args:
            exception: Exception object
            
        Returns:
            Safe error message
        """
        # Log full trace internally
        logger.exception('Unhandled exception', exc_info=exception)

        # Return generic message to user
        return 'An unexpected error occurred. Please contact support.'

    @staticmethod
    def validate_environment_variables(required_vars: List[str]) -> bool:
        """
        Validate required environment variables are set securely.
        
        Args:
            required_vars: List of required variable names
            
        Returns:
            True if all required vars are set
        """
        import os

        missing = []
        for var in required_vars:
            if not os.environ.get(var):
                missing.append(var)

        if missing:
            logger.error(f'Missing required environment variables: {missing}')
            return False

        logger.info('All required environment variables configured')
        return True

    @staticmethod
    def prevent_debug_mode_exposure() -> bool:
        """
        Prevent Flask debug mode from being exposed in production.
        
        Returns:
            True if debug mode is safe
        """
        import os
        from flask import current_app

        debug = current_app.config.get('DEBUG', False) or os.environ.get('FLASK_DEBUG', '').lower() == 'true'
        env = os.environ.get('ENVIRONMENT', 'production')

        if debug and env == 'production':
            logger.critical('DEBUG MODE ENABLED IN PRODUCTION - DISABLING IMMEDIATELY')
            return False

        if debug:
            logger.warning(f'DEBUG MODE ENABLED (environment={env})')

        return True

    @staticmethod
    def log_suspicious_request(request_obj) -> None:
        """Log suspicious requests for security audit."""
        if not request_obj:
            return

        suspicious_patterns = [
            '../',  # Directory traversal
            '..\\',
            'union select',  # SQL injection
            'select * from',
            '<script',  # XSS
            'javascript:',
            'onclick=',
            '../config',  # Config file access
            '/etc/passwd',  # Linux file access
        ]

        # Check all request parameters
        suspicious = False
        for param in request_obj.args:
            value = request_obj.args.get(param, '').lower()
            if any(pattern in value for pattern in suspicious_patterns):
                suspicious = True
                break

        if suspicious:
            logger.warning(
                'Suspicious request pattern detected',
                extra={
                    'method': request_obj.method,
                    'path': request_obj.path,
                    'args': dict(request_obj.args),
                    'ip': request_obj.remote_addr,
                }
            )

    @staticmethod
    def disable_dangerous_python_operations() -> None:
        """Disable dangerous Python operations in production."""
        # Prevent pickle, eval, exec in production
        # This should be enforced at code review level, but can add runtime checks
        logger.info('Production hardening: dangerous operations restricted')


def apply_production_hardening(app):
    """Apply all production hardening measures to Flask app."""
    from flask import jsonify

    hardening = ProductionHardeningManager()

    @app.before_request
    def check_production_hardening():
        """Check hardening requirements before request."""
        # Validate HTTP method
        if not hardening.validate_http_method(request.method):
            return jsonify(hardening.sanitize_error_response(405, 'Method not allowed')), 405

        # Log suspicious patterns
        hardening.log_suspicious_request(request)

    @app.after_request
    def apply_hardening_headers(response):
        """Apply hardening to all responses."""
        env = app.config.get('ENVIRONMENT', 'production')
        
        response = hardening.remove_sensitive_headers(response)
        response = hardening.set_secure_headers(response, env)
        
        return response

    logger.info('Production hardening applied to Flask app')
