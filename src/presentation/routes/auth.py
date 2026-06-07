"""Authentication route blueprint — register, login, logout, password management."""

from flask import Blueprint, request, jsonify
from src.application.rbac import require_auth, log_access

from src.infrastructure.security import (
    require_captcha,
    InputSanitizer, PasswordPolicy, SecurityAuditLogger, enhanced_rate_limiter,
    rate_limit_endpoint,
)
from src.infrastructure.comprehensive_security import (
    account_security, log_security_event, anti_enum, require_action,
    ResourceOwnershipValidator, MultiTenantIsolator,
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_auth_service = None
_rate_limiter = None


def init_auth_routes(auth_service, rate_limiter):
    global _auth_service, _rate_limiter
    _auth_service = auth_service
    _rate_limiter = rate_limiter


@auth_bp.route('/register', methods=['POST'])
@log_access
@require_captcha(action='register')
@rate_limit_endpoint(limit=5, window=3600, scope='ip', block_duration=900)
def register():
    try:
        data = request.get_json()

        required_fields = ['email', 'password', 'first_name', 'last_name', 'role', 'voucher_code', 'institution_id']
        for field in required_fields:
            if field not in data:
                SecurityAuditLogger.log_event('registration_missing_field',
                    f'Missing field {field} during registration', risk_score=20)
                return jsonify({'error': f'Missing required field: {field}'}), 400

        password = data['password']

        # Enterprise password policy enforcement
        pw_valid, pw_error = PasswordPolicy.validate(password)
        if not pw_valid:
            SecurityAuditLogger.log_event('weak_password', f'Weak password attempt: {pw_error}', risk_score=30)
            return jsonify({'error': pw_error}), 400

        # Sanitize text inputs
        sanitized_email = InputSanitizer.sanitize_email(data['email'])
        sanitized_first_name = InputSanitizer.sanitize_string(data['first_name'], max_length=100)
        sanitized_last_name = InputSanitizer.sanitize_string(data['last_name'], max_length=100)

        from src.domain.entities import UserRole
        role_mapping = {
            'institutional_admin': UserRole.INSTITUTIONAL_ADMIN,
            'lecturer': UserRole.LECTURER,
            'student': UserRole.STUDENT
        }

        role_enum = role_mapping.get(data['role'])
        if not role_enum:
            SecurityAuditLogger.log_event('invalid_role', f'Invalid role: {data["role"]}', risk_score=30)
            return jsonify({'error': f'Invalid role: {data["role"]}'}), 400

        if not _auth_service:
            return jsonify({'error': 'Authentication service not available'}), 500

        user = _auth_service.register_user(
            email=sanitized_email,
            password=password,
            first_name=sanitized_first_name,
            last_name=sanitized_last_name,
            role=role_enum,
            institution_id=data['institution_id'],
            voucher_code=data.get('voucher_code'),
            student_id=data.get('student_id')
        )

        SecurityAuditLogger.log_event('registration_success',
            f'User registered: {sanitized_email}', risk_score=0)

        return jsonify({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role.value,
            'institution_id': user.institution_id,
            'message': 'Registration successful'
        }), 201

    except ValueError as e:
        logger.warning(f"Registration validation error: {str(e)}")
        return jsonify({'error': 'Invalid registration data'}), 400
    except Exception as e:
        error_msg = str(e).lower()
        if 'firebase' in error_msg and 'credentials' in error_msg:
            return jsonify({'error': 'Service temporarily unavailable'}), 503
        if 'exists' in error_msg:
            return jsonify({'error': 'Email already registered'}), 409
        SecurityAuditLogger.log_event('registration_error',
            f'Registration exception: {str(e)[:200]}', risk_score=50)
        return jsonify({'error': 'Registration failed. Please try again.'}), 500


@auth_bp.route('/signup', methods=['POST'])
@log_access
@require_captcha(action='signup')
@rate_limit_endpoint(limit=5, window=3600, scope='ip', block_duration=900)
def signup():
    return register()


@auth_bp.route('/login', methods=['POST'])
@log_access
@require_captcha(action='login')
@account_security.require_not_locked(identifier_param='email')
@rate_limit_endpoint(limit=10, window=300, scope='ip', block_duration=600)
def login():
    try:
        data = request.get_json()
        if data is None:
            SecurityAuditLogger.log_event('login_invalid_format', 'Invalid JSON body', risk_score=40)
            return jsonify({'success': False, 'message': 'Invalid request format'}), 400

        ok, err = InputSanitizer.validate_json_body(
            data,
            allowed_fields={'email', 'password', 'remember_me', 'device_fingerprint', 'institutionId', 'institution_id'},
            required_fields={'email', 'password'}
        )
        if not ok:
            SecurityAuditLogger.log_event('login_invalid_fields', f'Invalid fields: {err}', risk_score=40)
            return jsonify({'success': False, 'message': err}), 400

        sanitized_email = InputSanitizer.sanitize_email(data.get('email', ''))
        if not sanitized_email or not data.get('password'):
            SecurityAuditLogger.log_event('login_missing_fields', 'Missing email/password', risk_score=40)
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400

        email_rate_key = f'login:{sanitized_email}'
        is_limited, _ = enhanced_rate_limiter.is_limited(key=email_rate_key, limit=5, window=300, block_duration=600)
        if is_limited:
            SecurityAuditLogger.log_event('login_account_limited',
                f'Account rate limited: {sanitized_email}', risk_score=60)
            return jsonify({'success': False, 'message': 'Account temporarily locked. Try again later.'}), 429

        if not _auth_service:
            return jsonify({'success': False, 'message': 'Service temporarily unavailable'}), 500

        result = _auth_service.authenticate_user(
            email=sanitized_email,
            password=data['password'],
            remember_me=data.get('remember_me', False),
            device_fingerprint=data.get('device_fingerprint'),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            institution_id=data.get('institutionId') or data.get('institution_id')
        )

        if result and isinstance(result, dict):
            if result.get('success'):
                SecurityAuditLogger.log_event('login_success',
                    f'Successful login: {sanitized_email}', risk_score=0)
                enhanced_rate_limiter.clear(email_rate_key)
                return jsonify(result), 200
            SecurityAuditLogger.log_event('login_failed',
                f'Failed login attempt: {sanitized_email}', risk_score=50)
            return jsonify(result), 401

        SecurityAuditLogger.log_event('login_failed',
            f'Auth returned no result: {sanitized_email}', risk_score=50)
        return jsonify({'success': False, 'message': 'Authentication failed'}), 401

    except Exception as e:
        SecurityAuditLogger.log_event('login_error',
            f'Exception: {str(e)[:100]}', risk_score=60)
        return jsonify({'success': False, 'message': 'Authentication failed'}), 401


@auth_bp.route('/refresh', methods=['POST'])
@log_access
@rate_limit_endpoint(limit=10, window=900, scope='ip', block_duration=1800)
def refresh_token():
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')

        if not refresh_token:
            return jsonify({'error': 'Refresh token required'}), 400

        result = _auth_service.refresh_token(refresh_token)

        if result:
            return jsonify(result), 200
        else:
            SecurityAuditLogger.log_event('refresh_token_failed',
                'Invalid refresh token', risk_score=50)
            return jsonify({'error': 'Invalid refresh token'}), 401

    except Exception as e:
        SecurityAuditLogger.log_event('refresh_token_error',
            f'Exception: {str(e)[:100]}', risk_score=50)
        return jsonify({'error': 'Token refresh failed'}), 500


@auth_bp.route('/logout', methods=['POST'])
@require_auth
@log_access
def logout():
    try:
        user_id = request.current_user.get('user_id')
        auth_header = request.headers.get('Authorization', '')
        token = (auth_header.replace('Bearer ', '', 1) if auth_header.startswith('Bearer ')
                 else request.cookies.get('auth_token', ''))
        success = _auth_service.logout_user(
            user_id=user_id,
            token=token,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )

        if success:
            SecurityAuditLogger.log_event('logout_success',
                f'User logged out: {user_id}', risk_score=0)
            return jsonify({'message': 'Logged out successfully'}), 200
        else:
            SecurityAuditLogger.log_event('logout_failed',
                f'Logout failed for user: {user_id}', risk_score=30)
            return jsonify({'error': 'Logout failed'}), 500
    except Exception as e:
        SecurityAuditLogger.log_event('logout_error',
            f'Exception: {str(e)[:100]}', risk_score=40)
        return jsonify({'error': 'Logout failed'}), 500


@auth_bp.route('/change-password', methods=['POST'])
@require_auth
@log_access
@rate_limit_endpoint(limit=3, window=3600, scope='user', block_duration=1800)
def change_password():
    try:
        data = request.get_json()
        if not data or not data.get('current_password') or not data.get('new_password'):
            return jsonify({'error': 'current_password and new_password required'}), 400

        new_password = data['new_password']
        pw_valid, pw_error = PasswordPolicy.validate(new_password)
        if not pw_valid:
            SecurityAuditLogger.log_event('weak_password_change',
                f'Weak new password: {pw_error}', risk_score=30)
            return jsonify({'error': pw_error}), 400

        user_id = request.current_user.get('user_id')
        ok = _auth_service.change_password(
            user_id=user_id,
            current_password=data['current_password'],
            new_password=new_password
        )
        if ok:
            SecurityAuditLogger.log_event('password_changed',
                f'Password changed for user {user_id}', risk_score=0)
            return jsonify({'message': 'Password changed successfully'}), 200
        else:
            SecurityAuditLogger.log_event('password_change_failed',
                f'Incorrect current password for user {user_id}', risk_score=50)
            return jsonify({'error': 'Current password is incorrect'}), 401
    except Exception as e:
        SecurityAuditLogger.log_event('password_change_error',
            f'Exception for user: {str(e)[:100]}', risk_score=60)
        return jsonify({'error': 'Password change failed'}), 500
