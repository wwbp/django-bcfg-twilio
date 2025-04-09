"""
Django settings for config project.

Generated by 'django-admin startproject' using Django 5.1.6.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import json
import os
from pathlib import Path
from saml2 import BINDING_HTTP_REDIRECT
from saml2 import BINDING_HTTP_POST

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-#7lq@_7b#8v!+1^6!$0@5v!u7z7x0^v1x0v0#4q8t^k9^3!%zr"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = ["*"]

# Application definition

INSTALLED_APPS = [
    "admin.apps.ChatAdmin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "chat",
    "tester",
    "django_celery_results",
    "djangosaml2",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "djangosaml2.middleware.SamlSessionMiddleware",
]

REQUIRE_SAML_AUTHENTICATION = os.getenv("REQUIRE_SAML_AUTHENTICATION", "False") == "True"

if REQUIRE_SAML_AUTHENTICATION:
    AUTHENTICATION_BACKENDS = ("djangosaml2.backends.Saml2Backend",)
else:
    AUTHENTICATION_BACKENDS = (
        "django.contrib.auth.backends.ModelBackend",
        "djangosaml2.backends.Saml2Backend",
    )

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

CSP_STYLE_SRC = ["'self'", "'unsafe-inline'"]
CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'"]


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases
DBINFO = json.loads(os.environ.get("DB_SECRET", "{}"))


# postgres dabase connection
if DBINFO:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": DBINFO["host"],
            "PORT": DBINFO["port"],
            "NAME": DBINFO["dbname"],
            "USER": DBINFO["username"],
            "PASSWORD": DBINFO["password"],
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ.get("DB_HOST", "db"),
            "PORT": 5432,
            "NAME": "chatbot",
            "USER": "bcfg_sa",
            "PASSWORD": "root_password",
        }
    }

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery Configuration Options
CELERY_BROKER_HOST = os.environ.get("CELERY_BROKER_HOST", "redis")
# CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_BROKER_URL = f"redis://{CELERY_BROKER_HOST}:6379"
CELERY_RESULT_BACKEND = "django-db"
CELERY_RESULT_EXTENDED = True
CELERY_TASK_SERIALIZER = "json"
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "retry_on_timeout": True,
    "max_retries": 5,  # Adjust based on your needs
    "socket_connect_timeout": 10,  # Timeout for establishing the connection
    "socket_timeout": 20,  # Timeout for read/write operations,
    "queue_order_strategy": "priority",
    "sep": ":",
    "priority_steps": list(range(2)),  # note - lower number is higher priority
}
CELERY_TASK_DEFAULT_PRIORITY = 0
# CELERY_TIMEZONE = os.environ.get('CELERY_TIMEZONE', 'UTC')
# CELERY_ENABLE_UTC = True

# Core app config
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
BCFG_DOMAIN = os.environ.get("BCFG_DOMAIN", "")
BCFG_API_KEY = os.environ.get("BCFG_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MODERATION_VALUES_FOR_BLOCKED = json.loads(
    os.environ.get(
        "MODERATION_VALUES_FOR_BLOCKED",
        """{
            "harassment": 0.5,
            "harassment/threatening": 0.1,
            "hate": 0.5,
            "hate/threatening": 0.1,
            "self-harm": 0.2,
            "self-harm/instructions": 0.5,
            "self-harm/intent": 0.7,
            "sexual": 0.5,
            "sexual/minors": 0.2,
            "violence": 0.7,
            "violence/graphic": 0.8
        }""",
    )
)


# SAML and PennKey Settings
LOGIN_REDIRECT_URL = "/admin/"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# SAML_USE_NAME_ID_AS_USERNAME = True

CERT_FILE = os.getenv("CERT_FILE", "/workspace/assets/shibcert.pem")
KEY_FILE = os.getenv("KEY_FILE", "/workspace/assets/shibkey.pem")

BASE_ADMIN_URI = os.getenv("BASE_ADMIN_URI", "http://localhost:8000/")

SAML_ATTRIBUTE_MAPPING = {
    "eduPersonPrincipalName": ("username",),
    "mail": ("email",),
    "givenName": ("first_name",),
    "sn": ("last_name",),
}
# SAML_USE_NAME_ID_AS_USERNAME = True
SAML_CREATE_UNKNOWN_USER = False

SAML_CONFIG_DEFAULT = {
    "xmlsec_binary": "/usr/bin/xmlsec1",
    "entityid": BASE_ADMIN_URI + "saml2/metadata/",
    "attribute_map_dir": os.path.join(BASE_DIR, "assets/attribute-maps"),
    "allow_unknown_attributes": True,
    "service": {
        "sp": {
            "name": "College Starter Kit",
            "allow_unsolicited": True,
            "endpoints": {
                "assertion_consumer_service": [
                    (BASE_ADMIN_URI + "saml2/acs/", BINDING_HTTP_POST),
                ],
                "single_logout_service": [
                    (BASE_ADMIN_URI + "saml2/ls/", BINDING_HTTP_REDIRECT),
                    (BASE_ADMIN_URI + "saml2/ls/post/", BINDING_HTTP_POST),
                ],
            },
            "required_attributes": ["eduPersonAffiliation", "eduPersonPrincipalName"],
            "optional_attributes": ["sn", "givenName", "mail"],
            "want_response_signed": False,
            "want_assertions_signed": False,
        },
    },
    "metadata": {
        "local": [os.path.join(BASE_DIR, "assets/metadata.xml")],
    },
    "debug": 1,
    "key_file": KEY_FILE,
    "cert_file": CERT_FILE,
    "encryption_keypairs": [
        {
            "key_file": KEY_FILE,
            "cert_file": CERT_FILE,
        }
    ],
    "contact_person": [
        {
            "given_name": "Jeffrey",
            "sur_name": "Licht",
            "company": "Pod Consulting",
            "email_address": "jllicht@upenn.edu",
            "contact_type": "technical",
        },
    ],
    "organization": {
        "name": [("UPenn", "en")],
        "display_name": [("Upenn", "en")],
        "url": [("http://www.upenn.edu", "en")],
    },
}
SAML_CONFIG = os.getenv("SAML_CONFIG", SAML_CONFIG_DEFAULT)
