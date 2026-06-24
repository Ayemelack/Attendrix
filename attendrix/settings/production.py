"""
Production settings for Attendrix
"""
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('PROD_DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('PROD_ALLOWED_HOSTS', default='attendrix.com,www.attendrix.com').split(',')

# Production Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('PROD_DB_NAME', default='attendrix_prod'),
        'USER': config('PROD_DB_USER', default='postgres'),
        'PASSWORD': config('PROD_DB_PASSWORD', default=''),
        'HOST': config('PROD_DB_HOST', default='localhost'),
        'PORT': config('PROD_DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 60,
        },
        'CONN_MAX_AGE': 60,
    }
}

# Email Configuration (production SMTP)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('PROD_EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('PROD_EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('PROD_EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('PROD_EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('PROD_EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('PROD_DEFAULT_FROM_EMAIL', default='noreply@attendrix.com')

# CORS Settings (restrictive)
CORS_ALLOWED_ORIGINS = config('PROD_CORS_ORIGINS', default='https://attendrix.com,https://www.attendrix.com').split(',')

# Security Settings (hardened)
SECURE_SSL_REDIRECT = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Session Settings (secure)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 1 week
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Static Files (production)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media Files (production)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Celery (async for production)
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False

# Cache (Redis for production)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('PROD_REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            }
        }
    }
}

# Logging (production)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"level": "{levelname}", "time": "{asctime}", "module": "{module}", "message": "{message}"}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
        },
        'security': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
        },
        'console': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.security': {
            'handlers': ['console', 'security'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.authentication': {
            'handlers': ['console', 'security'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# API Rate Limiting (production)
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '100/hour',
    'user': '1000/hour'
}

# Feature Flags (controlled via environment)
ENABLE_GEOLOCATION = config('PROD_ENABLE_GEOLOCATION', default=True, cast=bool)
ENABLE_DEVICE_FINGERPRINTING = config('PROD_ENABLE_DEVICE_FINGERPRINTING', default=True, cast=bool)
ENABLE_PREDICTIVE_ANALYTICS = config('PROD_ENABLE_PREDICTIVE_ANALYTICS', default=True, cast=bool)
ENABLE_GAMIFICATION = config('PROD_ENABLE_GAMIFICATION', default=True, cast=bool)

# Analytics and Monitoring
ENABLE_ANALYTICS = config('PROD_ENABLE_ANALYTICS', default=True, cast=bool)
SENTRY_DSN = config('PROD_SENTRY_DSN', default='')

# Sentry Integration
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                transaction_style='url',
                middleware_spans=True,
                signals_spans=True,
            ),
            CeleryIntegration(
                monitor_beat_tasks=True,
                propagate_traces=True,
            ),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
    )

# Environment indicator
ENVIRONMENT = 'production'

# Performance optimizations
CONN_MAX_AGE = 60
TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', [
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]),
]

# Security Headers
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# File Upload Security
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
UPLOAD_FILE_MAX_SIZE = 2 * 1024 * 1024  # 2MB per file

# Database Connection Pooling
DATABASE_POOL_ARGS = {
    'max_overflow': 10,
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Disable debug toolbar and extensions in production
INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in ['debug_toolbar', 'django_extensions']]
MIDDLEWARE = [mw for mw in MIDDLEWARE if 'debug_toolbar' not in mw]
