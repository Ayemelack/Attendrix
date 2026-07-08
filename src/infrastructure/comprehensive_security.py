"""
ATTENDRIX COMPREHENSIVE SECURITY MODULE
========================================
Enterprise-grade security implementing 16 security domains:
1.  Strict Backend Authorization
2.  Route Protection
3.  Multi-Tenant Isolation
4.  Firebase Rule Enforcement
5.  Resource Ownership Validation
6.  Secure Session Management
7.  API Security Hardening
8.  Error Handling Security
9.  Anti-Enumeration Protection
10. Account Security
11. IP and Network Security
12. Behavioral Security
13. Admin Panel Security
14. Security Logging
15. Database Query Security
16. Additional API Hardening
"""

import re
import os
import json
import time
import hmac
import hashlib
import logging
import secrets
import fnmatch
from typing import Dict, Any, Optional, Tuple, List, Set, Callable
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

from flask import request, jsonify, current_app, g, abort
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
SENSITIVE_ACTIONS = {'delete', 'destroy', 'ban', 'suspend', 'impersonate'}
ADMIN_PREFIXES = ('/admin/', '/api/admin', '/api/super-admin', '/system/')
AUTH_PREFIXES = ('/api/auth/', '/api/login', '/api/register', '/api/signup')
API_PREFIX = '/api/'
HEALTH_PREFIXES = ('/health', '/api/ping', '/api/pin', '/favicon.ico')

# ─────────────────────────────────────────────────────────────────────────────
# 1. STRICT BACKEND AUTHORIZATION
# ─────────────────────────────────────────────────────────────────────────────

class AuthorizationEnforcer:
    ROLE_HIERARCHY = {
        'super_admin': 100,
        'institutional_admin': 80,
        'lecturer': 50,
        'student': 20,
        'employee': 10,
    }

    ACTION_PERMISSIONS = {
        'create:users': ('super_admin', 'institutional_admin'),
        'read:users': ('super_admin', 'institutional_admin', 'lecturer'),
        'update:users': ('super_admin', 'institutional_admin'),
        'delete:users': ('super_admin',),
        'create:vouchers': ('super_admin', 'institutional_admin'),
        'read:vouchers': ('super_admin', 'institutional_admin'),
        'create:schedules': ('super_admin', 'institutional_admin'),
        'create:attendance_session': ('super_admin', 'institutional_admin', 'lecturer'),
        'mark:attendance': ('student',),
        'read:attendance': ('super_admin', 'institutional_admin', 'lecturer', 'student'),
        'read:analytics': ('super_admin', 'institutional_admin', 'lecturer'),
        'manage:system': ('super_admin',),
        'manage:institution': ('super_admin', 'institutional_admin'),
        'view:audit_logs': ('super_admin', 'institutional_admin'),
        'bypass:isolation': ('super_admin',),
    }

    @classmethod
    def check_permission(cls, user: Dict[str, Any], action: str) -> Tuple[bool, str]:
        if not user:
            return False, 'Authentication required'
        role = user.get('role', '')
        allowed = cls.ACTION_PERMISSIONS.get(action, ())
        if not allowed:
            return False, f'Unknown action: {action}'
        return role in allowed, f'Role {role} not authorized for {action}'

    @classmethod
    def require_action(cls, action: str):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                user = getattr(request, 'current_user', None)
                allowed, msg = cls.check_permission(user, action)
                if not allowed:
                    log_security_event('authorization_failure', msg, risk_score=70)
                    return jsonify({'error': 'Insufficient permissions'}), 403
                return f(*args, **kwargs)
            return wrapper
        return decorator


def require_action(action: str):
    return AuthorizationEnforcer.require_action(action)


# ─────────────────────────────────────────────────────────────────────────────
# 2. ROUTE PROTECTION
# ─────────────────────────────────────────────────────────────────────────────

class RouteProtector:
    PROTECTED_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')

    ROUTE_RULES = {
        '/api/admin/*': {'roles': ('super_admin',), 'audit': True, 'rate_limit': (20, 60)},
        '/api/super-admin/*': {'roles': ('super_admin',), 'audit': True, 'rate_limit': (20, 60)},
        '/api/institutional/*': {'roles': ('super_admin', 'institutional_admin'), 'audit': True, 'rate_limit': (30, 60)},
        '/system/*': {'roles': ('super_admin',), 'audit': True, 'rate_limit': (5, 60)},
        '/api/dashboard/*': {'auth': True, 'audit': True},
        '/api/users/*': {'auth': True, 'audit': True},
        '/api/schedules/*': {'auth': True, 'audit': True},
        '/api/attendance/*': {'auth': True, 'audit': True},
        '/api/biometric/*': {'auth': True, 'audit': True},
        '/api/voucher/*': {'auth': True, 'audit': True},
        '/api/feedback/*': {'auth': True, 'audit': True},
        '/api/mail/*': {'auth': True, 'audit': True},
    }

    @classmethod
    def get_route_rule(cls, path: str) -> Optional[Dict[str, Any]]:
        for pattern, rule in cls.ROUTE_RULES.items():
            if fnmatch.fnmatch(path, pattern):
                return rule
        return None

    @classmethod
    def check_route(cls, path: str, method: str, user: Optional[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], int]]:
        rule = cls.get_route_rule(path)
        if not rule:
            return None
        if rule.get('auth') and not user:
            return ({'error': 'Authentication required'}, 401)
        roles = rule.get('roles')
        if roles and user:
            user_role = user.get('role', '')
            if user_role not in roles:
                log_security_event('route_protection_blocked',
                    f'Role {user_role} blocked from {path}', risk_score=60)
                return ({'error': 'Insufficient permissions'}, 403)
        return None

    @classmethod
    def is_admin_route(cls, path: str) -> bool:
        return any(path.startswith(p) for p in ADMIN_PREFIXES)


