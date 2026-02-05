# -*- coding: utf-8 -*-
"""Django settings for bots project."""

import os
import platform

import bots
from bots.botsinit import BotsConfig # type: ignore


BOTS_PATH = bots.__path__[0]

# BOTSENV
BOTSENV = os.environ.get("BOTSENV") or "default"
BOTS_CONFIG_DIR = os.path.dirname(__file__)
BOTSENV_PATH = os.path.dirname(BOTS_CONFIG_DIR)

# BOTSSYS
config = BotsConfig()
config.read(os.path.join(BOTS_CONFIG_DIR, 'bots.ini'))
BOTSSYS = config.get('directories', 'botssys', 'botssys')
if os.path.sep not in BOTSSYS:
    # Set absolute botssys path from botsenv path
    BOTSSYS = os.path.join(BOTSENV_PATH, BOTSSYS)

HOSTNAME = platform.node()

# *******settings for sending bots error reports via email**********************************
MANAGERS = (
    ('admin', os.environ.get('ADMIN_EMAIL', 'services@pleasantmattress.com')),
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'relay.pminc.me')
EMAIL_PORT = os.environ.get('EMAIL_PORT', '25')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', f'edi-{BOTSENV}@pleasantmattress.com')

# *********database settings*************************
# Database configuration from environment variables
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'botsedi_data'),
        'USER': os.environ.get('DB_USER', 'botsedi'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'kona.db.pminc.me'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}

# SQLite database (alternative for development/testing)
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': os.path.join(BOTSSYS, 'sqlitedb', 'botsdb'),
#         "OPTIONS": {
#             "init_command": "PRAGMA synchronous=OFF;",
#             "transaction_mode": "EXCLUSIVE",
#             "timeout": 99.0,
#         },
#     }
# }

# PostgreSQL (alternative)
# DATABASES = {
#     'default': {
#         "ENGINE": "django.db.backends.postgresql",
#         'NAME': os.environ.get('DB_NAME', 'botsdb'),
#         'USER': os.environ.get('DB_USER', 'bots'),
#         'PASSWORD': os.environ.get('DB_PASSWORD', ''),
#         'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
#         'PORT': os.environ.get('DB_PORT', '5432'),
#         "OPTIONS": {
#             "client_encoding": "utf-8",
#         },
#     }
# }

# *********setting date/time zone and formats *************************
# Local time zone from environment or default
TIME_ZONE = os.environ.get('TZ', 'America/Los_Angeles')
# Bots engine always use localtime
USE_TZ = True

# ******language code/internationalization*************************
LANGUAGE_CODE = 'en-us'
USE_I18N = True

# *************************************************************************
# *********other django setting. please consult django docs.***************
# *************************************************************************
# *************************************************************************

# *********path settings*************************
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BOTSSYS, 'static')
ROOT_URLCONF = 'bots.urls'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/bots/home'
LOGOUT_URL = '/logout/'
# LOGOUT_REDIRECT_URL = # not such parameter; is set in urls.py
ALLOWED_HOSTS = ['*']

# *********sessions, cookies, l_PATH, 'staticfiles')
MEDIA_ROOT = os.path.join(BOTSSYS, 'media')
MEDIA_URL = '/media/'

ROOT_URLCONF = 'bots.urls'
WSGI_APPLICATION = 'bots.wsgi.application'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/bots/home'
LOGOUT_URL = '/logout/'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# CSRF trusted origins for modern Django (4.0+)
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'https://edi.k8.pminc.me,https://edi-dev.k8.pminc.me,https://edi-staging.k8.pminc.me'
).split(',')

# *********sessions, cookies, log out time*************************
SESSION_EXPIRE_AT_BROWSER_CLOSE = True    # True: always log in when browser is closed
SESSION_COOKIE_AGE = 3600                 # seconds a user needs to login when no activity
SESSION_SAVE_EVERY_REQUEST = True         # if True: SESSION_COOKIE_AGE is interpreted as: since last activity
SESSION_COOKIE_NAME = f"bots_sessionid_{BOTSENV}"
CSRF_COOKIE_NAME = f"bots_csrftoken_{BOTSENV}"

# Security settings
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'm@-u37qiujmeqfbu$daaaaz)sp^7an4u@h=wfx9dd$$$zl2i*x9#awojdc')
SITE_ID = 1

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# save uploaded file (=plugin) always to file. no path for temp storage is used, so system default is used.
FILE_UPLOAD_HANDLERS = (
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bots',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BOTS_PATH, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'bots.bots_context.set_context',
            ],
        },
    },
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'bots': {
            'handlers': ['console'],
            'level': os.environ.get('BOTS_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
