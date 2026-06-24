"""
Development settings for Attendrix
"""
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Development Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DEV_DB_NAME', default='attendrix_dev'),
        'USER': config('DEV_DB_USER', default='postgres'),
        'PASSWORD': config('DEV_DB_PASSWORD', default='password'),
        'HOST': config('DEV_DB_HOST', default='localhost'),
        'PORT': config('DEV_DB_PORT', default='5432'),
    }
}

# Email Backend for Development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Debug Toolbar
if 'debug_toolbar' not in INSTALLED_APPS:
    INSTALLED_APPS.append('debug_toolbar')

MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INTERNAL_IPS = ['127.0.0.1']

# Django Extensions
if 'django_extensions' not in INSTALLED_APPS:
    INSTALLED_APPS.append('django_extensions')

# Logging (verbose for development)
LOGGING['handlers']['console']['level'] = 'DEBUG'
LOGGING['loggers']['django']['level'] = 'DEBUG'
if 'loggers' in LOGGING and 'apps' in LOGGING['loggers']:
    LOGGING['loggers']['apps']['level'] = 'DEBUG'

# CORS Settings (relaxed for development)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

CORS_ALLOW_CREDENTIALS = True

# Security Settings (relaxed for development)
SECURE_SSL_REDIRECT = False
SECURE_BROWSER_XSS_FILTER = False
SECURE_CONTENT_TYPE_NOSNIFF = False
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Session Settings (relaxed for development)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Media Files (served by Django in development)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Static Files (served by Django in development)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Celery (sync for development)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Feature Flags (all enabled for development)
ENABLE_GEOLOCATION = True
ENABLE_DEVICE_FINGERPRINTING = True
ENABLE_PREDICTIVE_ANALYTICS = True
ENABLE_GAMIFICATION = True

# API Rate Limiting (relaxed for development)
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '1000/hour',
    'user': '10000/hour'
}

# Cache (dummy cache for development)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Environment indicator
ENVIRONMENT = 'development'
