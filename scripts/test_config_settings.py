# -*- coding: utf-8 -*-
"""Test Django settings for local testing with SQLite"""

import os
import platform
import tempfile

import bots
from bots.botsinit import BotsConfig


BOTS_PATH = bots.__path__[0]

# Test environment
BOTSENV = "test"
BOTS_CONFIG_DIR = os.path.dirname(__file__)
BOTSENV_PATH = os.path.dirname(BOTS_CONFIG_DIR)

# BOTSSYS - use temp directory for testing
BOTSSYS = os.path.join(tempfile.gettempdir(), 'bots_test', 'botssys')

# Create test directories
os.makedirs(os.path.join(BOTSSYS, 'sqlitedb'), exist_ok=True)
os.makedirs(os.path.join(BOTSSYS, 'data'), exist_ok=True)
os.makedirs(os.path.join(BOTSSYS, 'logging'), exist_ok=True)

HOSTNAME = platform.node()

# Email settings (not used in tests)
MANAGERS = ()
EMAIL_HOST = 'localhost'
EMAIL_PORT = '25'
EMAIL_USE_TLS = False
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
SERVER_EMAIL = f"test@{HOSTNAME}"

# *********database settings*************************
# SQLite database for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BOTSSYS, 'sqlitedb', 'test-botsdb'),
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
        "OPTIONS": {
            "init_command": "PRAGMA synchronous=OFF;",
            "transaction_mode": "EXCLUSIVE",
            "timeout": 99.0,
        },
    }
}

# *********setting date/time zone and formats *************************
TIME_ZONE = 'America/Los_Angeles'
USE_TZ = False

# ******language code/internationalization*************************
LANGUAGE_CODE = 'en-us'

# *******sessions, cookies************************
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# *******other django settings*******************************
ALLOWED_HOSTS = ['*']  # Test environment
SITE_ID = 1
USE_I18N = True
USE_L10N = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BOTSSYS, 'static')

# Media files  
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BOTSSYS, 'media')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'bots.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.humanize',
    'bots',
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Security settings
SECRET_KEY = "test-secret-key-not-for-production-use-only"
DEBUG = False
