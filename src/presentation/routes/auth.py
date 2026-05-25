"""Authentication route blueprint — register, login, logout, password management."""

import re
import time as _time
from flask import Blueprint, request, jsonify
from src.application.rbac import require_auth, log_access

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_auth_service = None
_rate_limiter = None


def init_auth_routes(auth_service, rate_limiter):
    global _auth_service, _rate_limiter
    _auth_service = auth_service
    _rate_limiter = rate_limiter


@auth_bp.route('/register', methods=['POST'])
@log_access
def register():
    try:
        data = request.get_json()

        required_fields = ['email', 'password', 'first_name', 'last_name', 'role', 'voucher_code', 'institution_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Server-side password validation (redundant security layer)
        if _rate_limiter:
            _client_ip = request.remote_addr or 'unknown'
            if _rate_limiter.get_attempt_count(_client_ip, window=3600) >= 5:
                return jsonify({'error': 'Too many registration attempts. Try again later.'}), 429
        password = data['password']
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        if not re.search(r'[A-Z]', password):
            return jsonify({'error': 'Password must contain at least one uppercase letter'}), 400
        if not re.search(r'[a-z]', password):
            return jsonify({'error': 'Password must contain at least one lowercase letter'}), 400
        if not re.search(r'[0-9]', password):
            return jsonify({'error': 'Password must contain at least one number'}), 400
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-]', password):
            return jsonify({'error': 'Password must contain at least one special character'}), 400

        from src.domain.entities import UserRole
        role_mapping = {
            'institutional_admin': UserRole.INSTITUTIONAL_ADMIN,
            'lecturer': UserRole.LECTURER,
            'student': UserRole.STUDENT
        }

        role_enum = role_mapping.get(data['role'])
        if not role_enum:
            return jsonify({'error': f'Invalid role: {data["role"]}'}), 400

        if not _auth_service:
            return jsonify({'error': 'Authentication service not available'}), 500

        user = _auth_service.register_user(
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            role=role_enum,
            institution_id=data['institution_id'],
            voucher_code=data.get('voucher_code'),
            student_id=data.get('student_id')
        )

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
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        error_msg = str(e).lower()
        if 'firebase' in error_msg and 'credentials' in error_msg:
            return jsonify({'error': 'Service temporarily unavailable'}), 503
        if 'exists' in error_msg:
            return jsonify({'error': 'Email already registered'}), 409
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500


@auth_bp.route('/signup', methods=['POST'])
@log_access
def signup():
    return register()


@auth_bp.route('/login', methods=['POST'])
@log_access
def login():
    try:
        data = request.get_json()
        if data is None:
            return jsonify({'success': False, 'message': 'Invalid request format'}), 400

        if not data.get('email') or not data.get('password'):
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400

        client_ip = request.remote_addr or 'unknown'
        if _rate_limiter:
            _attempts = _rate_limiter.get_attempt_count(client_ip)
            if _attempts >= 10:
                return jsonify({'success': False, 'message': 'Account temporarily locked. Try again later.'}), 429
            elif _attempts >= 5:
                _time.sleep(3)
            elif _attempts >= 3:
                _time.sleep(1)
            if _rate_limiter.is_limited(client_ip):
                return jsonify({'success': False, 'message': 'Too many attempts. Try again later.'}), 429

        if not _auth_service:
            return jsonify({'success': False, 'message': 'Service temporarily unavailable'}), 500

        result = _auth_service.authenticate_user(
            email=data['email'],
            password=data['password'],
            remember_me=data.get('remember_me', False),
            device_fingerprint=data.get('device_fingerprint'),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )

        if result and isinstance(result, dict):
            if result.get('success'):
                if _rate_limiter:
                    _rate_limiter.record_success(client_ip)
                return jsonify(result), 200
            return jsonify(result), 401

        return jsonify({'success': False, 'message': 'Authentication failed'}), 401

    except Exception as e:
        return jsonify({'success': False, 'message': 'Authentication failed'}), 401


@auth_bp.route('/refresh', methods=['POST'])
@log_access
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
            return jsonify({'error': 'Invalid refresh token'}), 401

    except Exception as e:
        return jsonify({'error': 'Token refresh failed'}), 500


@auth_bp.route('/logout', methods=['POST'])
@require_auth
@log_access
def logout():
    try:
        user_id = request.current_user.get('user_id')
        success = _auth_service.logout_user(
            user_id=user_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )

        if success:
            return jsonify({'message': 'Logged out successfully'}), 200
        else:
            return jsonify({'error': 'Logout failed'}), 500
    except Exception as e:
        return jsonify({'error': 'Logout failed'}), 500


@auth_bp.route('/change-password', methods=['POST'])
@require_auth
@log_access
def change_password():
    try:
        data = request.get_json()
        if not data or not data.get('current_password') or not data.get('new_password'):
            return jsonify({'error': 'current_password and new_password required'}), 400

        user_id = request.current_user.get('user_id')
        ok = _auth_service.change_password(
            user_id=user_id,
            current_password=data['current_password'],
            new_password=data['new_password']
        )
        if ok:
            return jsonify({'message': 'Password changed successfully'}), 200
        else:
            return jsonify({'error': 'Current password is incorrect'}), 401
    except Exception as e:
        return jsonify({'error': 'Password change failed'}), 500
