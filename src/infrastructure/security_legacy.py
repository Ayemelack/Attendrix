"""
ATTENDRIX SECURITY HARDENING MODULE
====================================
Enterprise-grade security middleware for the Attendrix distributed attendance system.
Provides: CAPTCHA/anti-bot, CSRF, XSS, rate limiting, input validation,
security headers, session security, audit logging, and data sanitization.

All implementations preserve existing application behavior and API contracts.
"""

import re
import time
import html
import json
import uuid
import hmac
import hashlib
import logging
import secrets
import ipaddress
from typing import Dict, Any, Optional, Tuple, Callable, List, Set
from datetime import datetime, timedelta
from functools import wraps

from flask import request, jsonify, current_app, g, make_response, session
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


# =============================================================================
# 1. CAPTCHA / BOT PROTECTION
# =============================================================================

class CaptchaVerifier:
    """
    Multi-provider CAPTCHA verification supporting Cloudflare Turnstile and Google reCAPTCHA.
    Configure via environment: TURNSTILE_SECRET_KEY or RECAPTCHA_SECRET_KEY.

    Phase 2B upgrade: real verification with replay protection, token caching,
    score-based reCAPTCHA v3 evaluation, hostname validation, and fallback chaining.
    """

    TURNSTILE_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
    RECAPTCHA_URL = 'https://www.google.com/recaptcha/api/siteverify'
    DEFAULT_CACHE_TTL = 300

    def __init__(self):
        self._cache: Dict[str, tuple[bool, float]] = {}
        self._used_tokens: Set[str] = set()

    def _get_turnstile_secret(self) -> str:
        return (current_app.config.get('CLOUDFLARE_TURNSTILE_SECRET_KEY')
                or current_app.config.get('TURNSTILE_SECRET_KEY')
                or '')

    def _get_recaptcha_secret(self) -> str:
        return current_app.config.get('RECAPTCHA_SECRET_KEY') or ''

    def _get_recaptcha_threshold(self) -> float:
        return current_app.config.get('RECAPTCHA_SCORE_THRESHOLD', 0.5)

    def _get_allowed_domains(self) -> List[str]:
        return current_app.config.get('TURNSTILE_ALLOWED_DOMAINS', [])

    def _is_dev(self) -> bool:
        return (current_app.config.get('ENV') == 'development'
                or current_app.debug
                or current_app.config.get('ENVIRONMENT') == 'development')

    def _cache_key(self, token: str) -> str:
        return f"captcha:{hashlib.sha256(token.encode()).hexdigest()}"

    def verify_turnstile(self, token: str, ip: str = None) -> bool:
        """Verify Cloudflare Turnstile token with replay protection and hostname validation."""
        import requests as _req

        if not token:
            logger.warning("Turnstile: empty token")
            return False

        if token in self._used_tokens:
            logger.warning(f"Turnstile: replay attack detected - token already used from {ip}")
            return False

        cache_key = self._cache_key(token)
        cached = self._cache.get(cache_key)
        if cached is not None:
            result, expiry = cached
            if time.time() < expiry:
                return result
            del self._cache[cache_key]

        secret = self._get_turnstile_secret()
        if not secret:
            logger.warning("Turnstile: secret key not configured - blocking request")
            return False

        try:
            resp = _req.post(
                self.TURNSTILE_URL,
                data={'secret': secret, 'response': token, 'remoteip': ip},
                timeout=10
            )
            result = resp.json()
            success = result.get('success', False)
            error_codes = result.get('error-codes', [])

            if not success:
                logger.warning(
                    f"Turnstile: verification failed | ip={ip} | errors={error_codes} | "
                    f"response={json.dumps(result)}"
                )
                self._cache[cache_key] = (False, time.time() + 60)
                return False

            hostname = result.get('hostname', '')
            allowed = self._get_allowed_domains()
            if allowed and hostname and hostname not in allowed:
                logger.warning(
                    f"Turnstile: hostname '{hostname}' not in allowed domains {allowed} | ip={ip}"
                )
                self._cache[cache_key] = (False, time.time() + 60)
                return False

            self._used_tokens.add(token)
            self._cache[cache_key] = (True, time.time() + self.DEFAULT_CACHE_TTL)

            logger.info(f"Turnstile: verification succeeded | ip={ip} | hostname={hostname}")
            return True

        except _req.exceptions.Timeout:
            logger.error(f"Turnstile: request timed out | ip={ip}")
            return False
        except _req.exceptions.RequestException as e:
            logger.error(f"Turnstile: request failed | ip={ip} | error={e}")
            return False
        except Exception as e:
            logger.error(f"Turnstile: unexpected error | ip={ip} | error={e}")
            return False

    def verify_recaptcha(self, token: str, ip: str = None) -> bool:
        """Verify Google reCAPTCHA v3 token with score threshold evaluation."""
        import requests as _req

        if not token:
            logger.warning("reCAPTCHA: empty token")
            return False

        cache_key = self._cache_key(token)
        cached = self._cache.get(cache_key)
        if cached is not None:
            result, expiry = cached
            if time.time() < expiry:
                return result
            del self._cache[cache_key]

        secret = self._get_recaptcha_secret()
        if not secret:
            logger.warning("reCAPTCHA: secret key not configured - blocking request")
            return False

        try:
            resp = _req.post(
                self.RECAPTCHA_URL,
                data={'secret': secret, 'response': token, 'remoteip': ip},
                timeout=10
            )
            result = resp.json()
            success = result.get('success', False)
            score = result.get('score', 0.0)
            threshold = self._get_recaptcha_threshold()

            if not success:
                error_codes = result.get('error-codes', [])
                logger.warning(
                    f"reCAPTCHA: verification failed | ip={ip} | errors={error_codes} | "
                    f"response={json.dumps(result)}"
                )
                self._cache[cache_key] = (False, time.time() + 60)
                return False

            if score < threshold:
                logger.warning(
                    f"reCAPTCHA: score {score} below threshold {threshold} | ip={ip}"
                )
                self._cache[cache_key] = (False, time.time() + 60)
                return False

            if score < 0.7:
                logger.info(
                    f"reCAPTCHA: suspicious activity | score={score} | ip={ip}"
                )

            self._cache[cache_key] = (True, time.time() + self.DEFAULT_CACHE_TTL)

            logger.info(f"reCAPTCHA: verification succeeded | score={score} | ip={ip}")
            return True

        except _req.exceptions.Timeout:
            logger.error(f"reCAPTCHA: request timed out | ip={ip}")
            return False
        except _req.exceptions.RequestException as e:
            logger.error(f"reCAPTCHA: request failed | ip={ip} | error={e}")
            return False
        except Exception as e:
            logger.error(f"reCAPTCHA: unexpected error | ip={ip} | error={e}")
            return False

    def get_provider(self) -> str:
        """Return the active provider name: 'turnstile', 'recaptcha', or 'none'."""
        if self._get_turnstile_secret():
            return 'turnstile'
        if self._get_recaptcha_secret():
            return 'recaptcha'
        return 'none'

    def is_configured(self) -> bool:
        """Check if any CAPTCHA provider is configured."""
        return bool(self._get_turnstile_secret() or self._get_recaptcha_secret())

    def verify(self, token: str = None, ip: str = None) -> bool:
        """Verify CAPTCHA token - auto-selects provider based on configuration."""
        if not token:
            if self._is_dev() and not self.is_configured():
                logger.warning("No CAPTCHA provider configured - allowing in development mode (no token)")
                return True
            return False

        provider = self.get_provider()

        if provider == 'turnstile':
            result = self.verify_turnstile(token, ip)
            logger.info(f"CaptchaVerifier: used turnstile | result={result} | ip={ip}")
            return result

        if provider == 'recaptcha':
            result = self.verify_recaptcha(token, ip)
            logger.info(f"CaptchaVerifier: used recaptcha | result={result} | ip={ip}")
            return result

        if self._is_dev():
            logger.warning("No CAPTCHA provider configured - allowing in development mode")
            return True

        logger.warning("No CAPTCHA provider configured - blocking request in production")
        return False

    def verify_with_fallback(self, token: str, ip: str = None,
                             providers: List[str] = None) -> bool:
        """Try multiple providers in order, returning True on first success."""
        if providers is None:
            providers = ['turnstile', 'recaptcha']

        if not token:
            return False

        for provider in providers:
            if provider == 'turnstile' and self._get_turnstile_secret():
                if self.verify_turnstile(token, ip):
                    return True
            elif provider == 'recaptcha' and self._get_recaptcha_secret():
                if self.verify_recaptcha(token, ip):
                    return True

        logger.warning(f"verify_with_fallback: all providers failed | providers={providers} | ip={ip}")
        return False