# ─────────────────────────────────────────────────────────────────────────────
# 3. MULTI-TENANT ISOLATION
# ─────────────────────────────────────────────────────────────────────────────

class MultiTenantIsolator:
    @staticmethod
    def get_user_institution(user: Dict[str, Any]) -> Optional[str]:
        if not user:
            return None
        role = user.get('role', '')
        if role == 'super_admin':
            return None
        return user.get('institution_id')

    @staticmethod
    def is_cross_institution(source_inst: Optional[str], target_inst: Optional[str]) -> bool:
        if source_inst is None:
            return False
        return source_inst != target_inst

    @classmethod
    def enforce(cls, user: Dict[str, Any], target_institution_id: Optional[str] = None) -> Tuple[bool, str]:
        user_inst = cls.get_user_institution(user)
        if user_inst is None:
            return True, ''
        if target_institution_id and user_inst != target_institution_id:
            log_security_event('cross_institution_access',
                f'User {user.get("user_id")} attempted cross-institution access',
                risk_score=80)
            return False, 'Cross-institution access denied'
        return True, ''

    @classmethod
    def filter_data_by_institution(cls, data: List[Dict[str, Any]], user: Dict[str, Any]) -> List[Dict[str, Any]]:
        user_inst = cls.get_user_institution(user)
        if user_inst is None:
            return data
        return [d for d in data if d.get('institution_id') == user_inst]

    @classmethod
    def require_institution_match(cls, param_name: str = 'institution_id'):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                user = getattr(request, 'current_user', None)
                if not user:
                    return jsonify({'error': 'Authentication required'}), 401
                target_inst = (kwargs.get(param_name)
                    or request.args.get(param_name)
                    or (request.is_json and request.get_json(silent=True) or {}).get(param_name))
                valid, msg = cls.enforce(user, target_inst)
                if not valid:
                    return jsonify({'error': msg}), 403
                return f(*args, **kwargs)
            return wrapper
        return decorator


# ─────────────────────────────────────────────────────────────────────────────
# 4. FIREBASE RULE ENFORCEMENT
# ─────────────────────────────────────────────────────────────────────────────

