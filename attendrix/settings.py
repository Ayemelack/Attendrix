"""
Attendrix Settings Loader
Dynamically loads settings based on ENVIRONMENT variable
"""
import os
from .base import *

# Environment detection
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development').lower()

# Load environment-specific settings
if ENVIRONMENT == 'production':
    from .production import *
elif ENVIRONMENT == 'staging':
    from .staging import *
else:
    from .development import *

# Ensure environment is set
if 'ENVIRONMENT' not in globals():
    ENVIRONMENT = 'development'

# Log environment startup
import logging
logger = logging.getLogger(__name__)
logger.info(f"Attendrix starting in {ENVIRONMENT} environment")
