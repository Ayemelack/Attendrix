import math
import os
import re
from pathlib import Path
from decouple import config

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Load environment file based on environment
ENV_FILE = '.env.dev' if config('ENVIRONMENT', default='production') == 'development' else '.env'
if os.path.exists(ENV_FILE):
    config.search_path = os.path.join(BASE_DIR, ENV_FILE)


class Config:
    """Base configuration class"""

    # ── Environment variable requirement sets ──────────────────────────────
    REQUIRED_ENV_VARS = ['SECRET_KEY', 'JWT_SECRET_KEY', 'DATABASE_URL']
    PRODUCTION_REQUIRED = [
        'SECRET_KEY',
        'JWT_SECRET_KEY',
        'DATABASE_URL',
        'REDIS_URL',
        'RATELIMIT_STORAGE_URL',
        'FIREBASE_CREDENTIALS_PATH',
        'FIREBASE_PROJECT_ID',
        'FIREBASE_DATABASE_URL',
        'SENTRY_DSN',
        'SMTP_HOST',
        'SMTP_USER',
        'SMTP_PASS',
        'MAIL_FROM',
        'TURNSTILE_SITE_KEY',
        'TURNSTILE_SECRET_KEY',
        'CLOUDFLARE_TURNSTILE_SITE_KEY',
        'CLOUDFLARE_TURNSTILE_SECRET_KEY',
        'SECURITY_ALERT_WEBHOOK',
        'BOOTSTRAP_ADMIN_PASSWORD',
    ]

    # Basic Flask configuration
    SECRET_KEY = config('SECRET_KEY', default='')
    DEBUG = config('DEBUG', default=False, cast=bool)

    # Environment
    ENVIRONMENT = config('ENVIRONMENT', default='production')

    # Firebase configuration
    FIREBASE_CREDENTIALS_PATH = config('FIREBASE_CREDENTIALS_PATH', default='firebase-dev.json')
    FIREBASE_PROJECT_ID = config('FIREBASE_PROJECT_ID', default='attendrix-dev')
    FIREBASE_DATABASE_URL = config('FIREBASE_DATABASE_URL', default='https://attendrix-dev.firebaseio.com')
    USE_MOCK_FIREBASE = config('USE_MOCK_FIREBASE', default='true')

    # Database configuration
    DATABASE_URL = config('DATABASE_URL', default='sqlite:///attendrix.db')
    SQLALCHEMY_DATABASE_URI = config('SQLALCHEMY_DATABASE_URI', default=DATABASE_URL)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

    # Redis session support
    REDIS_SESSION_ENABLED = config('REDIS_SESSION_ENABLED', default=False, cast=bool)

    # Security configuration
    JWT_SECRET_KEY = config('JWT_SECRET_KEY', default='')
    JWT_ACCESS_TOKEN_EXPIRES = config('JWT_ACCESS_TOKEN_EXPIRES', default=3600, cast=int)
    JWT_REFRESH_TOKEN_EXPIRES = config('JWT_REFRESH_TOKEN_EXPIRES', default=86400, cast=int)

    # Email configuration (legacy SMTP)
    MAIL_SERVER = config('MAIL_SERVER', default='smtp.gmail.com')
    MAIL_PORT = config('MAIL_PORT', default=587, cast=int)
    MAIL_USE_TLS = config('MAIL_USE_TLS', default=True, cast=bool)
    MAIL_USERNAME = config('MAIL_USERNAME', default='')
    MAIL_PASSWORD = config('MAIL_PASSWORD', default='')

    # SMTP transactional email configuration
    SMTP_HOST = config('SMTP_HOST', default='')
    SMTP_PORT = config('SMTP_PORT', default=587, cast=int)
    SMTP_USER = config('SMTP_USER', default='')
    SMTP_PASS = config('SMTP_PASS', default='')
    SMTP_USE_TLS = config('SMTP_USE_TLS', default=True, cast=bool)
    MAIL_FROM = config('MAIL_FROM', default='demo@lamela.com')
    MAIL_FROM_NAME = config('MAIL_FROM_NAME', default='Attendrix')

    # Email authentication (SPF / DKIM / DMARC)
    SPF_DOMAIN = config('SPF_DOMAIN', default='')
    DKIM_ENABLED = config('DKIM_ENABLED', default=False, cast=bool)
    DMARC_POLICY = config('DMARC_POLICY', default='none')

    # Resend transactional email API (fallback)
    RESEND_API_KEY = config('RESEND_API_KEY', default='')
    RESEND_FROM_EMAIL = config('RESEND_FROM_EMAIL', default='demo@lamela.com')
    RESEND_FROM_NAME = config('RESEND_FROM_NAME', default='Attendrix')
    EMAIL_ENABLED = config('EMAIL_ENABLED', default=False, cast=bool)

    # Rate limiting
    RATELIMIT_STORAGE_URL = config('RATELIMIT_STORAGE_URL', default='redis://localhost:6379/1')
    RATELIMIT_DEFAULT = config('RATELIMIT_DEFAULT', default='200 per day, 50 per hour')

    # Persistent (database-backed) rate limit
    PERSISTENT_RATE_LIMIT = config('PERSISTENT_RATE_LIMIT', default=False, cast=bool)

    # File upload configuration
    MAX_CONTENT_LENGTH = config('MAX_CONTENT_LENGTH', default=16777216, cast=int)  # 16MB
    UPLOAD_FOLDER = config('UPLOAD_FOLDER', default='uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

    # Analytics and monitoring
    SENTRY_DSN = config('SENTRY_DSN', default='')
    LOG_LEVEL = config('LOG_LEVEL', default='INFO')

    # Geolocation configuration
    GOOGLE_GEOCODING_API_KEY = config('GOOGLE_GEOCODING_API_KEY', default='')
    DEFAULT_GEOLOCATION_RADIUS = config('DEFAULT_GEOLOCATION_RADIUS', default=100, cast=int)

    # GeoIP resolution
    GEOIP_ENABLED = config('GEOIP_ENABLED', default=False, cast=bool)
    GEOIP_DATABASE_PATH = config('GEOIP_DATABASE_PATH', default='')

    # Geolocation enforcement
    GEOLOCATION_ENFORCED = config('GEOLOCATION_ENFORCED', default=False, cast=bool)

    # Third-party threat-intelligence APIs
    ABUSEIPDB_API_KEY = config('ABUSEIPDB_API_KEY', default='')
    IPQUALITY_API_KEY = config('IPQUALITY_API_KEY', default='')

    # Attendance configuration
    DEFAULT_ATTENDANCE_THRESHOLD = config('DEFAULT_ATTENDANCE_THRESHOLD', default=75, cast=int)
    SESSION_TIMEOUT_MINUTES = config('SESSION_TIMEOUT_MINUTES', default=15, cast=int)
    MAX_LATE_MINUTES = config('MAX_LATE_MINUTES', default=10, cast=int)

    # Cache configuration
    CACHE_TYPE = config('CACHE_TYPE', default='redis')
    CACHE_REDIS_URL = config('CACHE_REDIS_URL', default='redis://localhost:6379/2')

    # Celery configuration
    CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/3')
    CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/4')

    # CAPTCHA provider and keys
    CAPTCHA_PROVIDER = config('CAPTCHA_PROVIDER', default='turnstile')  # 'turnstile' or 'recaptcha'
    TURNSTILE_SITE_KEY = config('TURNSTILE_SITE_KEY', default='')
    TURNSTILE_SECRET_KEY = config('TURNSTILE_SECRET_KEY', default='')
    RECAPTCHA_SITE_KEY = config('RECAPTCHA_SITE_KEY', default='')
    RECAPTCHA_SECRET_KEY = config('RECAPTCHA_SECRET_KEY', default='')

    # Password policy
    PASSWORD_MIN_LENGTH = config('PASSWORD_MIN_LENGTH', default=8, cast=int)
    PASSWORD_REQUIRE_UPPER = config('PASSWORD_REQUIRE_UPPER', default=True, cast=bool)
    PASSWORD_REQUIRE_LOWER = config('PASSWORD_REQUIRE_LOWER', default=True, cast=bool)
    PASSWORD_REQUIRE_DIGIT = config('PASSWORD_REQUIRE_DIGIT', default=True, cast=bool)
    PASSWORD_REQUIRE_SPECIAL = config('PASSWORD_REQUIRE_SPECIAL', default=True, cast=bool)
    PASSWORD_MAX_AGE_DAYS = config('PASSWORD_MAX_AGE_DAYS', default=90, cast=int)
    PASSWORD_HISTORY_SIZE = config('PASSWORD_HISTORY_SIZE', default=5, cast=int)
    PASSWORD_LOCKOUT_THRESHOLD = config('PASSWORD_LOCKOUT_THRESHOLD', default=5, cast=int)
    PASSWORD_LOCKOUT_MINUTES = config('PASSWORD_LOCKOUT_MINUTES', default=15, cast=int)

    # Password reset
    PASSWORD_RESET_EXPIRY = config('PASSWORD_RESET_EXPIRY', default=3600, cast=int)

    # CSRF protection
    CSRF_TOKEN_EXPIRY = config('CSRF_TOKEN_EXPIRY', default=3600, cast=int)
    CSRF_TOKEN_BYTES = config('CSRF_TOKEN_BYTES', default=32, cast=int)

    # Rate limiting (enhanced)
    RATE_LIMIT_WINDOW = config('RATE_LIMIT_WINDOW', default=60, cast=int)
    RATE_LIMIT_IP_THRESHOLD = config('RATE_LIMIT_IP_THRESHOLD', default=100, cast=int)
    RATE_LIMIT_LOGIN_THRESHOLD = config('RATE_LIMIT_LOGIN_THRESHOLD', default=10, cast=int)
    RATE_LIMIT_REGISTER_THRESHOLD = config('RATE_LIMIT_REGISTER_THRESHOLD', default=5, cast=int)
    RATE_LIMIT_BLOCK_DURATION = config('RATE_LIMIT_BLOCK_DURATION', default=300, cast=int)

    # Session security
    SESSION_COOKIE_NAME = config('SESSION_COOKIE_NAME', default='attendrix_session')
    SESSION_COOKIE_PATH = config('SESSION_COOKIE_PATH', default='/')
    SESSION_COOKIE_DOMAIN = config('SESSION_COOKIE_DOMAIN', default=None)

    # Persistent session TTL
    PERSISTENT_SESSION_TTL = config('PERSISTENT_SESSION_TTL', default=86400, cast=int)

    # Security headers
    HSTS_MAX_AGE = config('HSTS_MAX_AGE', default=31536000, cast=int)
    HSTS_INCLUDE_SUBDOMAINS = config('HSTS_INCLUDE_SUBDOMAINS', default=True, cast=bool)
    CSP_DEFAULT_SRC = config('CSP_DEFAULT_SRC', default="'self'")
    CSP_SCRIPT_SRC = config('CSP_SCRIPT_SRC', default="'self' 'strict-dynamic' 'unsafe-inline' https://cdnjs.cloudflare.com https://maxcdn.bootstrapcdn.com https://challenges.cloudflare.com https://www.google.com https://www.gstatic.com")
    CSP_STYLE_SRC = config('CSP_STYLE_SRC', default="'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://maxcdn.bootstrapcdn.com https://fonts.googleapis.com")
    CSP_FONT_SRC = config('CSP_FONT_SRC', default="'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com https://maxcdn.bootstrapcdn.com")
    CSP_IMG_SRC = config('CSP_IMG_SRC', default="'self' data: blob: https: http:")

    # HSTS / CSP feature flags
    FORCE_HTTPS = config('FORCE_HTTPS', default=False, cast=bool)
    HSTS_ENABLED = config('HSTS_ENABLED', default=True, cast=bool)
    CSP_ENABLED = config('CSP_ENABLED', default=True, cast=bool)

    # Multi-factor authentication
    MFA_REQUIRED_FOR = config('MFA_REQUIRED_FOR', default='super_admin,institutional_admin')

    # Device trust
    DEVICE_TRUST_ENABLED = config('DEVICE_TRUST_ENABLED', default=False, cast=bool)

    # Audit logging
    AUDIT_LOG_ENABLED = config('AUDIT_LOG_ENABLED', default=True, cast=bool)
    AUDIT_LOG_RETENTION_DAYS = config('AUDIT_LOG_RETENTION_DAYS', default=365, cast=int)

    # Security monitoring
    SECURITY_MONITORING_ENABLED = config('SECURITY_MONITORING_ENABLED', default=False, cast=bool)
    SECURITY_ALERT_EMAIL = config('SECURITY_ALERT_EMAIL', default='')
    SECURITY_ALERT_WEBHOOK = config('SECURITY_ALERT_WEBHOOK', default='')

    # IP blocklist (comma-separated CIDR or IPs)
    IP_BLOCKLIST = config('IP_BLOCKLIST', default='')

    # Cloudflare configuration
    CLOUDFLARE_TURNSTILE_SITE_KEY = config('CLOUDFLARE_TURNSTILE_SITE_KEY', default='')
    CLOUDFLARE_TURNSTILE_SECRET_KEY = config('CLOUDFLARE_TURNSTILE_SECRET_KEY', default='')
    CLOUDFLARE_API_TOKEN = config('CLOUDFLARE_API_TOKEN', default='')
    CLOUDFLARE_ZONE_ID = config('CLOUDFLARE_ZONE_ID', default='')
    CLOUDFLARE_ACCOUNT_ID = config('CLOUDFLARE_ACCOUNT_ID', default='')
    CLOUDFLARE_ACCESS_TEAM_NAME = config('CLOUDFLARE_ACCESS_TEAM_NAME', default='')
    CLOUDFLARE_ACCESS_AUDIENCE_TAG = config('CLOUDFLARE_ACCESS_AUDIENCE_TAG', default='')
    CLOUDFLARE_BOT_SCORE_THRESHOLD = config('CLOUDFLARE_BOT_SCORE_THRESHOLD', default=30, cast=int)
    CLOUDFLARE_CHALLENGE_PASSED_TTL = config('CLOUDFLARE_CHALLENGE_PASSED_TTL', default=1800, cast=int)
    CLOUDFLARE_SECURITY_LEVEL = config('CLOUDFLARE_SECURITY_LEVEL', default='high')
    CLOUDFLARE_CHALLENGE_TTL = config('CLOUDFLARE_CHALLENGE_TTL', default=1800, cast=int)
    APPLICATION_URL = config('APPLICATION_URL', default='https://attendrix.app')
    ADMIN_URL = config('ADMIN_URL', default='https://admin.attendrix.app')
    API_URL = config('API_URL', default='https://api.attendrix.app')
    BOOTSTRAP_ADMIN_PASSWORD = config('BOOTSTRAP_ADMIN_PASSWORD', default='')

    # Demo and onboarding configuration
    DEMO_SESSION_EXPIRY_MINUTES = config('DEMO_SESSION_EXPIRY_MINUTES', default=60, cast=int)
    DEMO_BOOKING_WINDOW_DAYS = config('DEMO_BOOKING_WINDOW_DAYS', default=30, cast=int)
    DEMO_TRIAL_DURATION_DAYS = config('DEMO_TRIAL_DURATION_DAYS', default=14, cast=int)

    # Application URLs
    APPLICATION_ROOT = '/'
    PREFERRED_URL_SCHEME = 'https'

    # Session configuration
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # CORS configuration
    CORS_ORIGINS = ['http://localhost:3000', 'http://localhost:5000']

    # Pagination
    POSTS_PER_PAGE = 20

    # ── Secret validation ──────────────────────────────────────────────────

    @staticmethod
    def _validate_secret(key_name, key_value, min_entropy=128, min_length=32):
        """Validate a secret key meets minimum entropy and length requirements.

        Returns (is_valid: bool, error_message: str).
        """
        if not key_value:
            return (False, f"{key_name} is not set")

        if len(key_value) < min_length:
            return (
                False,
                f"{key_name} is too short ({len(key_value)} chars). "
                f"Minimum {min_length} characters required.",
            )

        # Reject common placeholder patterns
        _placeholders = [
            'must-set-', 'change-me', 'your-', 'change',
            'default', 'changethis', 'secret',
        ]
        lower_val = key_value.lower()
        for pattern in _placeholders:
            if pattern in lower_val:
                return (
                    False,
                    f"{key_name} contains common placeholder pattern '{pattern}'",
                )

        # Estimate entropy from character-set diversity
        char_set_size = len(set(key_value))
        if char_set_size <= 1:
            return (False, f"{key_name} has insufficient character diversity")

        entropy = len(key_value) * math.log2(char_set_size)
        if entropy < min_entropy:
            return (
                False,
                f"{key_name} has insufficient entropy ({entropy:.1f} bits). "
                f"Minimum {min_entropy} bits required.",
            )

        return (True, "")

    # ── Production-readiness validation ────────────────────────────────────

    @classmethod
    def validate_production_readiness(cls):
        """Validate all production configuration settings.

        Returns a dictionary of ``{setting_name: status}`` where *status* is
        ``'pass'``, ``'fail'``, or ``'warning'``.
        """
        results = {}

        # Basic non-empty check for every var in PRODUCTION_REQUIRED
        for var in cls.PRODUCTION_REQUIRED:
            value = getattr(cls, var, None)
            results[var] = 'pass' if value else 'fail'

        # Deep entropy / pattern validation for critical secrets
        for key_name, min_entropy, min_length in [
            ('SECRET_KEY', 128, 32),
            ('JWT_SECRET_KEY', 256, 64),
        ]:
            is_valid, _ = cls._validate_secret(
                key_name,
                getattr(cls, key_name, ''),
                min_entropy=min_entropy,
                min_length=min_length,
            )
            results[key_name] = 'pass' if is_valid else 'fail'

        # CAPTCHA keys – warn if the active provider is unconfigured
        captcha_provider = getattr(cls, 'CAPTCHA_PROVIDER', 'turnstile')
        if captcha_provider == 'turnstile':
            has_turnstile = bool(cls.TURNSTILE_SITE_KEY and cls.TURNSTILE_SECRET_KEY)
            has_cloudflare = bool(
                cls.CLOUDFLARE_TURNSTILE_SITE_KEY
                and cls.CLOUDFLARE_TURNSTILE_SECRET_KEY
            )
            results['CAPTCHA'] = 'pass' if (has_turnstile or has_cloudflare) else 'warning'
        elif captcha_provider == 'recaptcha':
            has_recaptcha = bool(cls.RECAPTCHA_SITE_KEY and cls.RECAPTCHA_SECRET_KEY)
            results['CAPTCHA'] = 'pass' if has_recaptcha else 'warning'

        # Email – warn when EMAIL_ENABLED but neither SMTP nor Resend is ready
        if cls.EMAIL_ENABLED:
            has_smtp = bool(cls.SMTP_HOST and cls.SMTP_USER and cls.SMTP_PASS)
            has_resend = bool(cls.RESEND_API_KEY)
            results['EMAIL'] = 'pass' if (has_smtp or has_resend) else 'warning'

        return results

    # ── Application initialisation ─────────────────────────────────────────

    @staticmethod
    def init_app(app):
        """Initialize application with this configuration.

        Map Cloudflare-specific Turnstile environment variables into the
        generic ``TURNSTILE_*`` config keys so templates and verification code
        use the production values without changing other code.
        """
        site = app.config.get('CLOUDFLARE_TURNSTILE_SITE_KEY') or app.config.get('TURNSTILE_SITE_KEY')
        secret = app.config.get('CLOUDFLARE_TURNSTILE_SECRET_KEY') or app.config.get('TURNSTILE_SECRET_KEY')
        if site:
            app.config['TURNSTILE_SITE_KEY'] = site
        if secret:
            app.config['TURNSTILE_SECRET_KEY'] = secret


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

    # Development database
    DATABASE_URL = config('DATABASE_URL', default='sqlite:///attendrix_dev.db')

    # Development logging
    LOG_LEVEL = 'DEBUG'

    # Development security (relaxed)
    SESSION_COOKIE_SECURE = False

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        import logging
        logging.basicConfig(level=logging.DEBUG)


class StagingConfig(Config):
    """Staging configuration"""
    DEBUG = False
    TESTING = True

    # Staging database
    DATABASE_URL = config('DATABASE_URL', default='postgresql://user:password@localhost:5432/attendrix_staging')

    # Staging logging
    LOG_LEVEL = 'INFO'

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        import logging
        logging.basicConfig(level=logging.INFO)


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

    # Production database
    DATABASE_URL = config('DATABASE_URL', default='postgresql://user:password@localhost:5432/attendrix_prod')

    # Production logging
    LOG_LEVEL = 'WARNING'

    # Production security (strict)
    SESSION_COOKIE_SECURE = True
    USE_MOCK_FIREBASE = False

    # Override bootstrap password default — must be explicitly set in env
    BOOTSTRAP_ADMIN_PASSWORD = config('BOOTSTRAP_ADMIN_PASSWORD', default='')

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        import logging
        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.WARNING)

        # ── Production-readiness gate ──────────────────────────────────────
        validation_results = cls.validate_production_readiness()

        critical_failures = []
        for setting, status in validation_results.items():
            if status == 'fail':
                msg = f"Production config check FAILED: {setting} is missing or invalid"
                logger.warning(msg)
                if setting in cls.REQUIRED_ENV_VARS:
                    critical_failures.append(msg)
            elif status == 'warning':
                logger.warning(
                    f"Production config check WARNING: {setting} is not configured"
                )

        if critical_failures:
            raise RuntimeError(
                "Critical production configuration errors:\n"
                + "\n".join(critical_failures)
            )

        # ── Sentry integration ─────────────────────────────────────────────
        if cls.SENTRY_DSN:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(
                dsn=cls.SENTRY_DSN,
                integrations=[FlaskIntegration()],
                traces_sample_rate=1.0,
            )


# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'default': ProductionConfig,
}


def get_config():
    """Get configuration based on environment"""
    env = config('ENVIRONMENT', default='production')
    return config_map.get(env, ProductionConfig)
