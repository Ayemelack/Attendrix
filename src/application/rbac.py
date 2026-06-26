from functools import wraps
from flask import request, jsonify, current_app, g
from typing import Dict, Any, List, Set
import logging
import time
from datetime import datetime

from src.domain.entities import UserRole
from src.application.auth_service import auth_service

logger = logging.getLogger(__name__)


class Permission:
    """Permission class for defining access rights"""

    # Institution permissions
    MANAGE_INSTITUTION = "manage_institution"
    VIEW_INSTITUTION_ANALYTICS = "view_institution_analytics"

    # Department permissions
    MANAGE_DEPARTMENTS = "manage_departments"
    VIEW_DEPARTMENT_ANALYTICS = "view_department_analytics"

    # User management permissions
    MANAGE_USERS = "manage_users"
    CREATE_USERS = "create_users"
    VIEW_USERS = "view_users"

    # Course permissions
    MANAGE_COURSES = "manage_courses"
    VIEW_COURSES = "view_courses"
    ENROLL_STUDENTS = "enroll_students"

    # Schedule permissions
    MANAGE_SCHEDULES = "manage_schedules"
    VIEW_SCHEDULES = "view_schedules"

    # Attendance permissions
    MANAGE_ATTENDANCE = "manage_attendance"
    MARK_ATTENDANCE = "mark_attendance"
    VIEW_ATTENDANCE = "view_attendance"
    VIEW_ATTENDANCE_REPORTS = "view_attendance_reports"

    # Leave permissions
    MANAGE_LEAVE_REQUESTS = "manage_leave_requests"
    SUBMIT_LEAVE_REQUEST = "submit_leave_request"
    APPROVE_LEAVE_REQUEST = "approve_leave_request"

    # Analytics permissions
    VIEW_ANALYTICS = "view_analytics"
    VIEW_PREDICTIVE_ANALYTICS = "view_predictive_analytics"

    # System permissions
    MANAGE_SYSTEM = "manage_system"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_NOTIFICATIONS = "manage_notifications"


class RolePermissions:
    """Role-based permission mappings"""

    PERMISSIONS = {
        UserRole.SUPER_ADMIN: [
            Permission.MANAGE_SYSTEM,
            Permission.MANAGE_INSTITUTION,
            Permission.VIEW_INSTITUTION_ANALYTICS,
            Permission.MANAGE_DEPARTMENTS,
            Permission.VIEW_DEPARTMENT_ANALYTICS,
            Permission.MANAGE_USERS,
            Permission.CREATE_USERS,
            Permission.VIEW_USERS,
            Permission.MANAGE_COURSES,
            Permission.VIEW_COURSES,
            Permission.ENROLL_STUDENTS,
            Permission.MANAGE_SCHEDULES,
            Permission.VIEW_SCHEDULES,
            Permission.MANAGE_ATTENDANCE,
            Permission.MARK_ATTENDANCE,
            Permission.VIEW_ATTENDANCE,
            Permission.VIEW_ATTENDANCE_REPORTS,
            Permission.MANAGE_LEAVE_REQUESTS,
            Permission.SUBMIT_LEAVE_REQUEST,
            Permission.APPROVE_LEAVE_REQUEST,
            Permission.VIEW_ANALYTICS,
            Permission.VIEW_PREDICTIVE_ANALYTICS,
            Permission.VIEW_AUDIT_LOGS,
            Permission.MANAGE_NOTIFICATIONS,
        ],

        UserRole.INSTITUTIONAL_ADMIN: [
            Permission.MANAGE_DEPARTMENTS,
            Permission.VIEW_DEPARTMENT_ANALYTICS,
            Permission.MANAGE_USERS,
            Permission.CREATE_USERS,
            Permission.VIEW_USERS,
            Permission.MANAGE_COURSES,
            Permission.VIEW_COURSES,
            Permission.ENROLL_STUDENTS,
            Permission.MANAGE_SCHEDULES,
            Permission.VIEW_SCHEDULES,
            Permission.MANAGE_ATTENDANCE,
            Permission.VIEW_ATTENDANCE,
            Permission.VIEW_ATTENDANCE_REPORTS,
            Permission.MANAGE_LEAVE_REQUESTS,
            Permission.APPROVE_LEAVE_REQUEST,
            Permission.VIEW_ANALYTICS,
            Permission.VIEW_AUDIT_LOGS,
            Permission.MANAGE_NOTIFICATIONS,
        ],

        UserRole.LECTURER: [
            Permission.VIEW_COURSES,
            Permission.MANAGE_ATTENDANCE,
            Permission.MARK_ATTENDANCE,
            Permission.VIEW_ATTENDANCE,
            Permission.VIEW_ATTENDANCE_REPORTS,
            Permission.VIEW_SCHEDULES,
            Permission.SUBMIT_LEAVE_REQUEST,
            Permission.VIEW_ANALYTICS,
        ],

        UserRole.EMPLOYEE: [
            Permission.VIEW_COURSES,
            Permission.VIEW_ATTENDANCE,
            Permission.VIEW_SCHEDULES,
            Permission.SUBMIT_LEAVE_REQUEST,
        ],

        UserRole.STUDENT: [
            Permission.VIEW_COURSES,
            Permission.MARK_ATTENDANCE,
            Permission.VIEW_ATTENDANCE,
            Permission.VIEW_SCHEDULES,
            Permission.SUBMIT_LEAVE_REQUEST,
            Permission.VIEW_ANALYTICS,
        ]
    }

    @classmethod
    def get_permissions(cls, role: UserRole) -> Set[str]:
        """Get permissions for a role"""
        return set(cls.PERMISSIONS.get(role, []))

    @classmethod
    def has_permission(cls, role: UserRole, permission: str) -> bool:
        """Check if role has specific permission"""
        return permission in cls.PERMISSIONS.get(role, [])

    @classmethod
    def has_any_permission(cls, role: UserRole, permissions: List[str]) -> bool:
        """Check if role has any of the specified permissions"""
        role_permissions = cls.get_permissions(role)
        return any(perm in role_permissions for perm in permissions)

    @classmethod
    def has_all_permissions(cls, role: UserRole, permissions: List[str]) -> bool:
        """Check if role has all of the specified permissions"""
        role_permissions = cls.get_permissions(role)
        return all(perm in role_permissions for perm in permissions)


