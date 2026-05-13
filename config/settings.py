import os
from pathlib import Path
from decouple import config

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Load environment file based on environment
ENV_FILE = '.env.dev' if config('ENVIRONMENT', default='development') == 'development' else '.env'
if os.path.exists(ENV_FILE):
    config.search_path = os.path.join(BASE_DIR, ENV_FILE)

class Config:
    """Base configuration class"""
    
    # Basic Flask configuration
    SECRET_KEY = config('SECRET_KEY', default='dev-secret-key')
    DEBUG = config('DEBUG', default=False, cast=bool)
    
    # Environment
    ENVIRONMENT = config('ENVIRONMENT', default='development')
    
    # Firebase configuration
    FIREBASE_CREDENTIALS_PATH = config('FIREBASE_CREDENTIALS_PATH', default='firebase-dev.json')
    FIREBASE_PROJECT_ID = config('FIREBASE_PROJECT_ID', default='attendrix-dev')
    FIREBASE_DATABASE_URL = config('FIREBASE_DATABASE_URL', default='https://attendrix-dev.firebaseio.com')
    USE_MOCK_FIREBASE = config('USE_MOCK_FIREBASE', default='true')
    
    # Database configuration
    DATABASE_URL = config('DATABASE_URL', default='sqlite:///attendrix.db')
    REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
    
    # Security configuration
    JWT_SECRET_KEY = config('JWT_SECRET_KEY', default='jwt-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = config('JWT_ACCESS_TOKEN_EXPIRES', default=3600, cast=int)
    JWT_REFRESH_TOKEN_EXPIRES = config('JWT_REFRESH_TOKEN_EXPIRES', default=86400, cast=int)
    
    # Email configuration
    MAIL_SERVER = config('MAIL_SERVER', default='smtp.gmail.com')
    MAIL_PORT = config('MAIL_PORT', default=587, cast=int)
    MAIL_USE_TLS = config('MAIL_USE_TLS', default=True, cast=bool)
    MAIL_USERNAME = config('MAIL_USERNAME', default='')
    MAIL_PASSWORD = config('MAIL_PASSWORD', default='')
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = config('RATELIMIT_STORAGE_URL', default='redis://localhost:6379/1')
    RATELIMIT_DEFAULT = config('RATELIMIT_DEFAULT', default='200 per day, 50 per hour')
    
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
    
    @staticmethod
    def init_app(app):
        """Initialize application with this configuration"""
        pass

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
        
        # Development-specific initialization
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
        
        # Staging-specific initialization
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
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Production-specific initialization
        import logging
        logging.basicConfig(level=logging.WARNING)
        
        # Sentry integration if DSN is provided
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
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = config('ENVIRONMENT', default='development')
    return config_map.get(env, DevelopmentConfig)