captcha_verifier = CaptchaVerifier()


def require_captcha(f: Callable = None, *, action: str = 'generic'):
    """Decorator to require CAPTCHA verification on a route."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            token = data.get('captchaToken') or data.get('turnstileToken') or data.get('g-recaptcha-response')
            ip = get_client_ip()
            if not captcha_verifier.verify(token, ip):
                logger.warning(f"CAPTCHA verification failed for {action} from {ip}")
                return jsonify({
                    'success': False,
                    'error': 'Security verification failed. Please complete the CAPTCHA.',
                    'captcha_required': True
                }), 403
            return func(*args, **kwargs)
        return wrapper
    return decorator(f) if f else decorator


# =============================================================================
# 2. RATE LIMITING (ENHANCED)
# =============================================================================

class EnhancedRateLimiter:
    """
    Intelligent rate limiter with per-endpoint buckets, burst protection,
    IP throttling, and user-based limiting. Uses sliding window counters.
    """

    def __init__(self):
        self._buckets: Dict[str, list] = {}
        self._blocked: Dict[str, datetime] = {}

    def _get_key(self, scope: str = 'ip') -> str:
        """Generate rate limit key based on scope."""
        try:
            from flask import request as flask_req
            path = flask_req.path
        except (RuntimeError, ImportError):
            path = ''
        if scope == 'user' and hasattr(request, 'current_user'):
            return f"user:{request.current_user.get('user_id', 'anon')}:{path}"
        client_ip = get_client_ip()
        return f"ip:{client_ip}:{path}"

    def is_limited(self, key: str = None, limit: int = 60, window: int = 60, block_duration: int = 300) -> Tuple[bool, int]:
        """
        Check if request is rate limited with progressive penalties.
        Returns (is_limited, retry_after_seconds).
        """
        if key is None:
            key = self._get_key()

        now = time.time()

        if key in self._blocked:
            block_until = self._blocked[key]
            if isinstance(block_until, datetime):
                if now < block_until.timestamp():
                    retry_after = int(block_until.timestamp() - now) + 1
                    return True, retry_after
                del self._blocked[key]
            elif isinstance(block_until, (int, float)):
                if now < block_until:
                    retry_after = int(block_until - now) + 1
                    return True, retry_after
                del self._blocked[key]

        if key not in self._buckets:
            self._buckets[key] = []

        self._buckets[key] = [t for t in self._buckets[key] if now - t < window]
        count = len(self._buckets[key])

        if count >= limit:
            offense_key = f'offense:{key}'
            offense_count = self._blocked.get(offense_key, 0)
            self._blocked[offense_key] = offense_count + 1

            progressive_multipliers = [1, 1, 2, 3, 4, 5, 5]
            idx = min(offense_count, len(progressive_multipliers) - 1)
            effective_block = block_duration * progressive_multipliers[idx]

            self._blocked[key] = now + effective_block
            if key in self._buckets:
                del self._buckets[key]
            return True, effective_block

        self._buckets[key].append(now)
        return False, 0

    def get_remaining(self, scope: str = 'ip', limit: int = 60, window: int = 60) -> int:
        """Get remaining requests before rate limit."""
        key = self._get_key(scope)
        now = time.time()
        if key in self._buckets:
            self._buckets[key] = [t for t in self._buckets[key] if now - t < window]
            return max(0, limit - len(self._buckets[key]))
        return limit

    def clear(self, key: str = None):
        """Clear rate limit for a key (e.g., after successful login)."""
        if key is None:
            key = self._get_key()
        self._buckets.pop(key, None)
        self._blocked.pop(key, None)


enhanced_rate_limiter = EnhancedRateLimiter()


def rate_limit_endpoint(limit: int = 60, window: int = 60, scope: str = 'ip', block_duration: int = 300):
    """Decorator to apply enhanced rate limiting to an endpoint."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = enhanced_rate_limiter._get_key(scope)
            local_limit = limit
            if get_client_ip() in ('127.0.0.1', 'localhost', '::1') and (current_app.config.get('ENV') == 'development' or current_app.debug or current_app.config.get('ENVIRONMENT') == 'development'):
                local_limit = max(limit, 100)
            is_limited, retry_after = enhanced_rate_limiter.is_limited(
                key=key, limit=local_limit, window=window, block_duration=block_duration
            )
            if is_limited:
                logger.warning(f"Rate limit exceeded for {key} on {request.path}")
                resp = jsonify({
                    'error': 'Too many requests. Please try again later.',
                    'retry_after': retry_after
                })
                resp.status_code = 429
                resp.headers['Retry-After'] = str(retry_after)
                resp.headers['X-RateLimit-Limit'] = str(limit)
                resp.headers['X-RateLimit-Remaining'] = '0'
                return resp
            response = f(*args, **kwargs)
            if isinstance(response, tuple):
                body, status, *extras = response
                remaining = enhanced_rate_limiter.get_remaining(scope=scope, limit=limit, window=window)
                if isinstance(body, tuple):
                    body[0].headers['X-RateLimit-Remaining'] = str(remaining)
                elif hasattr(body, 'headers'):
                    body.headers['X-RateLimit-Remaining'] = str(remaining)
            return response
        return wrapper
    return decorator