class FirebaseRuleEnforcer:
    ALLOWED_COLLECTIONS = frozenset({
        'users', 'institutions', 'departments', 'courses', 'course_enrollments',
        'schedules', 'class_sessions', 'attendance_sessions', 'attendance_records',
        'vouchers', 'leave_requests', 'audit_logs', 'security_logs',
        'notifications', 'device_fingerprints', 'system_configurations',
        'demo_bookings', 'face_descriptors', 'feedback',
        'user_profiles', 'offline_sync_queue', 'network_nodes',
    })

    SENSITIVE_COLLECTIONS = frozenset({
        'face_descriptors', 'security_logs', 'audit_logs',
    })

    ROLE_COLLECTION_ACCESS = {
        'super_admin': frozenset(ALLOWED_COLLECTIONS),
        'institutional_admin': frozenset({
            'users', 'institutions', 'departments', 'courses', 'course_enrollments',
            'schedules', 'class_sessions', 'attendance_sessions', 'attendance_records',
            'vouchers', 'leave_requests', 'audit_logs', 'security_logs',
            'notifications', 'feedback', 'user_profiles',
        }),
        'lecturer': frozenset({
            'courses', 'course_enrollments', 'schedules', 'class_sessions',
            'attendance_sessions', 'attendance_records', 'leave_requests',
            'notifications', 'feedback',
        }),
        'student': frozenset({
            'attendance_records', 'leave_requests', 'notifications',
            'face_descriptors', 'feedback', 'user_profiles',
        }),
    }

    @classmethod
    def check_collection_access(cls, collection: str, user: Dict[str, Any], operation: str = 'read') -> Tuple[bool, str]:
        if not user:
            return False, 'Authentication required'
        role = user.get('role', '')
        if collection not in cls.ALLOWED_COLLECTIONS:
            return False, f'Unknown collection: {collection}'
        allowed = cls.ROLE_COLLECTION_ACCESS.get(role, frozenset())
        if collection not in allowed:
            return False, f'Access denied to collection: {collection}'
        if collection in cls.SENSITIVE_COLLECTIONS and operation in ('write', 'delete'):
            if role not in ('super_admin', 'institutional_admin'):
                return False, f'Write access denied to sensitive collection: {collection}'
        return True, ''

    @classmethod
    def sanitize_firebase_data(cls, data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = dict(data)
        user_inst = MultiTenantIsolator.get_user_institution(user)
        if user_inst and 'institution_id' in sanitized:
            if sanitized['institution_id'] != user_inst:
                log_security_event('data_tamper_attempt',
                    'Attempt to write data with wrong institution_id',
                    risk_score=90)
                sanitized['institution_id'] = user_inst
        blocked_keys = {'password_hash', 'token', 'secret', 'private_key'}
        for key in list(sanitized.keys()):
            if any(bk in key.lower() for bk in blocked_keys):
                del sanitized[key]
        return sanitized


# ─────────────────────────────────────────────────────────────────────────────
# 5. RESOURCE OWNERSHIP VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

class ResourceOwnershipValidator:
    @staticmethod
    def get_resource_owner_id(resource_type: str, resource_data: Dict[str, Any]) -> Optional[str]:
        owner_fields = {
            'attendance_records': 'student_id',
            'users': 'id',
            'notifications': 'user_id',
            'face_descriptors': 'user_id',
            'leave_requests': 'user_id',
            'device_fingerprints': 'user_id',
            'feedback': 'user_id',
            'course_enrollments': 'student_id',
        }
        field = owner_fields.get(resource_type)
        if field:
            return resource_data.get(field)
        return None

    @classmethod
    def validate_ownership(cls, user: Dict[str, Any], resource_type: str,
                          resource_data: Dict[str, Any]) -> Tuple[bool, str]:
        if not user:
            return False, 'Authentication required'
        role = user.get('role', '')
        if role in ('super_admin', 'institutional_admin'):
            return True, ''
        owner_id = cls.get_resource_owner_id(resource_type, resource_data)
        if owner_id is None:
            return True, ''
        user_id = user.get('user_id')
        if owner_id != user_id:
            log_security_event('ownership_violation',
                f'User {user_id} attempted access to {resource_type} owned by {owner_id}',
                risk_score=70)
            return False, 'Resource ownership mismatch'
        return True, ''

    @classmethod
    def require_ownership(cls, resource_type: str, id_field: str = 'resource_id'):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                user = getattr(request, 'current_user', None)
                if not user:
                    return jsonify({'error': 'Authentication required'}), 401
                role = user.get('role', '')
                if role in ('super_admin', 'institutional_admin'):
                    return f(*args, **kwargs)
                resource_id = (kwargs.get(id_field)
                    or request.args.get(id_field)
                    or (request.is_json and request.get_json(silent=True) or {}).get(id_field))
                if resource_id:
                    from src.infrastructure.repositories import user_repo
                    data = user_repo.get_by_id(resource_id) if resource_type == 'users' else None
                    if data:
                        valid, msg = cls.validate_ownership(user, resource_type, data)
                        if not valid:
                            return jsonify({'error': msg}), 403
                return f(*args, **kwargs)
            return wrapper
        return decorator


# ─────────────────────────────────────────────────────────────────────────────
# 6. SECURE SESSION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class SessionSecurityManager:
    SESSION_EXPIRY = timedelta(hours=1)
    MAX_CONCURRENT_SESSIONS = 5
    IDLE_TIMEOUT = timedelta(minutes=30)
    ABSOLUTE_TIMEOUT = timedelta(hours=8)

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, user_id: str, metadata: Dict[str, Any]) -> str:
        self._cleanup_expired()
        active = [s for s in self._sessions.values()
                  if s['user_id'] == user_id and s.get('active', False)]
        if len(active) >= self.MAX_CONCURRENT_SESSIONS:
            oldest = min(active, key=lambda s: s['created_at'])
            oldest['active'] = False
        session_id = secrets.token_urlsafe(32)
        self._sessions[session_id] = {
            'user_id': user_id,
            'created_at': time.time(),
            'last_activity': time.time(),
            'ip_address': request.remote_addr if request else 'unknown',
            'user_agent': request.headers.get('User-Agent', '') if request else '',
            'active': True,
            'metadata': metadata,
        }
        return session_id

    def validate_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.get(session_id)
        if not session:
            return None
        if not session.get('active', False):
            return None
        now = time.time()
        if now - session['last_activity'] > self.IDLE_TIMEOUT.total_seconds():
            session['active'] = False
            log_security_event('session_idle_timeout', f'Session {session_id[:16]}... timed out', risk_score=20)
            return None
        if now - session['created_at'] > self.ABSOLUTE_TIMEOUT.total_seconds():
            session['active'] = False
            log_security_event('session_absolute_timeout', f'Session {session_id[:16]}... expired', risk_score=20)
            return None
        session['last_activity'] = now
        return session

    def invalidate_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if session:
            session['active'] = False

    def invalidate_user_sessions(self, user_id: str):
        for session in self._sessions.values():
            if session['user_id'] == user_id:
                session['active'] = False

    def _cleanup_expired(self):
        now = time.time()
        expired = [sid for sid, s in self._sessions.items()
                   if now - s['last_activity'] > self.ABSOLUTE_TIMEOUT.total_seconds()]
        for sid in expired:
            del self._sessions[sid]

    def get_active_session_count(self, user_id: str) -> int:
        return sum(1 for s in self._sessions.values()
                   if s['user_id'] == user_id and s.get('active', False))


