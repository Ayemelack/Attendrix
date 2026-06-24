"""
Staging settings for Attendrix
"""
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('STAGING_DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('STAGING_ALLOWED_HOSTS', default='staging.attendrix.com,localhost,127.0.0.1').split(',')

# Staging Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('STAGING_DB_NAME', default='attendrix_staging'),
        'USER': config('STAGING_DB_USER', default='postgres'),
        'PASSWORD': config('STAGING_DB_PASSWORD', default=''),
        'HOST': config('STAGING_DB_HOST', default='localhost'),
        'PORT': config('STAGING_DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 60,
        },
    }
}

# Email Configuration (using console for staging, can be overridden)
EMAIL_BACKEND = config('STAGING_EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')

# CORS Settings
CORS_ALLOWED_ORIGINS = config('STAGING_CORS_ORIGINS', default='https://staging.attendrix.com,http://localhost:3000').split(',')

# Security Settings (production-like)
SECURE_SSL_REDIRECT = config('STAGING_SSL_REDIRECT', default=True, cast=bool)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = config('STAGING_HSTS_SECONDS', default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Session Settings (secure)
SESSION_COOKIE_SECURE = config('STAGING_SESSION_SECURE', default=True, cast=bool)
CSRF_COOKIE_SECURE = config('STAGING_CSRF_SECURE', default=True, cast=bool)

# Static Files (production-like)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media Files (production-like)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Celery (async for staging)
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False

# Cache (Redis for staging)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('STAGING_REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Logging (production-like)
LOGGING['handlers']['console']['level'] = 'INFO'
LOGGING['loggers']['django']['level'] = 'INFO'
LOGGING['loggers']['apps']['level'] = 'INFO'

# API Rate Limiting (production-like)
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '100/hour',
    'user': '1000/hour'
}

# Feature Flags (can be controlled via environment)
ENABLE_GEOLOCATION = config('STAGING_ENABLE_GEOLOCATION', default=True, cast=bool)
ENABLE_DEVICE_FINGERPRINTING = config('STAGING_ENABLE_DEVICE_FINGERPRINTING', default=True, cast=bool)
ENABLE_PREDICTIVE_ANALYTICS = config('STAGING_ENABLE_PREDICTIVE_ANALYTICS', default=True, cast=bool)
ENABLE_GAMIFICATION = config('STAGING_ENABLE_GAMIFICATION', default=True, cast=bool)

# Analytics and Monitoring
ENABLE_ANALYTICS = config('STAGING_ENABLE_ANALYTICS', default=True, cast=bool)
SENTRY_DSN = config('STAGING_SENTRY_DSN', default='')

# Environment indicator
ENVIRONMENT = 'staging'

# Testing Configuration
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Additional middleware for staging
if 'debug_toolbar' not in INSTALLED_APPS and DEBUG:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']