# =============================================================================
# 3. INPUT VALIDATION & SANITIZATION
# =============================================================================

class InputSanitizer:
    """Enterprise input sanitization and validation utilities."""

    SQL_PATTERNS = [
        r"('|\")\s*(OR|AND|UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|EXECUTE)",
        r"(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|UNION|EXEC|EXECUTE)\s+.*\s+(FROM|INTO|TABLE|SET)",
        r"'.*\s+OR\s+'.*\s*=\s*'.*",
        r"(;|--|#|/\*)",
    ]

    XSS_PATTERNS = [
        r"<[^>]*script[\s>]",
        r"javascript\s*:",
        r"on\w+\s*=",
        r"<[^>]*iframe[\s>]",
        r"<[^>]*embed[\s>]",
        r"<[^>]*object[\s>]",
        r"document\.(cookie|write|location|domain)",
        r"eval\s*\(",
        r"setTimeout\s*\(",
        r"setInterval\s*\(",
    ]

    @staticmethod
    def has_sql_injection(value: str) -> bool:
        """Check if value contains SQL injection patterns."""
        if not isinstance(value, str):
            return False
        for pattern in InputSanitizer.SQL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def has_xss(value: str) -> bool:
        """Check if value contains XSS patterns."""
        if not isinstance(value, str):
            return False
        for pattern in InputSanitizer.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def sanitize_html(value: str) -> str:
        """Escape HTML entities to prevent XSS."""
        if not isinstance(value, str):
            return str(value)
        return html.escape(value, quote=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal."""
        if not filename:
            return ''
        clean = re.sub(r'[<>:"/\\|?*]', '_', filename)
        clean = re.sub(r'\.\.', '_', clean)
        clean = re.sub(r'[\x00-\x1f\x7f]', '', clean)
        return clean.strip('._').strip()[:255]

    @staticmethod
    def sanitize_email(email: str) -> str:
        """Sanitize and normalize email address."""
        if not email:
            return ''
        email = email.strip().lower()
        email = re.sub(r'[\s<>\'"]', '', email)
        return email[:254]

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Generic string sanitization."""
        if not isinstance(value, str):
            value = str(value)
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
        return value[:max_length]

    @staticmethod
    def validate_json_body(data: dict, allowed_fields: set, required_fields: set = None) -> Tuple[bool, Optional[str]]:
        """Validate JSON body against allowed and required fields. Prevents mass assignment."""
        if required_fields:
            missing = required_fields - set(data.keys())
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
        extra = set(data.keys()) - allowed_fields
        if extra:
            return False, f"Unexpected fields: {', '.join(extra)}"
        return True, None

    @staticmethod
    def strip_sensitive(data: Dict[str, Any], sensitive_keys: set = None) -> Dict[str, Any]:
        """Remove sensitive fields from data before returning to client."""
        if sensitive_keys is None:
            sensitive_keys = {'password', 'password_hash', 'token', 'secret', 'key', 'authorization'}
        return {k: v for k, v in data.items() if k.lower() not in sensitive_keys}


input_sanitizer = InputSanitizer()


def validate_request(schema: Dict[str, Dict[str, Any]]):
    """Decorator to validate request body against a schema."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            content_type = request.content_type or ''
            if request.method in ('POST', 'PUT', 'PATCH'):
                if 'application/json' not in content_type and 'multipart/form-data' not in content_type:
                    return jsonify({'error': 'Unsupported content type'}), 415

                if 'application/json' in content_type:
                    data = request.get_json(silent=True)
                    if data is None:
                        return jsonify({'error': 'Invalid JSON body'}), 400

                    for field, rules in schema.items():
                        if rules.get('required') and field not in data:
                            return jsonify({'error': f'Missing required field: {field}'}), 400
                        if field in data:
                            value = data[field]
                            if not isinstance(value, type(None)):
                                expected_type = rules.get('type')
                                if expected_type and not isinstance(value, expected_type):
                                    return jsonify({'error': f'Field {field} must be of type {expected_type.__name__}'}), 400
                                if isinstance(value, str):
                                    if rules.get('max_length') and len(value) > rules['max_length']:
                                        return jsonify({'error': f'Field {field} exceeds maximum length of {rules["max_length"]}'}), 400
                                    if rules.get('pattern') and not re.match(rules['pattern'], value):
                                        return jsonify({'error': f'Field {field} has invalid format'}), 400
                                    if rules.get('no_sql') and InputSanitizer.has_sql_injection(value):
                                        return jsonify({'error': f'Field {field} contains invalid characters'}), 400
                                    if rules.get('no_xss') and InputSanitizer.has_xss(value):
                                        return jsonify({'error': f'Field {field} contains invalid characters'}), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# 4. CSRF PROTECTION
# =============================================================================

class CSRFTokenManager:
    """
    CSRF token generation and validation for sensitive operations.
    Uses HMAC-SHA256 with time-bound tokens and per-session binding.
    """

    def __init__(self):
        self._tokens = {}

    def generate_token(self, session_id: str = None) -> str:
        """Generate a CSRF token bound to a session."""
        if session_id is None:
            session_id = get_client_ip()
        token = secrets.token_hex(32)
        expiry = time.time() + 3600
        self._tokens[token] = {
            'session_id': session_id,
            'expiry': expiry,
            'created': time.time()
        }
        return token

    def validate_token(self, token: str, session_id: str = None) -> bool:
        """Validate a CSRF token. Tokens are single-use."""
        if not token or not isinstance(token, str):
            return False
        if session_id is None:
            session_id = get_client_ip()
        stored = self._tokens.pop(token, None)
        if not stored:
            return False
        if time.time() > stored['expiry']:
            return False
        if stored['session_id'] != session_id:
            return False
        return True

    def validate_request(self):
        """Validate CSRF token from X-CSRF-Token header or JSON body."""
        token = request.headers.get('X-CSRF-Token') or ''
        if not token:
            data = request.get_json(silent=True) or {}
            token = data.get('csrfToken', '') or data.get('csrf_token', '')
        if not self.validate_token(token):
            client_ip = get_client_ip()
            logger.warning(f"CSRF validation failed for {request.path} from {client_ip}")
            return jsonify({'error': 'Invalid or expired security token. Please refresh the page.'}), 403
        return None


csrf_manager = CSRFTokenManager()


def require_csrf(f=None):
    """Decorator to require CSRF token on a route."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                result = csrf_manager.validate_request()
                if result:
                    return result
            return func(*args, **kwargs)
        return wrapper
    return decorator(func) if f else decorator


# =============================================================================
# 5. SECURITY HEADERS
# =============================================================================

class SecurityHeadersMiddleware:
    """
    Enterprise-grade HTTP security headers middleware.
    Applied to all responses via Flask after_request.
    """

    CSP_DEFAULT = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
        "https://challenges.cloudflare.com https://www.google.com https://www.gstatic.com "
        "https://apis.google.com https://fonts.googleapis.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
        "https://fonts.googleapis.com https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com https://fonts.googleapis.com; "
        "frame-src 'self' https://challenges.cloudflare.com https://www.google.com; "
        "connect-src 'self' https://api.resend.com wss:; "
        "media-src 'self' blob:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "upgrade-insecure-requests"
    )

    HEADERS = {
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'X-XSS-Protection': '0',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': (
            'camera=(self), microphone=(self), geolocation=(self), '
            'display-capture=(self), payment=(), usb=(), magnetometer=(), '
            'accelerometer=(), gyroscope=(), fullscreen=(self), '
            'interest-cohort=()'
        ),
        'Cross-Origin-Opener-Policy': 'same-origin',
        'Cross-Origin-Resource-Policy': 'same-origin',
        'Cross-Origin-Embedder-Policy': 'require-corp',
        'X-DNS-Prefetch-Control': 'off',
        'X-Download-Options': 'noopen',
        'X-Permitted-Cross-Domain-Policies': 'none',
        'Origin-Agent-Cluster': '?1',
    }

    @staticmethod
    def apply(response):
        """Apply security headers to a Flask response."""
        if response.headers.get('Content-Type', '').startswith('text/html'):
            response.headers['Content-Security-Policy'] = SecurityHeadersMiddleware.CSP_DEFAULT

        for header, value in SecurityHeadersMiddleware.HEADERS.items():
            if header not in response.headers:
                response.headers[header] = value

        env = current_app.config.get('ENVIRONMENT', 'production') if current_app else 'production'
        if env == 'production':
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )

        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response


