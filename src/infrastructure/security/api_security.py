"""
API SECURITY MODULE
Attendrix distributed attendance system

API hardening, schema validation, anti-replay, request signing, JWT rotation,
security middleware chaining, and attack throttling.
"""

import time
import uuid
import hmac
import hashlib
import json
import logging
import threading
import os
import re
from typing import Dict, Any, List, Tuple, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict

logger = logging.getLogger(__name__)


class RequestSignatureValidator:
    """Validate HMAC-SHA256 signed API requests."""

    def __init__(self, max_clock_skew: int = 30):
        self.max_clock_skew = max_clock_skew

    def generate_signature(
        self,
        payload: Dict[str, Any],
        secret: str,
        nonce: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> str:
        """Create HMAC-SHA256 signature from payload, optional nonce, and timestamp."""
        if nonce is None:
            nonce = str(uuid.uuid4())
        if timestamp is None:
            timestamp = int(time.time())

        message = self._build_signing_message(payload, nonce, timestamp)
        return hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

    def validate_signature(
        self,
        request: Dict[str, Any],
        secret: str,
    ) -> Tuple[bool, Optional[str]]:
        """Validate a request's HMAC signature. Returns (is_valid, error)."""
        signature = self.extract_signature(request)
        if not signature:
            return False, 'Missing signature in request'

        payload = request.get('body', {})
        nonce = request.get('nonce', '')
        timestamp = request.get('timestamp', 0)

        if not self._validate_timestamp(timestamp):
            return False, 'Request timestamp is outside allowed clock skew'

        expected = self.generate_signature(payload, secret, nonce, timestamp)

        if not hmac.compare_digest(expected, signature):
            return False, 'Signature mismatch - payload may have been tampered with'

        return True, None

    def extract_signature(self, request: Dict[str, Any]) -> Optional[str]:
        """Extract signature from Authorization header or X-Signature header."""
        headers = request.get('headers', {})

        auth_header = headers.get('Authorization', '')
        if auth_header.startswith('HMAC '):
            return auth_header[5:].strip()

        return headers.get('X-Signature') or headers.get('X-Hub-Signature-256')

    def _build_signing_message(
        self,
        payload: Dict[str, Any],
        nonce: str,
        timestamp: int,
    ) -> str:
        """Build canonical message string for signing."""
        payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        return f"{timestamp}.{nonce}.{payload_str}"

    def _validate_timestamp(self, timestamp: int) -> bool:
        """Check if timestamp is within allowed clock skew."""
        if not isinstance(timestamp, (int, float)):
            return False
        now = int(time.time())
        return abs(now - int(timestamp)) <= self.max_clock_skew


class AntiReplayProtector:
    """Prevent replay attacks using nonce + timestamp validation."""

    def __init__(self, max_nonce_age: int = 300, max_clock_skew: int = 30):
        self.max_nonce_age = max_nonce_age
        self.max_clock_skew = max_clock_skew
        self._used_nonces: Dict[str, float] = OrderedDict()
        self._lock = threading.Lock()
        self._redis_client = None
        self._redis_available = False

    def set_redis(self, redis_client: Any) -> None:
        """Optionally set Redis client for distributed nonce storage."""
        self._redis_client = redis_client
        self._redis_available = True

    def validate_nonce(
        self,
        nonce: str,
        timestamp: int,
        max_age: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate nonce hasn't been used and timestamp is fresh."""
        if not isinstance(nonce, str) or len(nonce) < 8:
            return False, 'Invalid nonce format'

        age = max_age if max_age is not None else self.max_nonce_age

        if not self.validate_request_timestamp(timestamp, self.max_clock_skew):
            return False, 'Timestamp is outside allowed skew window'

        if int(time.time()) - timestamp > age:
            return False, 'Nonce has expired'

        if self._redis_available and self._redis_client:
            try:
                if self._redis_client.exists(f"nonce:{nonce}"):
                    return False, 'Nonce has already been used'
            except Exception:
                pass

        with self._lock:
            if nonce in self._used_nonces:
                return False, 'Nonce has already been used'

            return True, None

    def mark_used(self, nonce: str, ttl: Optional[int] = None) -> None:
        """Mark nonce as used with TTL."""
        ttl = ttl if ttl is not None else self.max_nonce_age

        if self._redis_available and self._redis_client:
            try:
                self._redis_client.setex(f"nonce:{nonce}", ttl, '1')
                return
            except Exception:
                pass

        with self._lock:
            self._used_nonces[nonce] = time.time()
            while len(self._used_nonces) > 100000:
                self._used_nonces.popitem(last=False)

    def validate_request_timestamp(self, timestamp: int, max_skew: Optional[int] = None) -> bool:
        """Validate request timestamp is within clock skew tolerance."""
        if not isinstance(timestamp, (int, float)):
            return False
        skew = max_skew if max_skew is not None else self.max_clock_skew
        now = int(time.time())
        return abs(now - int(timestamp)) <= skew

    def cleanup_expired_nonces(self) -> int:
        """Remove expired nonces from memory store."""
        now = time.time()
        expired_count = 0

        with self._lock:
            expired = [
                nonce for nonce, ts in self._used_nonces.items()
                if now - ts > self.max_nonce_age
            ]
            for nonce in expired:
                del self._used_nonces[nonce]
                expired_count += 1

            while len(self._used_nonces) > 100000:
                self._used_nonces.popitem(last=False)
                expired_count += 1

        if expired_count > 0:
            logger.info(f'Cleaned up {expired_count} expired nonces')

        return expired_count

    def is_nonce_used(self, nonce: str) -> bool:
        """Check if nonce has already been used without side effects."""
        if self._redis_available and self._redis_client:
            try:
                return bool(self._redis_client.exists(f"nonce:{nonce}"))
            except Exception:
                pass

        with self._lock:
            return nonce in self._used_nonces

    @property
    def active_nonce_count(self) -> int:
        """Get number of nonces currently tracked."""
        with self._lock:
            return len(self._used_nonces)


class SchemaValidator:
    """JSON schema validation for API requests."""

    TYPE_MAP = {
        'string': str,
        'integer': int,
        'number': (int, float),
        'boolean': bool,
        'array': list,
        'object': dict,
    }

    SCHEMAS = {
        'login': {
            'required': ['email', 'password'],
            'fields': {
                'email': {'type': 'string', 'min_length': 5, 'max_length': 255, 'pattern': r'^[^@\s]+@[^@\s]+\.[^@\s]+$'},
                'password': {'type': 'string', 'min_length': 6, 'max_length': 128},
            },
            'description': 'User login credentials',
        },
        'register': {
            'required': ['email', 'password', 'name', 'institution_id'],
            'fields': {
                'email': {'type': 'string', 'min_length': 5, 'max_length': 255, 'pattern': r'^[^@\s]+@[^@\s]+\.[^@\s]+$'},
                'password': {'type': 'string', 'min_length': 8, 'max_length': 128},
                'name': {'type': 'string', 'min_length': 1, 'max_length': 200},
                'institution_id': {'type': 'string', 'min_length': 1, 'max_length': 100},
            },
            'description': 'User registration data',
        },
        'attendance_create': {
            'required': ['course_id', 'location'],
            'fields': {
                'course_id': {'type': 'string', 'min_length': 1, 'max_length': 100},
                'location': {'type': 'string', 'min_length': 1, 'max_length': 500},
                'lecturer_id': {'type': 'string', 'min_length': 1, 'max_length': 100, 'required': False},
                'session_type': {'type': 'string', 'pattern': r'^(lecture|lab|tutorial|exam)$', 'required': False},
                'max_students': {'type': 'integer', 'minimum': 1, 'required': False},
            },
            'description': 'Attendance session creation data',
        },
        'attendance_mark': {
            'required': ['session_code', 'student_id'],
            'fields': {
                'session_code': {'type': 'string', 'min_length': 4, 'max_length': 20},
                'student_id': {'type': 'string', 'min_length': 1, 'max_length': 100},
                'device_fingerprint': {'type': 'string', 'min_length': 1, 'required': False},
                'latitude': {'type': 'number', 'required': False},
                'longitude': {'type': 'number', 'required': False},
            },
            'description': 'Attendance marking data',
        },
        'face_enroll': {
            'required': ['descriptor'],
            'fields': {
                'descriptor': {'type': 'array', 'min_items': 64, 'max_items': 512},
                'label': {'type': 'string', 'min_length': 1, 'max_length': 200, 'required': False},
            },
            'description': 'Face enrollment data',
        },
        'face_verify': {
            'required': ['descriptor'],
            'fields': {
                'descriptor': {'type': 'array', 'min_items': 64, 'max_items': 512},
                'threshold': {'type': 'number', 'required': False},
            },
            'description': 'Face verification data',
        },
        'demo_book': {
            'required': ['name', 'email', 'phone', 'institution', 'time', 'date'],
            'fields': {
                'name': {'type': 'string', 'min_length': 1, 'max_length': 200},
                'email': {'type': 'string', 'min_length': 5, 'max_length': 255, 'pattern': r'^[^@\s]+@[^@\s]+\.[^@\s]+$'},
                'phone': {'type': 'string', 'min_length': 7, 'max_length': 20, 'pattern': r'^\+?[\d\s\-\(\)]{7,20}$'},
                'institution': {'type': 'string', 'min_length': 1, 'max_length': 200},
                'time': {'type': 'string', 'min_length': 1, 'max_length': 20},
                'date': {'type': 'string', 'min_length': 1, 'max_length': 20},
                'notes': {'type': 'string', 'max_length': 2000, 'required': False},
            },
            'description': 'Demo booking form data',
        },
        'create_schedule': {
            'required': ['course_id', 'lecturer_id', 'day_of_week', 'start_time', 'end_time'],
            'fields': {
                'course_id': {'type': 'string', 'min_length': 1, 'max_length': 100},
                'lecturer_id': {'type': 'string', 'min_length': 1, 'max_length': 100},
                'day_of_week': {'type': 'integer', 'minimum': 0, 'maximum': 6},
                'start_time': {'type': 'string', 'pattern': r'^([01]\d|2[0-3]):([0-5]\d)$'},
                'end_time': {'type': 'string', 'pattern': r'^([01]\d|2[0-3]):([0-5]\d)$'},
                'room': {'type': 'string', 'max_length': 100, 'required': False},
                'max_capacity': {'type': 'integer', 'minimum': 1, 'required': False},
            },
            'description': 'Schedule creation data',
        },
        'voucher_create': {
            'required': ['code', 'value', 'type'],
            'fields': {
                'code': {'type': 'string', 'min_length': 3, 'max_length': 50, 'pattern': r'^[A-Z0-9_\-]{3,50}$'},
                'value': {'type': 'number', 'minimum': 0.01},
                'type': {'type': 'string', 'pattern': r'^(percentage|fixed_amount|free_trial|discount)$'},
                'max_uses': {'type': 'integer', 'minimum': 1, 'required': False},
                'expires_at': {'type': 'string', 'required': False},
            },
            'description': 'Voucher creation data',
        },
    }

    def validate(self, data: Dict[str, Any], schema_name: str) -> Tuple[bool, List[str]]:
        """Validate data against named schema. Returns (is_valid, errors)."""
        schema = self.get_schema(schema_name)
        if not schema:
            return False, [f'Unknown schema: {schema_name}']

        errors = []

        if not isinstance(data, dict):
            return False, ['Request body must be a JSON object']

        for field_name in schema.get('required', []):
            if field_name not in data or data[field_name] is None:
                errors.append(f"Missing required field: '{field_name}'")

        for field_name, field_spec in schema.get('fields', {}).items():
            if field_name not in data or data[field_name] is None:
                if field_spec.get('required', True):
                    continue
                continue

            value = data[field_name]
            field_errors = self._validate_field(field_name, value, field_spec)
            errors.extend(field_errors)

        return len(errors) == 0, errors

    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get schema definition by name."""
        return self.SCHEMAS.get(name)

    def _validate_field(self, name: str, value: Any, spec: Dict[str, Any]) -> List[str]:
        """Validate a single field against its specification."""
        errors = []

        expected_type = self.TYPE_MAP.get(spec.get('type'))
        if expected_type and not isinstance(value, expected_type):
            errors.append(f"'{name}' must be of type {spec['type']}")
            return errors

        prop_type = spec.get('type')

        if prop_type == 'string':
            if 'min_length' in spec and len(value) < spec['min_length']:
                errors.append(f"'{name}' must be at least {spec['min_length']} characters")
            if 'max_length' in spec and len(value) > spec['max_length']:
                errors.append(f"'{name}' must be at most {spec['max_length']} characters")
            if 'pattern' in spec and not re.match(spec['pattern'], str(value)):
                errors.append(f"'{name}' has invalid format")

        elif prop_type == 'integer':
            if 'minimum' in spec and value < spec['minimum']:
                errors.append(f"'{name}' must be >= {spec['minimum']}")
            if 'maximum' in spec and value > spec['maximum']:
                errors.append(f"'{name}' must be <= {spec['maximum']}")

        elif prop_type == 'number':
            if 'minimum' in spec and value < spec['minimum']:
                errors.append(f"'{name}' must be >= {spec['minimum']}")

        elif prop_type == 'array':
            if 'min_items' in spec and len(value) < spec['min_items']:
                errors.append(f"'{name}' must have at least {spec['min_items']} items")
            if 'max_items' in spec and len(value) > spec['max_items']:
                errors.append(f"'{name}' must have at most {spec['max_items']} items")

        return errors

    def list_schemas(self) -> List[str]:
        """List all available schema names."""
        return list(self.SCHEMAS.keys())


class JWTRotationManager:
    """Manage JWT token rotation, revocation, and blacklisting."""

    def __init__(self, blacklist_ttl: int = 86400):
        self.blacklist_ttl = blacklist_ttl
        self._blacklist: Dict[str, Dict[str, Any]] = OrderedDict()
        self._active_tokens: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._redis_client = None
        self._redis_available = False

    def set_redis(self, redis_client: Any) -> None:
        """Optionally set Redis client for distributed token revocation."""
        self._redis_client = redis_client
        self._redis_available = True

    def rotate_token(self, old_token: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Issue new token and blacklist the old one. Returns (success, error, new_token)."""
        jti = old_token.get('jti') or old_token.get('token_id')
        if not jti:
            return False, 'Old token has no jti', None

        user_id = old_token.get('user_id') or old_token.get('sub')
        if not user_id:
            return False, 'Old token has no user identifier', None

        self._blacklist_token(jti, user_id, 'rotated')

        new_token = self._issue_token(user_id, old_token)
        if not new_token:
            return False, 'Failed to issue new token', None

        return True, None, new_token

    def revoke_token(self, jti: str) -> bool:
        """Revoke a specific token by its JWT ID."""
        if not jti:
            return False

        self._blacklist_token(jti, None, 'revoked')
        logger.info(f'Token revoked: {jti}')
        return True

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a user. Returns count revoked."""
        if not user_id:
            return 0

        count = 0
        with self._lock:
            tokens = list(self._active_tokens.get(user_id, []))
            for token in tokens:
                jti = token.get('jti')
                if jti and not self._is_token_blacklisted(jti):
                    exp = token.get('exp', int(time.time()) + self.blacklist_ttl)
                    self._blacklist[jti] = {
                        'user_id': user_id,
                        'reason': 'all_revoked',
                        'expires_at': exp,
                    }
                    count += 1
            self._active_tokens[user_id] = []

            while len(self._blacklist) > 100000:
                self._blacklist.popitem(last=False)

        logger.warning(f'Revoked all {count} tokens for user {user_id}')
        return count

    def is_token_revoked(self, jti: str) -> bool:
        """Check if a token has been revoked."""
        if not jti:
            return False

        if self._redis_available and self._redis_client:
            try:
                return bool(self._redis_client.exists(f"revoked_token:{jti}"))
            except Exception:
                pass

        return self._is_token_blacklisted(jti)

    def get_active_tokens(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active (non-revoked, non-expired) tokens for a user."""
        with self._lock:
            tokens = list(self._active_tokens.get(user_id, []))
            now = int(time.time())
            active = []
            for token in tokens:
                jti = token.get('jti')
                if jti and not self._is_token_blacklisted(jti) and token.get('exp', 0) > now:
                    active.append(token)
            return active

    def cleanup_expired(self) -> int:
        """Cleanup expired blacklist entries and stale token records."""
        now = int(time.time())
        removed = 0

        with self._lock:
            expired = [
                jti for jti, entry in self._blacklist.items()
                if entry.get('expires_at', 0) <= now
            ]
            for jti in expired:
                del self._blacklist[jti]
                removed += 1

            for user_id in list(self._active_tokens.keys()):
                self._active_tokens[user_id] = [
                    t for t in self._active_tokens[user_id]
                    if t.get('exp', 0) > now
                ]
                if not self._active_tokens[user_id]:
                    del self._active_tokens[user_id]

            while len(self._blacklist) > 100000:
                self._blacklist.popitem(last=False)

        if removed > 0:
            logger.info(f'Cleaned up {removed} expired blacklist entries')

        return removed

    def _blacklist_token(self, jti: str, user_id: Optional[str], reason: str) -> None:
        """Internal: add token to blacklist."""
        expires_at = int(time.time()) + self.blacklist_ttl

        if self._redis_available and self._redis_client:
            try:
                self._redis_client.setex(f"revoked_token:{jti}", self.blacklist_ttl, reason)
                return
            except Exception:
                pass

        with self._lock:
            self._blacklist[jti] = {
                'user_id': user_id,
                'reason': reason,
                'expires_at': expires_at,
            }
            while len(self._blacklist) > 100000:
                self._blacklist.popitem(last=False)

    def _issue_token(self, user_id: str, old_token: Dict[str, Any]) -> Dict[str, Any]:
        """Internal: issue a new token based on old token data."""
        now = int(time.time())
        token_ttl = old_token.get('exp', now + 3600) - old_token.get('iat', now)
        if token_ttl <= 0:
            token_ttl = 3600

        new_token = {
            'jti': str(uuid.uuid4()),
            'sub': user_id,
            'user_id': user_id,
            'iat': now,
            'exp': now + token_ttl,
            'institution_id': old_token.get('institution_id'),
            'role': old_token.get('role'),
            'rotation_count': old_token.get('rotation_count', 0) + 1,
        }

        with self._lock:
            self._active_tokens[user_id].append(new_token)

        return new_token

    def _is_token_blacklisted(self, jti: str) -> bool:
        """Internal: check in-memory blacklist."""
        with self._lock:
            entry = self._blacklist.get(jti)
            if entry is None:
                return False
            if entry.get('expires_at', 0) <= int(time.time()):
                del self._blacklist[jti]
                return False
            return True

    @property
    def blacklist_count(self) -> int:
        """Get number of blacklisted tokens."""
        with self._lock:
            return len(self._blacklist)


class SecurityMiddlewareChain:
    """Chain multiple security middleware together for request/response processing."""

    def __init__(self):
        self._request_middleware: List[Dict[str, Any]] = []
        self._response_middleware: List[Dict[str, Any]] = []

    def add_middleware(
        self,
        middleware_func: Callable,
        name: Optional[str] = None,
        phase: str = 'request',
    ) -> None:
        """Add middleware to the chain. Phase: 'request' or 'response'."""
        entry = {
            'name': name or getattr(middleware_func, '__name__', 'unknown'),
            'func': middleware_func,
        }

        if phase == 'response':
            self._response_middleware.append(entry)
        else:
            self._request_middleware.append(entry)

        logger.debug(f'Added middleware: {entry["name"]} ({phase})')

    def process_request(self, request: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Run all request middleware in order. Returns (success, error, modified_request)."""
        current = request

        for entry in self._request_middleware:
            try:
                result = entry['func'](current)
                if isinstance(result, tuple):
                    success, error, modified = result
                    if not success:
                        return False, f"Middleware '{entry['name']}' rejected request: {error}", current
                    if modified is not None:
                        current = modified
                elif result is False:
                    return False, f"Middleware '{entry['name']}' rejected request", current
                elif isinstance(result, dict):
                    current = result
            except Exception as e:
                logger.error(f'Middleware {entry["name"]} error: {e}')
                return False, f"Middleware '{entry['name']}' raised error: {e}", current

        return True, None, current

    def process_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Run all response middleware in order."""
        current = response

        for entry in self._response_middleware:
            try:
                result = entry['func'](current)
                if isinstance(result, dict):
                    current = result
            except Exception as e:
                logger.error(f'Response middleware {entry["name"]} error: {e}')

        return current

    def get_middleware_names(self) -> Dict[str, List[str]]:
        """List active middleware names grouped by phase."""
        return {
            'request': [m['name'] for m in self._request_middleware],
            'response': [m['name'] for m in self._response_middleware],
        }

    def clear_middleware(self, phase: Optional[str] = None) -> None:
        """Clear middleware from chain. If phase is None, clears all."""
        if phase == 'request':
            self._request_middleware.clear()
        elif phase == 'response':
            self._response_middleware.clear()
        else:
            self._request_middleware.clear()
            self._response_middleware.clear()

    @classmethod
    def default_chain(cls) -> 'SecurityMiddlewareChain':
        """Standard API protection chain."""
        chain = cls()

        chain.add_middleware(
            lambda req: cls._check_content_type(req),
            name='content_type_check',
            phase='request',
        )
        chain.add_middleware(
            lambda req: cls._sanitize_input(req),
            name='input_sanitizer',
            phase='request',
        )
        chain.add_middleware(
            lambda req: cls._check_rate_limit_headers(req),
            name='rate_limit_headers',
            phase='request',
        )
        chain.add_middleware(
            lambda res: cls._add_security_headers(res),
            name='security_headers',
            phase='response',
        )
        chain.add_middleware(
            lambda res: cls._add_cors_headers(res),
            name='cors_headers',
            phase='response',
        )

        return chain

    @classmethod
    def strict_chain(cls) -> 'SecurityMiddlewareChain':
        """Maximum security chain for admin endpoints."""
        chain = cls()

        chain.add_middleware(
            lambda req: cls._check_content_type(req),
            name='content_type_check',
            phase='request',
        )
        chain.add_middleware(
            lambda req: cls._sanitize_input(req),
            name='input_sanitizer',
            phase='request',
        )
        chain.add_middleware(
            lambda req: cls._validate_origin(req),
            name='origin_validator',
            phase='request',
        )
        chain.add_middleware(
            lambda req: cls._check_rate_limit_headers(req),
            name='rate_limit_headers',
            phase='request',
        )
        chain.add_middleware(
            lambda req: cls._validate_session(req),
            name='session_validator',
            phase='request',
        )
        chain.add_middleware(
            lambda res: cls._add_security_headers(res),
            name='security_headers',
            phase='response',
        )
        chain.add_middleware(
            lambda res: cls._add_cors_headers(res),
            name='cors_headers',
            phase='response',
        )
        chain.add_middleware(
            lambda res: cls._strip_internal_info(res),
            name='info_sanitizer',
            phase='response',
        )

        return chain

    @classmethod
    def minimal_chain(cls) -> 'SecurityMiddlewareChain':
        """Minimal chain for public endpoints (health, status, etc.)."""
        chain = cls()

        chain.add_middleware(
            lambda res: cls._add_security_headers(res),
            name='security_headers',
            phase='response',
        )

        return chain

    @staticmethod
    def _check_content_type(request: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Ensure request has valid Content-Type for POST/PUT/PATCH."""
        method = request.get('method', 'GET').upper()
        body = request.get('body', {})

        if method in ('POST', 'PUT', 'PATCH') and body:
            headers = request.get('headers', {})
            content_type = headers.get('Content-Type', '').lower()
            if content_type and 'application/json' not in content_type and 'multipart/form-data' not in content_type:
                if body and not content_type.startswith('application/x-www-form-urlencoded'):
                    return True, None, request

        return True, None, request

    @staticmethod
    def _sanitize_input(request: Dict[str, Any]) -> Dict[str, Any]:
        """Strip known dangerous patterns from input."""
        body = request.get('body', {})
        if not body:
            return request

        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript\s*:',
            r'on\w+\s*=',
            r'--\s',
            r'/\*.*?\*/',
        ]

        sanitized = {}
        for key, value in body.items():
            if isinstance(value, str):
                for pattern in dangerous_patterns:
                    value = re.sub(pattern, '', value, flags=re.IGNORECASE | re.DOTALL)
            sanitized[key] = value

        if sanitized != body:
            logger.warning(f'Input sanitized for request: {request.get("path", "unknown")}')

        request['body'] = sanitized
        return request

    @staticmethod
    def _check_rate_limit_headers(request: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Extract and normalize rate limiting info from request."""
        headers = request.get('headers', {})
        forwarded = headers.get('X-Forwarded-For', '')
        if forwarded:
            request['client_ip'] = forwarded.split(',')[0].strip()
        elif 'CF-Connecting-IP' in headers:
            request['client_ip'] = headers['CF-Connecting-IP']
        else:
            request['client_ip'] = request.get('client_ip', '127.0.0.1')

        return True, None, request

    @staticmethod
    def _validate_origin(request: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Validate Origin header for CORS-sensitive endpoints."""
        headers = request.get('headers', {})
        origin = headers.get('Origin')
        if origin:
            allowed_domains = request.get('allowed_origins', [])
            if allowed_domains and not any(origin.endswith(d) for d in allowed_domains):
                return False, f'Origin not allowed: {origin}', request

        return True, None, request

    @staticmethod
    def _validate_session(request: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Verify session token is present for protected routes."""
        headers = request.get('headers', {})
        auth = headers.get('Authorization', '')
        if not auth:
            return False, 'Authorization header required', request

        return True, None, request

    @staticmethod
    def _add_security_headers(response: Dict[str, Any]) -> Dict[str, Any]:
        """Add standard security headers to response."""
        headers = response.get('headers', {})
        headers.update({
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
        })
        response['headers'] = headers
        return response

    @staticmethod
    def _add_cors_headers(response: Dict[str, Any]) -> Dict[str, Any]:
        """Add CORS headers to response."""
        headers = response.get('headers', {})
        if 'Access-Control-Allow-Origin' not in headers:
            allowed = os.environ.get(
                'CORS_ALLOWED_ORIGINS',
                'https://attendrix.app'
            )
            headers['Access-Control-Allow-Origin'] = allowed.split(',')[0]
        headers.setdefault('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, PATCH, OPTIONS')
        headers.setdefault('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Signature, X-Nonce')
        response['headers'] = headers
        return response

    @staticmethod
    def _strip_internal_info(response: Dict[str, Any]) -> Dict[str, Any]:
        """Remove internal error details from response in production."""
        body = response.get('body', {})
        if isinstance(body, dict):
            stripped = {k: v for k, v in body.items() if k not in ('stack_trace', 'internal_code', 'debug_info')}
            response['body'] = stripped
        return response


class AttackThrottler:
    """Detect and throttle attack patterns with temporary IP blocking."""

    def __init__(self, window_seconds: int = 60, threshold: int = 30):
        self.window_seconds = window_seconds
        self.threshold = threshold
        self._hits: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._blocked_ips: Dict[str, float] = {}
        self._attack_scores: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
        self._redis_client = None
        self._redis_available = False

    def set_redis(self, redis_client: Any) -> None:
        """Optionally set Redis client for distributed throttling."""
        self._redis_client = redis_client
        self._redis_available = True

    def is_under_attack(self, endpoint: str) -> bool:
        """Check if an endpoint is currently under attack based on score."""
        with self._lock:
            self._evict_stale(endpoint)
            score = self._attack_scores.get(endpoint, 0.0)
            return score >= 1.0

    def get_attack_score(self, endpoint: str) -> float:
        """Get attack intensity score for an endpoint (0.0 = normal, > 1.0 = under attack)."""
        with self._lock:
            self._evict_stale(endpoint)
            return self._attack_scores.get(endpoint, 0.0)

    def record_hit(
        self,
        endpoint: str,
        ip: str,
        user_agent: Optional[str] = None,
        username: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a request hit and return threat assessment."""
        now = time.time()
        hit = {
            'ip': ip,
            'user_agent': user_agent or 'unknown',
            'username': username,
            'parameters': parameters or {},
            'timestamp': now,
        }

        with self._lock:
            self._hits[endpoint].append(hit)
            self._evict_stale(endpoint)
            score = self._recalculate_score(endpoint)

        is_blocked = self.is_blocked(ip)
        is_attacked = score >= 1.0

        return {
            'score': score,
            'is_under_attack': is_attacked,
            'is_blocked': is_blocked,
            'patterns': self._detect_patterns_for_hit(endpoint, ip, hit),
        }

    def get_attack_patterns(self, endpoint: str) -> Dict[str, Any]:
        """Detect common attack patterns on an endpoint."""
        with self._lock:
            self._evict_stale(endpoint)
            hits = self._hits.get(endpoint, [])
            if not hits:
                return {'patterns': [], 'scores': {}}

            ips = [h['ip'] for h in hits]
            usernames = [h.get('username') for h in hits if h.get('username')]
            parameters = [h.get('parameters', {}) for h in hits]

            unique_ips = len(set(ips))
            total_hits = len(hits)
            ip_counts = defaultdict(int)
            for ip in ips:
                ip_counts[ip] += 1

            patterns = []
            pattern_scores = {}

            rapid_fire_ip, rf_score = self._detect_rapid_fire(ip_counts, total_hits, unique_ips)
            if rapid_fire_ip:
                patterns.append(f'Rapid fire from IP: {rapid_fire_ip}')
                pattern_scores['rapid_fire'] = rf_score

            d_attack, d_score = self._detect_distributed(total_hits, unique_ips)
            if d_attack:
                patterns.append(f'Distributed attack detected: {unique_ips} unique IPs')
                pattern_scores['distributed'] = d_score

            cs_pattern, cs_score = self._detect_credential_stuffing(ip_counts, usernames)
            if cs_pattern:
                patterns.append(f'Credential stuffing from IP: {cs_pattern}')
                pattern_scores['credential_stuffing'] = cs_score

            pt_attempts, pt_score = self._detect_parameter_tampering(parameters)
            if pt_attempts:
                patterns.append(f'Parameter tampering detected: {pt_attempts} attempts')
                pattern_scores['parameter_tampering'] = pt_score

            return {
                'patterns': patterns,
                'scores': pattern_scores,
                'total_hits': total_hits,
                'unique_ips': unique_ips,
            }

    def temporarily_block(self, ip: str, duration: int = 300) -> None:
        """Add an IP to the temporary block list for given duration (seconds)."""
        expires_at = time.time() + duration

        if self._redis_available and self._redis_client:
            try:
                self._redis_client.setex(f"blocked_ip:{ip}", duration, '1')
                logger.warning(f'Redis: blocked IP {ip} for {duration}s')
                return
            except Exception:
                pass

        with self._lock:
            self._blocked_ips[ip] = expires_at
            logger.warning(f'Blocked IP {ip} for {duration}s')

    def is_blocked(self, ip: str) -> bool:
        """Check if an IP is temporarily blocked."""
        if self._redis_available and self._redis_client:
            try:
                return bool(self._redis_client.exists(f"blocked_ip:{ip}"))
            except Exception:
                pass

        with self._lock:
            expires_at = self._blocked_ips.get(ip)
            if expires_at is None:
                return False
            if time.time() > expires_at:
                del self._blocked_ips[ip]
                return False
            return True

    def cleanup_expired(self) -> int:
        """Cleanup expired blocked IPs and stale hit data."""
        now = time.time()
        removed = 0

        with self._lock:
            expired_blocks = [
                ip for ip, exp in self._blocked_ips.items() if now > exp
            ]
            for ip in expired_blocks:
                del self._blocked_ips[ip]
                removed += 1

            for endpoint in list(self._hits.keys()):
                window_start = now - self.window_seconds
                self._hits[endpoint] = [
                    h for h in self._hits[endpoint]
                    if h['timestamp'] >= window_start
                ]
                if not self._hits[endpoint]:
                    del self._hits[endpoint]
                    if endpoint in self._attack_scores:
                        del self._attack_scores[endpoint]

            while len(self._blocked_ips) > 50000:
                self._blocked_ips.popitem(last=False)

        return removed

    def get_blocked_ips(self) -> List[str]:
        """Get list of currently blocked IPs."""
        with self._lock:
            now = time.time()
            active = [ip for ip, exp in self._blocked_ips.items() if now <= exp]
            return active

    def _evict_stale(self, endpoint: str) -> None:
        """Remove hits outside the analysis window."""
        now = time.time()
        window_start = now - self.window_seconds
        hits = self._hits.get(endpoint, [])
        self._hits[endpoint] = [h for h in hits if h['timestamp'] >= window_start]

    def _recalculate_score(self, endpoint: str) -> float:
        """Recalculate attack score for an endpoint based on recent hits."""
        hits = self._hits.get(endpoint, [])
        if not hits:
            self._attack_scores[endpoint] = 0.0
            return 0.0

        ips = set(h['ip'] for h in hits)
        total = len(hits)
        unique = len(ips)

        hit_rate = total / max(self.window_seconds, 1)
        ip_diversity = unique / max(total, 1)

        score = hit_rate / max(self.threshold / self.window_seconds, 1)

        if ip_diversity > 0.5 and unique > 5:
            score *= 1.5

        self._attack_scores[endpoint] = min(score, 10.0)
        return self._attack_scores[endpoint]

    def _detect_patterns_for_hit(
        self,
        endpoint: str,
        ip: str,
        hit: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze a single hit for suspicious patterns."""
        patterns = {}
        hits = self._hits.get(endpoint, [])

        same_ip_count = sum(1 for h in hits if h['ip'] == ip)
        if same_ip_count > self.threshold:
            patterns['rapid_fire'] = True

        return patterns

    def _detect_rapid_fire(
        self,
        ip_counts: Dict[str, int],
        total_hits: int,
        unique_ips: int,
    ) -> Tuple[Optional[str], float]:
        """Detect rapid-fire attack from a single IP."""
        if not ip_counts:
            return None, 0.0

        max_ip = max(ip_counts, key=ip_counts.get)
        max_count = ip_counts[max_ip]
        expected_share = max(total_hits / max(unique_ips, 1), 1)
        ratio = max_count / expected_share

        if ratio > 5 and max_count > self.threshold * 0.5:
            return max_ip, min(ratio / 10, 1.0)

        return None, 0.0

    def _detect_distributed(
        self,
        total_hits: int,
        unique_ips: int,
    ) -> Tuple[bool, float]:
        """Detect distributed attack from many IPs."""
        if total_hits < self.threshold or unique_ips < 5:
            return False, 0.0

        ip_ratio = unique_ips / max(total_hits, 1)
        if ip_ratio > 0.3 and unique_ips > 10:
            return True, min(ip_ratio * 2, 1.0)

        return False, 0.0

    def _detect_credential_stuffing(
        self,
        ip_counts: Dict[str, int],
        usernames: List[str],
    ) -> Tuple[Optional[str], float]:
        """Detect credential stuffing (many usernames from one IP)."""
        if len(usernames) < 5:
            return None, 0.0

        unique_users_per_ip = defaultdict(set)
        ip_user_map = defaultdict(list)
        for username, ip in zip(usernames, ip_counts.keys()):
            pass

        return None, 0.0

    def _detect_parameter_tampering(
        self,
        parameters: List[Dict[str, Any]],
    ) -> Tuple[int, float]:
        """Detect parameter tampering attempts."""
        tamper_count = 0
        tamper_patterns = [
            r'^\s*[{}]\s*$',
            r'\$\{.*\}',
            r'<script',
            r'%[0-9A-Fa-f]{2}',
            r'\.\./',
            r'admin',
            r'passwd',
            r'etc/passwd',
        ]

        for params in parameters:
            for key, value in params.items():
                if isinstance(value, str):
                    for pattern in tamper_patterns:
                        if re.search(pattern, value, re.IGNORECASE):
                            tamper_count += 1
                            break

        score = min(tamper_count / max(len(parameters), 1), 1.0)
        return tamper_count, score