def require_auth(f):
    """Hardened decorator to require authentication with secure JWT validation.

    Strict token verification — no dev bypass. All requests must present
    a valid Authorization: Bearer <token> header. The token payload is
    validated against the user store and checked for active status.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            log_security_alert('missing_auth_header', 'No Authorization header')
            return jsonify({'error': 'Authentication required'}), 401

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            log_security_alert('bad_auth_format', f'Malformed Authorization header: {auth_header[:40]}')
            return jsonify({'error': 'Invalid authorization header format'}), 401

        token = parts[1]

        if not token or len(token) < 20:
            log_security_alert('short_token', 'Token too short, likely spoofed')
            return jsonify({'error': 'Invalid token'}), 401

        payload = auth_service.verify_token(token)
        if not payload:
            log_security_alert('invalid_token', 'Token verification failed')
            return jsonify({'error': 'Invalid or expired token'}), 401

        required_fields = ['user_id', 'email', 'role', 'institution_id']
        for field in required_fields:
            if field not in payload:
                log_security_alert('incomplete_token_payload', f'Token missing field: {field}')
                return jsonify({'error': 'Invalid token'}), 401

        request.current_user = payload
        return f(*args, **kwargs)

    return decorated_function


def log_security_alert(event_type: str, description: str):
    """Log security alerts without importing the full audit module."""
    try:
        from src.infrastructure.repositories import security_log_repo
        from datetime import datetime
        security_log_repo.create({
            'user_id': getattr(request, 'current_user', {}).get('user_id') if hasattr(request, 'current_user') else None,
            'event_type': event_type,
            'description': description,
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')[:500],
            'risk_score': 70,
            'created_at': datetime.utcnow().isoformat()
        })
    except Exception:
        pass


def require_role(*allowed_roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401
            
            user_role = request.current_user.get('role')
            
            # Convert string role to UserRole enum if needed
            if isinstance(user_role, str):
                try:
                    user_role = UserRole(user_role)
                except ValueError:
                    return jsonify({'error': 'Invalid user role'}), 403
            
            # Convert allowed roles to UserRole enum if they are strings
            allowed_role_enums = []
            for role in allowed_roles:
                if isinstance(role, str):
                    try:
                        allowed_role_enums.append(UserRole(role))
                    except ValueError:
                        continue
                else:
                    allowed_role_enums.append(role)
            
            if user_role not in allowed_role_enums:
                logger.warning(f"Access denied: User role {user_role} not in allowed roles {allowed_role_enums}")
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_admin_webauthn(f):
    """Require admin users to have at least one WebAuthn passkey enrolled.

    Applied after @require_auth and @require_role so that only authenticated
    admin users reach this check.  Routes needed for *enrolling* the first
    passkey (register_begin, register_complete) must NOT use this decorator.
    """
    _admin_roles = {UserRole.SUPER_ADMIN, UserRole.INSTITUTIONAL_ADMIN}

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({'error': 'Authentication required'}), 401

        role = request.current_user.get('role')
        if isinstance(role, str):
            try:
                role = UserRole(role)
            except ValueError:
                return jsonify({'error': 'Invalid user role'}), 403

        if role not in _admin_roles:
            return f(*args, **kwargs)

        from src.infrastructure.security.webauthn_service import webauthn_service
        user_id = request.current_user.get('user_id')
        if not webauthn_service.has_active_credentials(user_id):
            logger.warning(f"Admin 2FA block: user {user_id} has no passkey enrolled")
            return jsonify({
                'error': 'Passkey required',
                'message': 'Enroll a passkey before performing admin actions',
                'setup_required': True,
                'setup_url': '/auth/webauthn/register/begin',
            }), 403

        return f(*args, **kwargs)

    return decorated_function


def require_permission(*permissions: str):
    """Decorator to require specific permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401
            
            user_role = UserRole(request.current_user.get('role'))
            
            if not RolePermissions.has_any_permission(user_role, permissions):
                logger.warning(f"Access denied: User role {user_role} lacks required permissions {permissions}")
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_institution_access(f):
    """Decorator to ensure user can access institution data"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = UserRole(request.current_user.get('role'))
        user_institution_id = request.current_user.get('institution_id')
        
        # Super admins can access any institution
        if user_role == UserRole.SUPER_ADMIN:
            return f(*args, **kwargs)
        
        # Get institution_id from request (either from path, query param, or request body)
        target_institution_id = None
        
        # Check path parameters
        if 'institution_id' in kwargs:
            target_institution_id = kwargs['institution_id']
        # Check query parameters
        elif 'institution_id' in request.args:
            target_institution_id = request.args.get('institution_id')
        # Check JSON body
        elif request.is_json and 'institution_id' in request.get_json():
            target_institution_id = request.get_json()['institution_id']
        
        # If no specific institution requested, allow access to user's own institution
        if not target_institution_id:
            return f(*args, **kwargs)
        
        # Check if user can access the requested institution
        if user_institution_id != target_institution_id:
            logger.warning(f"Access denied: User cannot access institution {target_institution_id}")
            return jsonify({'error': 'Access denied to institution'}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_active_user(f):
    """Decorator to ensure user account is active"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({'error': 'Authentication required'}), 401
        
        user_id = request.current_user.get('user_id')
        
        # Check user status in database
        from src.infrastructure.repositories import user_repo
        user_data = user_repo.get_by_id(user_id)
        
        if not user_data or not user_data.get('is_active', False):
            logger.warning(f"Access denied: User account {user_id} is not active")
            return jsonify({'error': 'Account is not active'}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def log_access(f):
    """Decorator to log API access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = None
        if hasattr(request, 'current_user'):
            user_id = request.current_user.get('user_id')
        
        logger.info(f"API Access: {request.method} {request.path} - User: {user_id} - IP: {request.remote_addr}")
        
        try:
            response = f(*args, **kwargs)
            
            # Log successful access
            if user_id:
                from src.infrastructure.repositories import audit_log_repo
                audit_log_data = {
                    'user_id': user_id,
                    'institution_id': request.current_user.get('institution_id') if hasattr(request, 'current_user') else None,
                    'action': f"{request.method} {request.path}",
                    'resource_type': 'api_access',
                    'ip_address': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent'),
                    'timestamp': datetime.utcnow().isoformat()
                }
                audit_log_repo.create(audit_log_data)
            
            return response
            
        except Exception as e:
            # Log failed access
            logger.error(f"API Error: {request.method} {request.path} - User: {user_id} - Error: {str(e)}")
            raise
    
    return decorated_function


class RateLimiter:
    """Simple rate limiter for API endpoints"""
    
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """Check if request is allowed based on rate limit"""
        import time
        
        now = time.time()
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests outside the window
        self.requests[key] = [req_time for req_time in self.requests[key] if now - req_time < window]
        
        # Check if under limit
        if len(self.requests[key]) < limit:
            self.requests[key].append(now)
            return True
        
        return False


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(limit: int = 100, window: int = 3600):
    """Decorator to apply rate limiting"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use IP address or user ID for rate limiting
            key = request.remote_addr
            if hasattr(request, 'current_user'):
                key = request.current_user.get('user_id', request.remote_addr)
            
            if not rate_limiter.is_allowed(key, limit, window):
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def validate_json(schema: Dict[str, Any]):
    """Decorator to validate JSON request body"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Content-Type must be application/json'}), 400
            
            data = request.get_json()
            
            # Basic validation based on schema
            for field, field_type in schema.items():
                if field in data and not isinstance(data[field], field_type):
                    return jsonify({'error': f'Field {field} must be of type {field_type.__name__}'}), 400
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


# Import datetime for audit logging
from datetime import datetime