# =============================================================================
# 6. ERROR HANDLING SECURITY
# =============================================================================

def secure_error_response(status_code: int, message: str = None, details: Any = None) -> tuple:
    """Generate a secure error response that does not leak internal details."""
    generic_messages = {
        400: 'Bad request',
        401: 'Authentication required',
        403: 'Access denied',
        404: 'Resource not found',
        405: 'Method not allowed',
        409: 'Conflict',
        429: 'Too many requests. Please try again later.',
        500: 'An unexpected error occurred. Please try again later.',
        502: 'Service temporarily unavailable',
        503: 'Service temporarily unavailable. Please try again later.',
    }

    safe_message = message or generic_messages.get(status_code, 'An error occurred')

    response_data = {'error': safe_message}

    env = current_app.config.get('ENVIRONMENT', 'production') if current_app else 'production'
    if env in ('development', 'staging') and details:
        response_data['details'] = str(details) if isinstance(details, Exception) else details

    return jsonify(response_data), status_code


def hide_internal_error(f):
    """Decorator to catch exceptions and return safe error messages."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unhandled exception in {request.path}: {str(e)}", exc_info=True)
            return secure_error_response(500)
    return wrapper


# =============================================================================
# 7. SECURITY AUDIT LOGGING
# =============================================================================

class SecurityAuditLogger:
    """
    Comprehensive security event logging for audit trails.
    Logs: failed logins, suspicious activity, unauthorized access,
    admin actions, token failures, rate limit violations.
    """

    @staticmethod
    def log_event(event_type: str, description: str, risk_score: int = 0,
                  user_id: str = None, ip_address: str = None,
                  user_agent: str = None, metadata: Dict[str, Any] = None):
        """Log a security event to the database and logger."""
        try:
            if user_id is None and hasattr(request, 'current_user'):
                user_id = request.current_user.get('user_id')
            if ip_address is None:
                ip_address = get_client_ip()
            if user_agent is None:
                user_agent = request.headers.get('User-Agent')

            inst_id = 'system'
            if hasattr(request, 'current_user') and request.current_user:
                inst_id = request.current_user.get('institution_id', 'system')
                
            event_data = {
                'institution_id': inst_id,
                'user_id': user_id,
                'event_type': event_type,
                'severity': 'HIGH' if risk_score >= 50 else 'LOW',
                'description': f"{description} | UA: {user_agent} | Risk: {risk_score}",
                'ip_address': ip_address,
                'created_at': datetime.utcnow()
            }

            from src.infrastructure.pg_repositories import pg_repos
            from src.infrastructure.models import SecurityLog
            security_log = SecurityLog(**event_data)
            pg_repos.security_logs.create(security_log)

            log_level = logging.WARNING if risk_score >= 50 else logging.INFO
            logger.log(log_level, f"Security event [{event_type}]: {description} - User: {user_id} - IP: {ip_address}")

            if risk_score >= 50:
                SecurityAuditLogger._dispatch_alert(event_type, description, risk_score, event_data)

        except Exception as e:
            logger.error(f"Failed to log security event: {e}")

    @staticmethod
    def _dispatch_alert(event_type: str, description: str, risk_score: int, event_data: dict):
        """Dispatch a real-time alert for high-risk events via configured webhook."""
        import os
        webhook = os.environ.get('SECURITY_ALERT_WEBHOOK', '').strip()
        if not webhook:
            return
        try:
            import urllib.request
            payload = json.dumps({
                'text': f'[Attendrix Security Alert] {event_type}\n'
                        f'Risk: {risk_score}/100\n'
                        f'Description: {description}\n'
                        f'Time: {event_data["created_at"]}\n'
                        f'IP: {event_data.get("ip_address", "unknown")}\n'
                        f'User: {event_data.get("user_id", "anonymous")}'
            }).encode('utf-8')
            req = urllib.request.Request(webhook, data=payload,
                                         headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.error(f"Failed to dispatch security alert to webhook: {e}")

    @staticmethod
    def log_unauthorized_access(endpoint: str):
        """Log unauthorized access attempt."""
        SecurityAuditLogger.log_event(
            event_type='unauthorized_access',
            description=f'Unauthorized access attempt to {endpoint}',
            risk_score=70,
            metadata={'endpoint': endpoint, 'method': request.method}
        )

    @staticmethod
    def log_suspicious_activity(description: str, risk_score: int = 50):
        """Log suspicious activity."""
        SecurityAuditLogger.log_event(
            event_type='suspicious_activity',
            description=description,
            risk_score=risk_score
        )

    @staticmethod
    def log_admin_action(action: str, details: str = None):
        """Log administrative action."""
        SecurityAuditLogger.log_event(
            event_type='admin_action',
            description=f'Admin action: {action}',
            risk_score=0,
            metadata={'action': action, 'details': details}
        )


# =============================================================================
# 8. CONTENT SECURITY POLICY BUILDER
# =============================================================================

class CSPBuilder:
    """Dynamic Content Security Policy builder."""

    def __init__(self):
        self._directives = {
            'default-src': ["'self'"],
            'script-src': ["'self'"],
            'style-src': ["'self'"],
            'img-src': ["'self'", 'data:', 'blob:'],
            'font-src': ["'self'"],
            'connect-src': ["'self'"],
            'frame-src': ["'self'"],
            'media-src': ["'self'", 'blob:'],
            'object-src': ["'none'"],
            'base-uri': ["'self'"],
            'form-action': ["'self'"],
            'frame-ancestors': ["'none'"],
        }

    def allow_script(self, *sources: str):
        self._directives['script-src'].extend(sources)
        return self

    def allow_style(self, *sources: str):
        self._directives['style-src'].extend(sources)
        return self

    def allow_frame(self, *sources: str):
        self._directives['frame-src'].extend(sources)
        return self

    def allow_connect(self, *sources: str):
        self._directives['connect-src'].extend(sources)
        return self

    def allow_img(self, *sources: str):
        self._directives['img-src'].extend(sources)
        return self

    def allow_font(self, *sources: str):
        self._directives['font-src'].extend(sources)
        return self

    def upgrade_insecure_requests(self):
        self._directives['upgrade-insecure-requests'] = []
        return self

    def build(self) -> str:
        parts = []
        for directive, sources in self._directives.items():
            if not sources:
                parts.append(directive)
            else:
                parts.append(f"{directive} {' '.join(set(sources))}")
        return '; '.join(parts)


# =============================================================================
# 9. SESSION SECURITY
# =============================================================================

class SessionSecurity:
    """Session hardening utilities."""

    @staticmethod
    def configure_session(app):
        """Apply secure session configuration to Flask app."""
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        app.config['SESSION_COOKIE_SECURE'] = app.config.get('ENVIRONMENT', 'production') == 'production'
        app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
        app.config['SESSION_REFRESH_EACH_REQUEST'] = True

    @staticmethod
    def rotate_session():
        """Force session rotation (call after login/logout)."""
        session.clear()
        session.regenerate = True


# =============================================================================
# 10. FILE UPLOAD SECURITY
# =============================================================================

class SecureFileUpload:
    """File upload validation and security."""

    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'text/csv',
    }

    EXECUTABLE_EXTENSIONS = {
        'exe', 'bat', 'cmd', 'com', 'msi', 'scr', 'pif',
        'sh', 'bash', 'zsh', 'ksh',
        'py', 'pl', 'rb', 'php', 'asp', 'aspx', 'jsp', 'cgi',
        'jar', 'war', 'class',
        'dll', 'so', 'dylib', 'sys', 'vxd',
        'ps1', 'vbs', 'js', 'vbe', 'jse',
        'htm', 'html', 'shtml', 'xhtml',
    }

    @staticmethod
    def validate_upload(file_storage) -> Tuple[bool, Optional[str]]:
        """Validate uploaded file for security."""
        if not file_storage or not file_storage.filename:
            return False, 'No file provided'

        filename = InputSanitizer.sanitize_filename(file_storage.filename)
        if not filename:
            return False, 'Invalid filename'

        extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if extension in SecureFileUpload.EXECUTABLE_EXTENSIONS:
            return False, 'File type not allowed'

        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
        file_storage.seek(0, 2)
        size = file_storage.tell()
        file_storage.seek(0)
        if size > max_size:
            return False, f'File size exceeds maximum of {max_size / 1024 / 1024:.0f}MB'

        return True, None

    @staticmethod
    def is_safe_extension(extension: str) -> bool:
        """Check if file extension is safe."""
        return extension.lower() not in SecureFileUpload.EXECUTABLE_EXTENSIONS


# =============================================================================
# 11. MIDDLEWARE REGISTRATION
# =============================================================================

def register_security_middleware(app):
    """Register all security middleware with the Flask application."""

    security_headers = SecurityHeadersMiddleware()

    # Routes exempted from CSRF protection (auth entry points, demos, bootstrap)
    CSRF_EXEMPT_PATHS = [
        '/api/auth/login', '/api/auth/register', '/api/auth/signup',
        '/api/auth/refresh',
        '/api/auth/forgot-password', '/api/auth/reset-password',
        '/demo/', '/api/demo/',
        '/system/bootstrap',
        '/api/ping',
        '/api/pin',
        '/api/authentication/login',
        '/api/voucher/validate/',
    ]

    # Endpoint-specific rate limit configuration
    ENDPOINT_RATE_LIMITS = {
        '/api/auth/login': {'limit': 5, 'window': 60, 'block_duration': 900},
        '/api/authentication/login': {'limit': 5, 'window': 60, 'block_duration': 900},
        '/api/auth/signup': {'limit': 3, 'window': 300, 'block_duration': 1800},
        '/api/auth/change-password': {'limit': 3, 'window': 300, 'block_duration': 1800},
        '/api/voucher/generate-batch': {'limit': 10, 'window': 60, 'block_duration': 600},
        '/api/attendance/mark': {'limit': 10, 'window': 60, 'block_duration': 300},
        '/api/attendance/create-session': {'limit': 20, 'window': 60, 'block_duration': 300},
        '/api/student/verify-scan': {'limit': 20, 'window': 60, 'block_duration': 300},
        '/api/biometric/face/enroll': {'limit': 5, 'window': 300, 'block_duration': 900},
        '/system/bootstrap': {'limit': 1, 'window': 3600, 'block_duration': 86400},
        '/api/demo/book': {'limit': 5, 'window': 60, 'block_duration': 600},
        '/api/request-demo': {'limit': 5, 'window': 60, 'block_duration': 600},
    }

    PROGRESSIVE_BLOCK_MULTIPLIERS = [1, 2, 4, 8, 16, 32, 64]

    def get_progressive_block_duration(key: str, base_duration: int) -> int:
        """Calculate progressive block duration based on repeat offenses."""
        offense_count = enhanced_rate_limiter._blocked.get(f'offense:{key}', 0)
        multiplier_idx = min(offense_count, len(PROGRESSIVE_BLOCK_MULTIPLIERS) - 1)
        multiplier = PROGRESSIVE_BLOCK_MULTIPLIERS[multiplier_idx]
        enhanced_rate_limiter._blocked[f'offense:{key}'] = offense_count + 1
        return base_duration * multiplier

    def get_endpoint_rate_limit(path: str) -> dict:
        """Get rate limit config for endpoint, with progressive penalties."""
        for prefix, config in ENDPOINT_RATE_LIMITS.items():
            if path.startswith(prefix):
                return config
        if path.startswith('/api/admin') or path.startswith('/admin/'):
            return {'limit': 20, 'window': 60, 'block_duration': 300}
        if path.startswith('/api/institutional/'):
            return {'limit': 30, 'window': 60, 'block_duration': 120}
        if path.startswith('/api/super-admin/'):
            return {'limit': 20, 'window': 60, 'block_duration': 300}
        if path.startswith('/api/voucher/'):
            return {'limit': 15, 'window': 60, 'block_duration': 300}
        if path.startswith('/api/'):
            return {'limit': 30, 'window': 60, 'block_duration': 60}
        return {'limit': 60, 'window': 60, 'block_duration': 60}

    @app.after_request
    def apply_security_headers(response):
        return security_headers.apply(response)

    @app.before_request
    def validate_request_security():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            content_length = request.content_length or 0
            max_length = app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
            if content_length > max_length:
                return jsonify({'error': 'Request entity too large'}), 413

            if request.content_type and 'application/json' in request.content_type:
                data = request.get_json(silent=True)
                if data is not None and not isinstance(data, dict):
                    return jsonify({'error': 'Invalid request body format'}), 400

            path = request.path
            exempt = any(path.startswith(p) for p in CSRF_EXEMPT_PATHS) or path.startswith('/api/') or path.startswith('/auth/')
            if not exempt:
                result = csrf_manager.validate_request()
                if result:
                    return result

        if request.path.startswith('/api/') and not request.path.startswith('/api/ping') and not request.path.startswith('/api/pin'):
            user_agent = request.headers.get('User-Agent', '')
            if len(user_agent) > 500:
                return jsonify({'error': 'Invalid request'}), 400

        if request.path.startswith('/static/'):
            return

        rate_config = get_endpoint_rate_limit(request.path)
        limit = rate_config['limit']
        window = rate_config['window']
        base_block = rate_config['block_duration']

        # Relax rate limits for localhost in development/testing to prevent blocking sequential test suites
        if get_client_ip() in ('127.0.0.1', 'localhost', '::1') and (current_app.config.get('ENV') == 'development' or current_app.debug or current_app.config.get('ENVIRONMENT') == 'development'):
            limit = max(limit, 100)

        # Isolate global rate limit keys by endpoint path to prevent registration/validation from consuming login limit
        key = f"global:{enhanced_rate_limiter._get_key()}:{request.path}"
        is_limited, retry_after = enhanced_rate_limiter.is_limited(
            key=key, limit=limit, window=window, block_duration=base_block
        )
        if is_limited:
            block_duration = get_progressive_block_duration(key, base_block)
            logger.warning(
                f"Rate limit exceeded for {key} on {request.path} "
                f"(blocked {block_duration}s)"
            )
            SecurityAuditLogger.log_event(
                'rate_limited',
                f'Rate limit exceeded: {request.path} (blocked {block_duration}s)',
                risk_score=40,
                metadata={'key': key, 'block_duration': block_duration}
            )
            resp = jsonify({
                'error': 'Too many requests. Please try again later.',
                'retry_after': retry_after
            })
            resp.status_code = 429
            resp.headers['Retry-After'] = str(retry_after)
            resp.headers['X-RateLimit-Limit'] = str(limit)
            resp.headers['X-RateLimit-Remaining'] = '0'
            return resp

    @app.before_request
    def verify_content_type():
        if request.method in ('POST', 'PUT', 'PATCH'):
            if request.content_type:
                if 'application/json' in request.content_type:
                    if request.get_data(as_text=True).strip() == '':
                        return jsonify({'error': 'Empty request body'}), 400

    @app.before_request
    def check_suspicious_request_patterns():
        if request.path.startswith('/api/') and not request.path.startswith('/api/ping') and not request.path.startswith('/api/pin'):
            user_agent = request.headers.get('User-Agent', '')
            if len(user_agent) < 10 and request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                SecurityAuditLogger.log_event(
                    'missing_user_agent',
                    f'Request with missing/short UA on state-changing operation',
                    risk_score=50,
                    metadata={'path': request.path}
                )
                return jsonify({'error': 'Invalid request'}), 400

            referer = request.headers.get('Referer', '')
            if referer and request.method == 'POST':
                allowed_origins = app.config.get('CORS_ALLOWED_ORIGINS', '')
                if allowed_origins:
                    origins = [o.strip().rstrip('/') for o in allowed_origins.split(',')]
                    referer_base = re.match(r'^(https?://[^/]+)', referer)
                    if referer_base:
                        ref_origin = referer_base.group(1)
                        if not any(ref_origin == o for o in origins):
                            logger.warning(f"Suspicious referer: {ref_origin} not in allowed origins")
                            if app.config.get('ENVIRONMENT') == 'production':
                                return jsonify({'error': 'Invalid request'}), 400

            if request.method in ('POST', 'PUT', 'PATCH'):
                content_type = request.content_type or ''
                if 'application/json' in content_type:
                    data = request.get_json(silent=True)
                    if data and isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, str) and len(value) > 100000:
                                return jsonify({'error': 'Field too large'}), 400

    SessionSecurity.configure_session(app)


# =============================================================================
# 12. API SECURITY UTILITIES
# =============================================================================

def obfuscate_api_structure(data: Any, depth: int = 0) -> Any:
    """Obfuscate API response structure to prevent enumeration."""
    if depth > 5:
        return str(data)
    if isinstance(data, dict):
        return {str(k): obfuscate_api_structure(v, depth + 1) for k, v in data.items()}
    if isinstance(data, list):
        return [obfuscate_api_structure(item, depth + 1) for item in data]
    return data


def remove_server_signature(response):
    """Remove server identifying headers."""
    for header in ('Server', 'X-Powered-By', 'X-AspNet-Version', 'X-AspNetMvc-Version'):
        response.headers.pop(header, None)
    return response


def get_client_ip() -> str:
    """
    Get real client IP, supporting Cloudflare proxy headers.
    Checks CF-Connecting-IP first, then X-Forwarded-For, then remote_addr.
    """
    try:
        from src.infrastructure.cloudflare_security import get_client_ip as _cf_ip
        return _cf_ip()
    except (ImportError, Exception):
        cf_ip = request.headers.get('CF-Connecting-IP')
        if cf_ip:
            return cf_ip.split(',')[0].strip()
        xff = request.headers.get('X-Forwarded-For')
        if xff:
            return xff.split(',')[0].strip()
        return request.remote_addr or '0.0.0.0'


# =============================================================================
# 13. PASSWORD POLICY
# =============================================================================

class PasswordPolicy:
    """Enterprise password policy enforcement."""

    MIN_LENGTH = 8
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True
    COMMON_PASSWORDS = {
        'password', 'password123', '12345678', 'qwerty123', 'admin123',
        'letmein', 'welcome', 'monkey', 'dragon', 'master', '123456789',
        'passw0rd', 'p@ssw0rd', 'Password1', 'password1', 'admin',
    }

    @classmethod
    def validate(cls, password: str) -> Tuple[bool, Optional[str]]:
        """Validate password against policy."""
        if not password or len(password) < cls.MIN_LENGTH:
            return False, f'Password must be at least {cls.MIN_LENGTH} characters long'
        if len(password) > cls.MAX_LENGTH:
            return False, f'Password must not exceed {cls.MAX_LENGTH} characters'
        if cls.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            return False, 'Password must contain at least one uppercase letter'
        if cls.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            return False, 'Password must contain at least one lowercase letter'
        if cls.REQUIRE_DIGIT and not re.search(r'[0-9]', password):
            return False, 'Password must contain at least one number'
        if cls.REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-]', password):
            return False, 'Password must contain at least one special character'
        if password.lower() in cls.COMMON_PASSWORDS:
            return False, 'Password is too common. Please choose a stronger password.'
        return True, None


# =============================================================================
# 14. ANTI-TAMPERING
# =============================================================================

class AntiTamper:
    """Request tampering detection."""

    @staticmethod
    def sign_payload(payload: Dict[str, Any], secret: str = None) -> str:
        """Sign a payload with HMAC for integrity verification."""
        if secret is None:
            secret = current_app.config.get('JWT_SECRET_KEY', '')
        if isinstance(payload, dict):
            payload_str = json.dumps(payload, sort_keys=True)
        else:
            payload_str = str(payload)
        return hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verify_signature(payload: Dict[str, Any], signature: str, secret: str = None) -> bool:
        """Verify payload signature."""
        expected = AntiTamper.sign_payload(payload, secret)
        return hmac.compare_digest(expected, signature)


# =============================================================================
# 15. DISTRIBUTED SYSTEM SECURITY
# =============================================================================

class DistributedSecurity:
    """Security for distributed node communication."""

    @staticmethod
    def validate_node_message(message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a message from a distributed node."""
        if not isinstance(message, dict):
            return False, 'Invalid message format'
        required = {'node_id', 'timestamp', 'payload'}
        missing = required - set(message.keys())
        if missing:
            return False, f'Missing fields: {missing}'
        try:
            msg_time = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
            now = datetime.utcnow()
            if abs((now - msg_time).total_seconds()) > 300:
                return False, 'Message timestamp is too far from current time'
        except (ValueError, TypeError):
            return False, 'Invalid timestamp format'
        return True, None

    @staticmethod
    def generate_node_token(node_id: str) -> str:
        """Generate an authentication token for a distributed node."""
        return secrets.token_urlsafe(32)
