# Test settings for health check testing with SQLite
# This file should be used only for local testing

import os
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent
BOTS_DIR = BASE_DIR / 'bots' / 'bots'

# Import rest of settings from main settings
import sys
sys.path.insert(0, str(BASE_DIR / 'bots_config'))

# Import all from main settings first
from settings import *

# Override database settings for SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'bots', 'bots', 'db.sqlite3'),
    }
}

# Add health check app to installed apps if not already present
if 'bots' not in INSTALLED_APPS:
    INSTALLED_APPS = list(INSTALLED_APPS) + ['bots']

# Ensure middleware is configured
if not hasattr(sys.modules[__name__], 'MIDDLEWARE'):
    MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]
