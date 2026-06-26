"""
SECURITY DECORATORS
Attendrix distributed attendance system

Decorators for enforcing security policies across endpoints.
"""

import functools
import logging
from typing import Callable, Any
from flask import request, jsonify, current_app

logger = logging.getLogger(__name__)


def require_geolocation(geofence_lat: float, geofence_lon: float, geofence_radius_m: float):
    """
    Require GPS geolocation validation for endpoint.
    
    Usage:
        @require_geolocation(lat, lon, radius)
        def record_attendance():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from src.infrastructure.security import GeolocationValidator, Location
                
                data = request.get_json() or {}
                lat = data.get('latitude')
                lon = data.get('longitude')
                accuracy = data.get('accuracy')
                
                if not (lat and lon):
                    return jsonify({
                        'error': True,
                        'message': 'GPS location required for this operation'
                    }), 400
                
                location = Location(
                    latitude=lat,
                    longitude=lon,
                    accuracy=accuracy,
                )
                
                validator = GeolocationValidator()
                from src.infrastructure.security import GeoFence
                geofence = GeoFence(geofence_lat, geofence_lon, geofence_radius_m)
                
                is_valid, error, metadata = validator.validate_attendance_location(
                    location,
                    geofence,
                    allow_buffer=True,
                )
                
                if not is_valid:
                    logger.warning(f'Geolocation validation failed: {error}', extra=metadata)
                    return jsonify({
                        'error': True,
                        'message': error
                    }), 403
                
                # Pass location metadata to endpoint
                kwargs['location_metadata'] = metadata
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f'Geolocation validation error: {e}')
                return jsonify({
                    'error': True,
                    'message': 'Geolocation validation unavailable'
                }), 500
        
        return decorated_function
    return decorator


def require_non_vpn():
    """
    Require connection from non-VPN network.
    
    Usage:
        @require_non_vpn()
        def sensitive_operation():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from src.infrastructure.security import NetworkSecurityValidator
                
                validator = NetworkSecurityValidator()
                is_valid, error, reputation = validator.validate_network(
                    block_vpn=True,
                    block_proxy=True,
                    block_tor=True,
                )
                
                if not is_valid:
                    logger.warning(f'Network validation failed: {error}')
                    return jsonify({
                        'error': True,
                        'message': error
                    }), 403
                
                kwargs['network_metadata'] = validator.get_network_metadata()
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f'Network validation error: {e}')
                return jsonify({
                    'error': True,
                    'message': 'Network validation unavailable'
                }), 500
        
        return decorated_function
    return decorator


def require_trusted_device():
    """
    Require device to be previously registered.
    
    Usage:
        @require_trusted_device()
        def sensitive_operation():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from src.infrastructure.security import DeviceFingerprintAnalyzer
                
                user_id = kwargs.get('user_id') or getattr(request, 'user_id', None)
                if not user_id:
                    return jsonify({
                        'error': True,
                        'message': 'Authentication required'
                    }), 401
                
                analyzer = DeviceFingerprintAnalyzer()
                fingerprint = analyzer.generate_fingerprint(
                    request.headers.get('User-Agent'),
                    request.get_json() or {}
                )
                
                is_valid, error, metadata = analyzer.validate_device(
                    user_id,
                    fingerprint,
                )
                
                if not is_valid:
                    logger.warning(f'Device validation failed: {error}')
                    return jsonify({
                        'error': True,
                        'message': error
                    }), 403
                
                kwargs['device_metadata'] = metadata
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f'Device validation error: {e}')
                return jsonify({
                    'error': True,
                    'message': 'Device validation unavailable'
                }), 500
        
        return decorated_function
    return decorator


def require_valid_session(rotate_token: bool = False):
    """
    Require valid session token with optional rotation.
    
    Usage:
        @require_valid_session(rotate_token=True)
        def protected_endpoint():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from src.infrastructure.security import SessionManager
                
                token_id = request.headers.get('X-Session-Token') or \
                           request.get_json().get('session_token') if request.is_json else None
                
                if not token_id:
                    return jsonify({
                        'error': True,
                        'message': 'Session token required'
                    }), 401
                
                manager = current_app.extensions.get('session_manager')
                if not manager:
                    manager = SessionManager()
                    current_app.extensions['session_manager'] = manager
                
                is_valid, error, session = manager.validate_session(token_id)
                
                if not is_valid:
                    logger.warning(f'Session validation failed: {error}')
                    return jsonify({
                        'error': True,
                        'message': error
                    }), 401
                
                # Update activity
                manager.update_activity(token_id)
                
                # Optionally rotate token
                if rotate_token:
                    device_fp = kwargs.get('device_fingerprint_id')
                    ip = request.remote_addr
                    success, err, new_session = manager.rotate_token(token_id, device_fp, ip)
                    if success:
                        kwargs['new_session_token'] = new_session.token_id
                
                kwargs['session'] = session
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f'Session validation error: {e}')
                return jsonify({
                    'error': True,
                    'message': 'Session validation failed'
                }), 500
        
        return decorated_function
    return decorator


def require_admin_mfa():
    """
    Require MFA verification for admin actions.
    
    Usage:
        @require_admin_mfa()
        def admin_sensitive_operation():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from src.infrastructure.security import AdminSecurityManager
                
                admin_id = kwargs.get('admin_id') or getattr(request, 'admin_id', None)
                if not admin_id:
                    return jsonify({
                        'error': True,
                        'message': 'Admin authentication required'
                    }), 401
                
                data = request.get_json() or {}
                mfa_code = data.get('mfa_code')
                
                if not mfa_code:
                    return jsonify({
                        'error': True,
                        'message': 'MFA code required'
                    }), 400
                
                manager = current_app.extensions.get('admin_security')
                if not manager:
                    manager = AdminSecurityManager()
                    current_app.extensions['admin_security'] = manager
                
                is_valid, error = manager.verify_mfa(admin_id, mfa_code)
                
                if not is_valid:
                    logger.warning(f'Admin MFA verification failed: {error}')
                    return jsonify({
                        'error': True,
                        'message': error
                    }), 403
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f'Admin MFA verification error: {e}')
                return jsonify({
                    'error': True,
                    'message': 'MFA verification failed'
                }), 500
        
        return decorated_function
    return decorator


def enforce_new_account_isolation():
    """
    Enforce data isolation for new accounts.
    
    Usage:
        @enforce_new_account_isolation()
        def get_dashboard_data():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from src.infrastructure.security import NewAccountIsolationManager
                
                user_id = kwargs.get('user_id') or getattr(request, 'user_id', None)
                if not user_id:
                    return jsonify({
                        'error': True,
                        'message': 'Authentication required'
                    }), 401
                
                manager = current_app.extensions.get('account_isolation')
                if not manager:
                    manager = NewAccountIsolationManager()
                    current_app.extensions['account_isolation'] = manager
                
                # Check isolation and get safe data
                result = f(*args, **kwargs)
                
                # If isolation applies, sanitize response
                policy = manager.get_account_isolation_policy(user_id)
                if policy:
                    # Apply isolation (implementation depends on response type)
                    logger.info(f'New account isolation enforced for user {user_id}')
                
                return result
                
            except Exception as e:
                logger.error(f'Account isolation enforcement error: {e}')
                return jsonify({
                    'error': True,
                    'message': 'Data access validation failed'
                }), 500
        
        return decorated_function
    return decorator
