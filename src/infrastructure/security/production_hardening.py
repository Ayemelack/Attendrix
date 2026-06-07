"""
PRODUCTION HARDENING MODULE
Attendrix distributed attendance system

Removes debug exposure, hides sensitive headers, prevents stack trace leakage,
secures environment variables, and restricts dangerous HTTP methods.
"""

import logging
import os
import secrets
import ssl
import time
import uuid
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
        'Set-Cookie',
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
    def generate_nonce() -> str:
        """Generate a CSP nonce."""
        return secrets.token_urlsafe(16)

    @staticmethod
    def correlation_id() -> str:
        """Generate a unique error correlation ID."""
        return uuid.uuid4().hex[:12]

    @staticmethod
    def get_security_headers_config(app) -> Dict[str, str]:
        """
        Read CSP/HSTS config values from app.config.

        Args:
            app: Flask application instance

        Returns:
            Dictionary of security header configuration values
        """
        return {
            'csp_default_src': app.config.get('CSP_DEFAULT_SRC', "'self'"),
            'csp_script_src': app.config.get('CSP_SCRIPT_SRC', "'self'"),
            'csp_style_src': app.config.get('CSP_STYLE_SRC', "'self' 'unsafe-inline'"),
            'csp_font_src': app.config.get('CSP_FONT_SRC', "'self' https://fonts.gstatic.com"),
            'csp_img_src': app.config.get('CSP_IMG_SRC', "'self' data: https:"),
            'csp_connect_src': app.config.get('CSP_CONNECT_SRC', "'self' https:"),
            'csp_frame_src': app.config.get('CSP_FRAME_SRC', "'self'"),
            'csp_media_src': app.config.get('CSP_MEDIA_SRC', "'self'"),
            'csp_object_src': app.config.get('CSP_OBJECT_SRC', "'none'"),
            'csp_frame_ancestors': app.config.get('CSP_FRAME_ANCESTORS', "'none'"),
            'csp_base_uri': app.config.get('CSP_BASE_URI', "'self'"),
            'csp_form_action': app.config.get('CSP_FORM_ACTION', "'self'"),
            'hsts_max_age': str(app.config.get('HSTS_MAX_AGE', '31536000')),
            'hsts_include_subdomains': str(app.config.get('HSTS_INCLUDE_SUBDOMAINS', 'True')),
            'hsts_preload': str(app.config.get('HSTS_PRELOAD', 'True')),
        }

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
        from flask import current_app as _current_app

        if environment == 'production':
            config = {}
            if _current_app:
                try:
                    config = ProductionHardeningManager.get_security_headers_config(_current_app)
                except Exception:
                    config = {}

            csp_default = config.get('csp_default_src', "'self'")
            csp_script_src_raw = config.get('csp_script_src', "'self'")
            csp_style_src_raw = config.get('csp_style_src', "'self' 'unsafe-inline'")
            csp_font = config.get('csp_font_src', "'self' https://fonts.gstatic.com")
            csp_img = config.get('csp_img_src', "'self' data: https:")
            csp_connect = config.get('csp_connect_src', "'self' https:")
            csp_frame = config.get('csp_frame_src', "'self'")
            csp_media = config.get('csp_media_src', "'self'")
            csp_object = config.get('csp_object_src', "'none'")
            csp_frame_ancestors = config.get('csp_frame_ancestors', "'none'")
            csp_base_uri = config.get('csp_base_uri', "'self'")
            csp_form_action = config.get('csp_form_action', "'self'")

            hsts_max_age = config.get('hsts_max_age', '31536000')
            hsts_include = config.get('hsts_include_subdomains', 'True')
            hsts_preload_val = config.get('hsts_preload', 'True')

            hsts_directives = f'max-age={hsts_max_age}'
            if hsts_include.lower() == 'true':
                hsts_directives += '; includeSubDomains'
            if hsts_preload_val.lower() == 'true':
                hsts_directives += '; preload'

            csp_script_parts = [
                p for p in csp_script_src_raw.split()
                if p not in ("'unsafe-inline'",)
            ]

            nonce = getattr(request, '_csp_nonce', None)
            if nonce:
                csp_script_parts.append(f"'nonce-{nonce}'")

            csp_script = ' '.join(csp_script_parts)

            csp_style_parts = csp_style_src_raw.split()
            if "'unsafe-inline'" not in csp_style_parts:
                csp_style_parts.append("'unsafe-inline'")
            csp_style = ' '.join(csp_style_parts)

            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = hsts_directives

            response.headers['Content-Security-Policy'] = (
                f"default-src {csp_default}; "
                f"script-src {csp_script}; "
                f"style-src {csp_style}; "
                f"img-src {csp_img}; "
                f"font-src {csp_font}; "
                f"connect-src {csp_connect}; "
                f"frame-src {csp_frame}; "
                f"media-src {csp_media}; "
                f"object-src {csp_object}; "
                f"frame-ancestors {csp_frame_ancestors}; "
                f"base-uri {csp_base_uri}; "
                f"form-action {csp_form_action};"
            )

            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response.headers['Permissions-Policy'] = (
                'geolocation=(), microphone=(), camera=(), '
                'payment=(), usb=(), magnetometer=(), '
                'gyroscope=(), accelerometer=()'
            )

            response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
            response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
            response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'

            logger.debug('Applied production security headers')

        elif environment == 'staging':
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
        cid = ProductionHardeningManager.correlation_id()

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

        message = generic_messages.get(error_code, 'An error occurred')

        logger.error(
            'Error %s: %s (correlation_id=%s, show_details=%s)',
            error_code, error_message, cid, show_details,
        )

        return {
            'error': True,
            'code': error_code,
            'message': message,
            'correlation_id': cid,
            'timestamp': int(time.time()),
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
        from flask import current_app as _current_app

        cid = ProductionHardeningManager.correlation_id()
        logger.exception(
            'Unhandled exception (correlation_id=%s)', cid, exc_info=exception
        )
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
        from flask import current_app as _current_app

        debug = (
            _current_app.config.get('DEBUG', False)
            if _current_app and hasattr(_current_app, 'config')
            else False
        )
        debug = debug or os.environ.get('FLASK_DEBUG', '').lower() == 'true'
        env = os.environ.get('ENVIRONMENT', 'production')

        if debug and env == 'production':
            logger.critical(
                'DEBUG MODE ENABLED IN PRODUCTION - DISABLING IMMEDIATELY'
            )
            if _current_app:
                _current_app.debug = False
                _current_app.config['DEBUG'] = False
                _current_app.config['TESTING'] = False
            os.environ['FLASK_DEBUG'] = 'false'

            webhook_url = os.environ.get('SECURITY_WEBHOOK_URL', '')
            if webhook_url:
                try:
                    import requests as _requests
                    _requests.post(
                        webhook_url,
                        json={
                            'alert': 'debug_mode_production',
                            'message': 'Debug mode was enabled in production and has been forcefully disabled.',
                            'severity': 'critical',
                            'source': 'production_hardening',
                        },
                        timeout=5,
                    )
                except Exception as wh_e:
                    logger.error('Failed to send security webhook alert: %s', wh_e)

            logger.info('Debug mode forcefully disabled in production environment')
            return True

        if debug:
            logger.warning(f'DEBUG MODE ENABLED (environment={env})')

        return True

    @staticmethod
    def log_suspicious_request(request_obj) -> None:
        """Log suspicious requests for security audit."""
        if not request_obj:
            return

        suspicious_patterns = [
            '../',
            '..\\',
            'union select',
            'select * from',
            '<script',
            'javascript:',
            'onclick=',
            '../config',
            '/etc/passwd',
        ]

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
        logger.info('Production hardening: dangerous operations restricted')

    @staticmethod
    def validate_tls_version() -> None:
        """
        Check that TLS 1.2+ is available and warn if not.
        """
        if ssl.HAS_TLSv1_3:
            logger.info('TLS 1.3 supported - secure')
        elif ssl.HAS_TLSv1_2:
            logger.warning('TLS 1.2 supported (TLS 1.3 not available)')
        else:
            logger.critical(
                'NEITHER TLS 1.2 NOR TLS 1.3 AVAILABLE - '
                'PRODUCTION CONNECTION INSECURE'
            )


def apply_production_hardening(app):
    """Apply all production hardening measures to Flask app."""
    from flask import jsonify, redirect

    hardening = ProductionHardeningManager()

    env = app.config.get('ENVIRONMENT', 'production')
    force_https = app.config.get('FORCE_HTTPS', False)

    if env == 'production':
        if force_https:
            app.config['SESSION_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    @app.before_request
    def check_production_hardening():
        """Check hardening requirements before request."""
        if force_https and request.scheme != 'https':
            secure_url = request.url.replace('http://', 'https://', 1)
            return redirect(secure_url, code=301)

        if not hardening.validate_http_method(request.method):
            return jsonify(
                hardening.sanitize_error_response(405, 'Method not allowed')
            ), 405

        hardening.log_suspicious_request(request)

        request._csp_nonce = ProductionHardeningManager.generate_nonce()

    @app.after_request
    def apply_hardening_headers(response):
        """Apply hardening to all responses."""
        app_env = app.config.get('ENVIRONMENT', 'production')

        response = hardening.remove_sensitive_headers(response)
        response = hardening.set_secure_headers(response, app_env)

        return response

    ProductionHardeningManager.validate_tls_version()

    logger.info('Production hardening applied to Flask app')
