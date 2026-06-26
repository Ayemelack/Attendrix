"""
SECURITY INTEGRATION MODULE
Attendrix distributed attendance system

Central integration point for all security systems into Flask application.
Configures and initializes all security modules.
"""

import logging
from typing import Optional
from flask import Flask, g, request

logger = logging.getLogger(__name__)


class SecurityManager:
    """Central security manager - initializes and coordinates all security systems."""

    def __init__(self, app: Optional[Flask] = None):
        """Initialize security manager."""
        self.app = app
        self.geolocation_validator = None
        self.network_validator = None
        self.device_analyzer = None
        self.session_manager = None
        self.attendance_manager = None
        self.offline_sync_manager = None
        self.account_isolation_manager = None
        self.admin_security_manager = None

        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize all security subsystems in Flask app."""
        from src.infrastructure.security import (
            GeolocationValidator,
            NetworkSecurityValidator,
            CampusNetworkValidator,
            DeviceFingerprintAnalyzer,
            SessionManager,
            AttendanceSessionManager,
            OfflineSyncSecurityManager,
            NewAccountIsolationManager,
            AdminSecurityManager,
            apply_production_hardening,
        )

        self.app = app

        # Initialize security managers as singletons
        self.geolocation_validator = GeolocationValidator()
        self.network_validator = NetworkSecurityValidator()
        self.device_analyzer = DeviceFingerprintAnalyzer()
        self.session_manager = SessionManager(
            token_ttl_seconds=app.config.get('SESSION_TTL_SECONDS', 3600),
            inactivity_timeout_seconds=app.config.get('SESSION_INACTIVITY_TIMEOUT', 900),
        )
        self.attendance_manager = AttendanceSessionManager(
            session_duration_seconds=app.config.get('ATTENDANCE_SESSION_DURATION', 600),
        )
        self.offline_sync_manager = OfflineSyncSecurityManager()
        self.account_isolation_manager = NewAccountIsolationManager()
        self.admin_security_manager = AdminSecurityManager()

        # Store in app extensions
        if not hasattr(app, 'extensions'):
            app.extensions = {}

        app.extensions['security_manager'] = self
        app.extensions['geolocation_validator'] = self.geolocation_validator
        app.extensions['network_validator'] = self.network_validator
        app.extensions['device_analyzer'] = self.device_analyzer
        app.extensions['session_manager'] = self.session_manager
        app.extensions['attendance_manager'] = self.attendance_manager
        app.extensions['offline_sync_manager'] = self.offline_sync_manager
        app.extensions['account_isolation_manager'] = self.account_isolation_manager
        app.extensions['admin_security_manager'] = self.admin_security_manager

        # Register before/after request handlers
        self._register_security_handlers(app)

        # Apply production hardening
        apply_production_hardening(app)

        logger.info('Security manager initialized and all subsystems loaded')

    def _register_security_handlers(self, app: Flask):
        """Register Flask before/after request handlers."""

        @app.before_request
        def security_before_request():
            """Security checks before each request."""
            # Store request metadata in g for later access
            g.request_start_time = __import__('time').time()
            g.request_ip = self._get_client_ip()

            # Network validation (optional based on config)
            if app.config.get('REQUIRE_RESIDENTIAL_NETWORK', False):
                is_valid, error, reputation = self.network_validator.validate_network(
                    g.request_ip,
                    require_residential=True,
                )
                if not is_valid:
                    logger.warning(f'Network validation failed: {error}')
                    return {'error': True, 'message': error}, 403

            # Log suspicious patterns
            from src.infrastructure.security import ProductionHardeningManager
            ProductionHardeningManager.log_suspicious_request(request)

        @app.after_request
        def security_after_request(response):
            """Security processing after each request."""
            # Calculate request duration
            if hasattr(g, 'request_start_time'):
                duration = __import__('time').time() - g.request_start_time
                response.headers['X-Response-Time'] = f"{duration:.3f}s"

            # Clean up session expired records (background maintenance)
            if hasattr(self, 'session_manager') and __import__('random').random() < 0.01:
                self.session_manager.cleanup_expired_sessions()

            if hasattr(self, 'attendance_manager') and __import__('random').random() < 0.01:
                self.attendance_manager.cleanup_expired_sessions()

            return response

    def _get_client_ip(self) -> str:
        """Get client IP from request."""
        if request:
            if 'CF-Connecting-IP' in request.headers:
                return request.headers['CF-Connecting-IP']
            if 'X-Forwarded-For' in request.headers:
                return request.headers['X-Forwarded-For'].split(',')[0].strip()
            return request.remote_addr or '127.0.0.1'
        return '127.0.0.1'

    def get_geolocation_validator(self):
        """Get geolocation validator instance."""
        return self.geolocation_validator

    def get_network_validator(self):
        """Get network validator instance."""
        return self.network_validator

    def get_device_analyzer(self):
        """Get device analyzer instance."""
        return self.device_analyzer

    def get_session_manager(self):
        """Get session manager instance."""
        return self.session_manager

    def get_attendance_manager(self):
        """Get attendance session manager instance."""
        return self.attendance_manager

    def get_offline_sync_manager(self):
        """Get offline sync manager instance."""
        return self.offline_sync_manager

    def get_account_isolation_manager(self):
        """Get account isolation manager instance."""
        return self.account_isolation_manager

    def get_admin_security_manager(self):
        """Get admin security manager instance."""
        return self.admin_security_manager


# Convenience function for Flask initialization
def init_security(app: Flask) -> SecurityManager:
    """
    Initialize comprehensive security for Flask app.
    
    Usage:
        from src.infrastructure.security.integration import init_security
        
        app = Flask(__name__)
        security = init_security(app)
    """
    manager = SecurityManager(app)
    logger.info('Attendrix security infrastructure initialized')
    return manager
