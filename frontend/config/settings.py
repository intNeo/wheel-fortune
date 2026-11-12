import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = False
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
INSTALLED_APPS = ['django.contrib.staticfiles', 'wheel']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware',
              'whitenoise.middleware.WhiteNoiseMiddleware',
              'django.middleware.common.CommonMiddleware',
              'wheel.security.SecurityMiddleware',
              'django.middleware.csrf.CsrfViewMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'DIRS': [], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.csrf']}}]
WSGI_APPLICATION = 'config.wsgi.application'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
CSRF_TRUSTED_ORIGINS = list(filter(None, os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')))
CSRF_COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'true').lower() == 'true'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FLASK_API_URL = os.getenv('FLASK_API_URL', 'http://backend:5000')
API_TOKEN = os.environ['API_TOKEN']
LANGUAGE_CODE = 'ru'
USE_TZ = True

# Required secrets; no default access credential.
from wheel.access_tokens import parse_access_tokens
WHEEL_ACCESS_TOKEN = os.getenv('WHEEL_ACCESS_TOKEN', '')
WHEEL_ACCESS_TOKENS = parse_access_tokens(os.getenv('WHEEL_ACCESS_TOKENS', ''), WHEEL_ACCESS_TOKEN)
REDIS_URL = os.environ['REDIS_URL']
REDIS_PREFIX = os.getenv('REDIS_PREFIX', 'fortune')
AUTH_SESSION_SECONDS = int(os.getenv('AUTH_SESSION_SECONDS', '28800'))
REQUESTS_PER_MINUTE = int(os.getenv('REQUESTS_PER_MINUTE', '120'))
LOGIN_ATTEMPTS = int(os.getenv('LOGIN_ATTEMPTS', '5'))
LOGIN_WINDOW_SECONDS = int(os.getenv('LOGIN_WINDOW_SECONDS', '300'))
LOGIN_GLOBAL_PER_MINUTE = int(os.getenv('LOGIN_GLOBAL_PER_MINUTE', '60'))
SPINS_PER_MINUTE = int(os.getenv('SPINS_PER_MINUTE', '10'))
SPIN_BURST_PER_SECOND = int(os.getenv('SPIN_BURST_PER_SECOND', '2'))
SPINS_GLOBAL_PER_MINUTE = int(os.getenv('SPINS_GLOBAL_PER_MINUTE', '60'))
TRUSTED_PROXY_CIDRS = list(filter(None, os.getenv('TRUSTED_PROXY_CIDRS', '').split(',')))
import ipaddress
for cidr in TRUSTED_PROXY_CIDRS:
    ipaddress.ip_network(cidr)
for limit in (AUTH_SESSION_SECONDS, REQUESTS_PER_MINUTE, LOGIN_ATTEMPTS,
              LOGIN_WINDOW_SECONDS, LOGIN_GLOBAL_PER_MINUTE, SPINS_PER_MINUTE,
              SPIN_BURST_PER_SECOND, SPINS_GLOBAL_PER_MINUTE):
    if limit <= 0:
        raise ValueError('Session duration and rate limits must be positive')
DATA_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024
CSRF_COOKIE_SAMESITE = 'Strict'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'wheel.security': {'handlers': ['console'], 'level': 'INFO', 'propagate': False}},
}