session_security = SessionSecurityManager()


def require_session(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        session_token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
        if not session_token:
            return jsonify({'error': 'Session required'}), 401
        session = session_security.validate_session(session_token)
        if not session:
            return jsonify({'error': 'Invalid or expired session'}), 401
        g.session = session
        return f(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# 7. API SECURITY HARDENING
# ─────────────────────────────────────────────────────────────────────────────

class APIHardener:
    BLOCKED_HEADERS = frozenset({
        'x-forwarded-host', 'x-forwarded-scheme', 'x-originating-ip',
        'x-remote-ip', 'x-remote-addr', 'x-client-ip',
    })

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    MAX_FIELD_LENGTH = 10000
    MAX_FIELDS_PER_REQUEST = 100
    MAX_NESTING_DEPTH = 10

    ALLOWED_CONTENT_TYPES = frozenset({
        'application/json', 'multipart/form-data', 'application/x-www-form-urlencoded',
    })

    @classmethod
    def validate_content_type(cls) -> Optional[Tuple[Dict[str, str], int]]:
        if request.method in ('POST', 'PUT', 'PATCH'):
            ct = (request.content_type or '').split(';')[0].strip()
            if ct and ct not in cls.ALLOWED_CONTENT_TYPES:
                if not ct.startswith('multipart/'):
                    return ({'error': 'Unsupported media type'}, 415)
        return None

    @classmethod
    def validate_request_size(cls) -> Optional[Tuple[Dict[str, str], int]]:
        if request.content_length and request.content_length > cls.MAX_CONTENT_LENGTH:
            return ({'error': 'Request entity too large'}, 413)
        return None

    @classmethod
    def validate_data_structure(cls, data: Any, depth: int = 0) -> Optional[Tuple[Dict[str, str], int]]:
        if depth > cls.MAX_NESTING_DEPTH:
            return ({'error': 'Data nesting too deep'}, 400)
        if isinstance(data, dict):
            if len(data) > cls.MAX_FIELDS_PER_REQUEST:
                return ({'error': 'Too many fields'}, 400)
            for key, value in data.items():
                if isinstance(value, str) and len(value) > cls.MAX_FIELD_LENGTH:
                    return ({'error': f'Field {key} exceeds maximum length'}, 400)
                if isinstance(value, (dict, list)):
                    result = cls.validate_data_structure(value, depth + 1)
                    if result:
                        return result
        elif isinstance(data, list):
            if len(data) > 1000:
                return ({'error': 'Array too large'}, 400)
            for item in data:
                if isinstance(item, (dict, list)):
                    result = cls.validate_data_structure(item, depth + 1)
                    if result:
                        return result
        return None

    @classmethod
    def remove_hop_by_hop_headers(cls):
        hop_by_hop = frozenset({
            'Connection', 'Keep-Alive', 'Proxy-Authenticate', 'Proxy-Authorization',
            'TE', 'Trailer', 'Transfer-Encoding', 'Upgrade',
        })
        for header in hop_by_hop:
            request.headers.environ.pop(header, None)

    @classmethod
    def check_blocked_headers(cls) -> Optional[Tuple[Dict[str, str], int]]:
        for header in cls.BLOCKED_HEADERS:
            if request.headers.get(header):
                log_security_event('blocked_header_detected',
                    f'Blocked header {header} present in request', risk_score=60)
                return ({'error': 'Invalid request'}, 400)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 8. ERROR HANDLING SECURITY
# ─────────────────────────────────────────────────────────────────────────────

class SecureErrorHandler:
    GENERIC_MESSAGES = {
        400: 'Bad request',
        401: 'Authentication required',
        403: 'Access denied',
        404: 'Resource not found',
        405: 'Method not allowed',
        409: 'Conflict',
        413: 'Request too large',
        415: 'Unsupported media type',
        429: 'Too many requests. Please try again later.',
        500: 'An unexpected error occurred',
        502: 'Service temporarily unavailable',
        503: 'Service unavailable',
    }

    NONCE_PATTERNS = [
        r'\buser_id\b', r'\bemail\b', r'\btoken\b',
        r'\bsession\b', r'\bpassword\b', r'\bsecret\b',
    ]

    @classmethod
    def safe_error(cls, status_code: int, message: Optional[str] = None,
                   log_details: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
        safe_msg = message or cls.GENERIC_MESSAGES.get(status_code, 'An error occurred')
        response = {'error': safe_msg, 'status': status_code}
        env = current_app.config.get('ENVIRONMENT', 'production') if current_app else 'production'
        if env in ('development', 'staging') and log_details:
            response['debug'] = str(log_details)[:500]
        if log_details:
            log_security_event('error_response', f'{status_code}: {log_details}',
                             risk_score=30 if status_code >= 500 else 10)
        return jsonify(response), status_code

    @classmethod
    def sanitize_error_message(cls, message: str) -> str:
        for pattern in cls.NONCE_PATTERNS:
            message = re.sub(pattern, '[REDACTED]', message, flags=re.IGNORECASE)
        return message[:500]

    @classmethod
    def hide_internal_error(cls, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Unhandled exception in {request.path}: {e}", exc_info=True)
                return cls.safe_error(500, log_details=str(e)[:200])
        return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# 9. ANTI-ENUMERATION PROTECTION
# ─────────────────────────────────────────────────────────────────────────────

class AntiEnumerationProtector:
    def __init__(self):
        self._timing_stats: Dict[str, List[float]] = defaultdict(list)
        self._response_cache: Dict[str, Tuple[Dict[str, Any], int]] = {}

    def constant_time_compare(self, a: str, b: str) -> bool:
        return hmac.compare_digest(a, b)

    def uniform_error(self, field: str = 'credentials') -> Tuple[Dict[str, Any], int]:
        return jsonify({'error': f'Invalid {field}'}), 401

    def obfuscate_resource_count(self, count: int, max_show: int = 10) -> int:
        if count <= max_show:
            return count
        return max_show + (count % 5)

    def add_response_jitter(self, min_ms: float = 50, max_ms: float = 150):
        import random as _r
        jitter = _r.uniform(min_ms, max_ms) / 1000.0
        time.sleep(jitter)

    def normalize_response_time(self, success_time: float, failure_time: float) -> float:
        target = (success_time + failure_time) / 2
        if abs(success_time - target) > 0.05:
            time.sleep(max(0, target - success_time))
        return target

    def paginate_safely(self, page: int, per_page: int, max_per_page: int = 50) -> Tuple[int, int]:
        safe_page = max(1, min(page, 1000))
        safe_per_page = max(1, min(per_page, max_per_page))
        return safe_page, safe_per_page


anti_enum = AntiEnumerationProtector()


# ─────────────────────────────────────────────────────────────────────────────
# 10. ACCOUNT SECURITY
# ─────────────────────────────────────────────────────────────────────────────

class AccountSecurityManager:
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)
    PASSWORD_HISTORY_SIZE = 5
    ACCOUNT_ACTIVATION_TIMEOUT = timedelta(days=7)

    def __init__(self):
        self._login_attempts: Dict[str, List[float]] = defaultdict(list)
        self._lockouts: Dict[str, datetime] = {}

    def record_login_attempt(self, identifier: str, success: bool):
        now = datetime.utcnow()
        if success:
            self._login_attempts.pop(identifier, None)
            self._lockouts.pop(identifier, None)
        else:
            attempts = self._login_attempts.setdefault(identifier, [])
            attempts.append(now)
            attempts[:] = [t for t in attempts if now - t < timedelta(hours=1)]
            if len(attempts) >= self.MAX_LOGIN_ATTEMPTS:
                self._lockouts[identifier] = now + self.LOCKOUT_DURATION
                log_security_event('account_locked',
                    f'Account {identifier} locked for {self.LOCKOUT_DURATION}', risk_score=70)

    def is_locked(self, identifier: str) -> Tuple[bool, Optional[int]]:
        lockout = self._lockouts.get(identifier)
        if lockout:
            now = datetime.utcnow()
            if now < lockout:
                remaining = int((lockout - now).total_seconds())
                return True, remaining
            del self._lockouts[identifier]
        return False, None

    def get_remaining_attempts(self, identifier: str) -> int:
        now = datetime.utcnow()
        attempts = self._login_attempts.get(identifier, [])
        attempts[:] = [t for t in attempts if now - t < timedelta(hours=1)]
        return max(0, self.MAX_LOGIN_ATTEMPTS - len(attempts))

    def require_not_locked(self, identifier_param: str = 'email'):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                data = request.get_json(silent=True) or {}
                identifier = data.get(identifier_param, '')
                locked, remaining = self.is_locked(identifier)
                if locked:
                    log_security_event('login_blocked_locked',
                        f'Login blocked for locked account {identifier}', risk_score=50)
                    return jsonify({
                        'error': 'Account temporarily locked. Try again later.',
                        'retry_after': remaining
                    }), 429
                return f(*args, **kwargs)
            return wrapper
        return decorator


account_security = AccountSecurityManager()


# ─────────────────────────────────────────────────────────────────────────────
# 11. IP AND NETWORK SECURITY
# ─────────────────────────────────────────────────────────────────────────────

class IPNetworkSecurityManager:
    PRIVATE_RANGES = [
        ('127.0.0.0', '127.255.255.255'),
        ('10.0.0.0', '10.255.255.255'),
        ('172.16.0.0', '172.31.255.255'),
        ('192.168.0.0', '192.168.255.255'),
    ]

    SUSPICIOUS_PORTS = frozenset({22, 23, 25, 53, 135, 137, 139, 445, 1433, 1521, 3306, 3389, 5432, 6379, 8080, 8443, 27017})

    def __init__(self):
        self._rate_by_ip: Dict[str, List[float]] = defaultdict(list)

    @staticmethod
    def get_client_ip() -> str:
        cf_ip = request.headers.get('CF-Connecting-IP')
        if cf_ip:
            return cf_ip.split(',')[0].strip()
        xff = request.headers.get('X-Forwarded-For')
        if xff:
            return xff.split(',')[0].strip()
        return request.remote_addr or '0.0.0.0'

    @classmethod
    def ip_to_int(cls, ip: str) -> Optional[int]:
        try:
            parts = [int(p) for p in ip.split('.')]
            return (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
        except (ValueError, IndexError):
            return None

    @classmethod
    def is_private_ip(cls, ip: str) -> bool:
        ip_int = cls.ip_to_int(ip)
        if ip_int is None:
            return False
        for start, end in cls.PRIVATE_RANGES:
            start_int = cls.ip_to_int(start)
            end_int = cls.ip_to_int(end)
            if start_int and end_int and start_int <= ip_int <= end_int:
                return True
        return False

    @classmethod
    def is_suspicious_port_scan(cls, path: str) -> bool:
        if path.startswith('/api/institutional/network-scanner'):
            return False
            
        port_patterns = [
            r':(22|23|25|135|139|445|1433|3306|3389|5432|6379|27017)[/\s]',
            r'scan', r'nmap', r'masscan', r'port.*check',
        ]
        for pattern in port_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        return False

    def rate_limit_ip(self, max_requests: int = 100, window: int = 60) -> Tuple[bool, int]:
        ip = self.get_client_ip()
        now = time.time()
        requests = self._rate_by_ip[ip]
        requests[:] = [t for t in requests if now - t < window]
        if len(requests) >= max_requests:
            return True, len(requests)
        requests.append(now)
        return False, len(requests)


ip_network_security = IPNetworkSecurityManager()


# ─────────────────────────────────────────────────────────────────────────────
# 12. BEHAVIORAL SECURITY
# ─────────────────────────────────────────────────────────────────────────────

class BehavioralSecurityMonitor:
    def __init__(self):
        self._user_behavior: Dict[str, Dict[str, Any]] = {}
        self._velocity_checks: Dict[str, List[float]] = defaultdict(list)

    SUSPICIOUS_PATTERNS = {
        'rapid_fire': {'window': 5, 'threshold': 20, 'risk': 60},
        'endpoint_crawl': {'window': 30, 'threshold': 50, 'risk': 50},
        'auth_storm': {'window': 10, 'threshold': 10, 'risk': 80},
        'admin_probe': {'window': 60, 'threshold': 5, 'risk': 70},
    }

    def track_request(self, user_id: str, path: str, method: str):
        now = time.time()
        behavior = self._user_behavior.setdefault(user_id, {
            'paths': defaultdict(int),
            'methods': defaultdict(int),
            'first_seen': now,
            'last_seen': now,
            'total_requests': 0,
            'suspicious_score': 0,
        })
        behavior['paths'][path] += 1
        behavior['methods'][method] += 1
        behavior['total_requests'] += 1
        behavior['last_seen'] = now

        velocity_key = f'{user_id}:{path}'
        hits = self._velocity_checks[velocity_key]
        hits.append(now)
        hits[:] = [t for t in hits if now - t > 1]

        rapid = [t for t in hits if now - t < 5]
        if len(rapid) > 20:
            log_security_event('behavior_rapid_fire',
                f'Rapid-fire requests from {user_id} to {path}', risk_score=60)

        if path.startswith('/api/auth'):
            auth_hits = [t for t in hits if now - t < 10]
            if len(auth_hits) > 10:
                log_security_event('behavior_auth_storm',
                    f'Auth storm detected from {user_id}', risk_score=80)

        admin_count = sum(1 for p in behavior['paths'] if p.startswith(ADMIN_PREFIXES))
        if admin_count > 20 and behavior['total_requests'] < 50:
            log_security_event('behavior_admin_probe',
                f'Admin probe pattern from {user_id}', risk_score=70)

    def get_behavior_score(self, user_id: str) -> int:
        behavior = self._user_behavior.get(user_id, {})
        score = 0
        if behavior.get('total_requests', 0) > 500:
            score += 20
        admin_ratio = sum(1 for p in behavior.get('paths', {}) if p.startswith(ADMIN_PREFIXES))
        if admin_ratio > 10 and behavior.get('total_requests', 0) < 30:
            score += 30
        return score


behavioral_monitor = BehavioralSecurityMonitor()


# ─────────────────────────────────────────────────────────────────────────────
# 13. ADMIN PANEL SECURITY
# ─────────────────────────────────────────────────────────────────────────────

class AdminPanelSecurity:
    RESTRICTED_ADMIN_ACTIONS = frozenset({
        'delete_user', 'ban_user', 'suspend_institution', 'delete_institution',
        'impersonate_user', 'modify_system_config', 'execute_raw_query',
        'mass_email', 'export_all_data', 'force_password_reset',
    })

    ACTION_CONFIRMATION_REQUIRED = frozenset({
        'delete_user', 'delete_institution', 'impersonate_user',
        'execute_raw_query', 'mass_email', 'export_all_data',
    })

    @classmethod
    def verify_admin_session(cls, user: Dict[str, Any]) -> Tuple[bool, str]:
        if not user:
            return False, 'Authentication required'
        role = user.get('role', '')
        if role not in ('super_admin', 'institutional_admin'):
            return False, 'Admin access required'
        if not user.get('is_active', True):
            return False, 'Account is disabled'
        return True, ''

    @classmethod
    def require_admin_confirmation(cls, action: str):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                user = getattr(request, 'current_user', None)
                valid, msg = cls.verify_admin_session(user)
                if not valid:
                    return jsonify({'error': msg}), 403
                if action in cls.ACTION_CONFIRMATION_REQUIRED:
                    data = request.get_json(silent=True) or {}
                    confirmation = data.get('confirmation', '') or data.get('confirm', '')
                    if confirmation != action:
                        return jsonify({
                            'error': f'Confirmation required for action: {action}',
                            'confirmation_required': action,
                        }), 400
                log_security_event('admin_action',
                    f'Admin {user.get("user_id")} performed {action}', risk_score=0)
                return f(*args, **kwargs)
            return wrapper
        return decorator

    @classmethod
    def require_admin_role(cls, min_role: str = 'institutional_admin'):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                user = getattr(request, 'current_user', None)
                valid, msg = cls.verify_admin_session(user)
                if not valid:
                    return jsonify({'error': msg}), 403
                role = user.get('role', '')
                role_level = AuthorizationEnforcer.ROLE_HIERARCHY.get(role, 0)
                min_level = AuthorizationEnforcer.ROLE_HIERARCHY.get(min_role, 0)
                if role_level < min_level:
                    return jsonify({'error': 'Insufficient admin privileges'}), 403
                return f(*args, **kwargs)
            return wrapper
        return decorator


# ─────────────────────────────────────────────────────────────────────────────
# 14. SECURITY LOGGING
# ─────────────────────────────────────────────────────────────────────────────

class SecurityLogger:
    def __init__(self):
        self._event_buffer: List[Dict[str, Any]] = []
        self._buffer_size = 50

    def log(self, event_type: str, description: str, risk_score: int = 0,
            user_id: Optional[str] = None, ip_address: Optional[str] = None,
            user_agent: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        try:
            if user_id is None and hasattr(request, 'current_user'):
                user_id = request.current_user.get('user_id')
            if ip_address is None:
                ip_address = IPNetworkSecurityManager.get_client_ip()
            if user_agent is None:
                user_agent = request.headers.get('User-Agent', '')[:500]

            event = {
                'event_type': event_type,
                'description': str(description)[:1000],
                'risk_score': min(risk_score, 100),
                'user_id': user_id,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'path': request.path if request else '',
                'method': request.method if request else '',
                'timestamp': datetime.utcnow().isoformat(),
            }
            if metadata:
                try:
                    event['metadata'] = json.dumps(metadata)[:2000]
                except (TypeError, ValueError):
                    event['metadata'] = str(metadata)[:2000]

            log_level = logging.WARNING if risk_score >= 50 else logging.INFO
            logger.log(log_level, f"[{event_type}] {description} (risk={risk_score}) user={user_id} ip={ip_address}")

            self._event_buffer.append(event)
            if len(self._event_buffer) >= self._buffer_size:
                self._flush_buffer()
        except Exception as e:
            logger.error(f"Security logging failed: {e}")

    def _flush_buffer(self):
        if not self._event_buffer:
            return
        try:
            from src.infrastructure.repositories import security_log_repo
            buffer = self._event_buffer[:]
            self._event_buffer.clear()
            for event in buffer:
                try:
                    security_log_repo.create(event)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to flush security log buffer: {e}")

    def log_request(self, response_status: int):
        try:
            user_id = None
            if hasattr(request, 'current_user'):
                user_id = request.current_user.get('user_id')

            if response_status >= 400:
                risk = 50 if response_status >= 500 else 30 if response_status >= 403 else 20
                self.log('http_error',
                    f'{request.method} {request.path} -> {response_status}',
                    risk_score=risk, user_id=user_id)
            elif response_status < 400:
                if user_id and not request.path.startswith(HEALTH_PREFIXES):
                    pass
        except Exception:
            pass


security_logger = SecurityLogger()


def log_security_event(event_type: str, description: str, risk_score: int = 0,
                       user_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
    security_logger.log(event_type, description, risk_score, user_id=user_id, metadata=metadata)


# ─────────────────────────────────────────────────────────────────────────────
# 15. DATABASE QUERY SECURITY
# ─────────────────────────────────────────────────────────────────────────────

class DatabaseQuerySecurity:
    BLOCKED_PATTERNS = [
        r"(?i)(\bOR\b|\bAND\b).*[=].*[=]",
        r"(?i)union.*select",
        r"(?i)select.*from.*(password|token|secret|key)",
        r"(?i)(exec|execute|xp_cmdshell|sp_executesql)",
        r"(?i)(drop|truncate|alter|create|delete).*(table|database|index|view)",
        r"(?i)information_schema",
        r"(?i)pg_sleep|waitfor.*delay|benchmark\s*\(",
        r"(?i)load_file|into\s+(out|dump)file",
        r"(?i)char\s*\(|nchar\s*\(",
        r"(?i)convert\s*\(.*,.*\)",
    ]

    SAFE_QUERY_PATTERNS = [
        r"^[a-zA-Z0-9_\s,='()]+$",
    ]

    MAX_QUERY_LENGTH = 5000
    MAX_IN_CLAUSE = 100
    MAX_NESTED_QUERIES = 5

    @classmethod
    def validate_query(cls, query: str) -> Tuple[bool, Optional[str]]:
        if not query or not isinstance(query, str):
            return False, 'Invalid query'
        if len(query) > cls.MAX_QUERY_LENGTH:
            return False, 'Query too long'
        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, query):
                return False, 'Query contains blocked patterns'
        return True, None

    @classmethod
    def sanitize_query_param(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\\\']', '', value)
            return cleaned[:1000]
        if isinstance(value, dict):
            return {k: cls.sanitize_query_param(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls.sanitize_query_param(v) for v in value][:cls.MAX_IN_CLAUSE]
        return value

    @classmethod
    def validate_firestore_filter(cls, filters: List[Dict[str, Any]],
                                  user: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if len(filters) > 20:
            return False, 'Too many filters'
        for f in filters:
            field = f.get('field', '')
            if field.startswith('$') or '.' in field:
                return False, f'Invalid field name: {field}'
            value = f.get('value')
            if isinstance(value, str) and len(value) > 1000:
                return False, f'Filter value too long for field: {field}'
            op = f.get('operator', '==')
            if op not in ('==', '!=', '<', '<=', '>', '>=', 'array-contains',
                          'array-contains-any', 'in', 'not-in'):
                return False, f'Invalid operator: {op}'
        if user:
            user_inst = MultiTenantIsolator.get_user_institution(user)
            if user_inst:
                has_inst = any(f.get('field') == 'institution_id' for f in filters)
                if not has_inst:
                    filters.append({'field': 'institution_id', 'value': user_inst})
        return True, None


db_query_security = DatabaseQuerySecurity()


# ─────────────────────────────────────────────────────────────────────────────
# 16. MIDDLEWARE REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

def register_comprehensive_security_middleware(app):
    @app.before_request
    def comprehensive_security_before():
        if request.path.startswith(HEALTH_PREFIXES):
            return None

        g.request_start_time = time.time()
        g.request_id = secrets.token_hex(8)

        ip = IPNetworkSecurityManager.get_client_ip()

        if IPNetworkSecurityManager.is_suspicious_port_scan(request.path):
            log_security_event('port_scan_attempt',
                f'Port scan pattern detected from {ip}', risk_score=90)
            return jsonify({'error': 'Invalid request'}), 400

        ct_result = APIHardener.validate_content_type()
        if ct_result:
            return ct_result

        size_result = APIHardener.validate_request_size()
        if size_result:
            return size_result

        header_result = APIHardener.check_blocked_headers()
        if header_result:
            return header_result

        if request.is_json:
            data = request.get_json(silent=True)
            if data is not None:
                structure_result = APIHardener.validate_data_structure(data)
                if structure_result:
                    return structure_result

        if request.path.startswith(API_PREFIX):
            limited, count = ip_network_security.rate_limit_ip()
            if limited:
                log_security_event('ip_rate_limited',
                    f'IP {ip} rate limited ({count} requests)', risk_score=50)
                return jsonify({'error': 'Too many requests'}), 429

        user = getattr(request, 'current_user', None)
        if user:
            behavioral_monitor.track_request(
                user.get('user_id', 'unknown'), request.path, request.method
            )

        return None

    @app.after_request
    def comprehensive_security_after(response):
        if hasattr(g, 'request_start_time'):
            duration = time.time() - g.request_start_time
            response.headers['X-Response-Time'] = f'{duration:.3f}s'

        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Request-Id'] = getattr(g, 'request_id', '')

        security_logger.log_request(response.status_code)

        return response

    @app.errorhandler(404)
    def secure_404(error):
        log_security_event('404_not_found', f'Resource not found: {request.path}', risk_score=10)
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(500)
    def secure_500(error):
        log_security_event('500_error', f'Internal error on {request.path}', risk_score=50)
        env = app.config.get('ENVIRONMENT', 'production')
        msg = 'An unexpected error occurred'
        if env == 'development':
            msg = str(error)
        return jsonify({'error': msg}), 500

    @app.errorhandler(403)
    def secure_403(error):
        log_security_event('403_forbidden', f'Forbidden access: {request.path}', risk_score=60)
        return jsonify({'error': 'Access denied'}), 403

    @app.errorhandler(429)
    def secure_429(error):
        return jsonify({'error': 'Too many requests. Please try again later.'}), 429

    logger.info('Comprehensive security middleware registered')

    return app
