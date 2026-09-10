"""Configuração Django do SME-Identidade-SSO-Microsservico."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
API_KEY = os.getenv("API_KEY", "dev-key-default")
API_KEY_HEADER = os.getenv("API_KEY_HEADER", "X-API-Key")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
]
NIVEL_LOG = os.getenv("NIVEL_LOG", "INFO")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "rest_framework",
    "drf_spectacular",
    "apps.core",
    "apps.autenticacao",
    "apps.cache",
    "apps.gateway_ms",
    "apps.sessoes",
    "apps.login",
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

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.autenticacao.api.autenticacao.AutenticacaoApiKey",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SME-Identidade-SSO-Microsservico API",
    "DESCRIPTION": "API de sessão compartilhada e logout global do SSO-MS",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": API_KEY_HEADER,
            }
        }
    },
    "SECURITY": [{"ApiKeyAuth": []}],
}

# ---------------------------------------------------------------------------
# KeyDB (cache) — fonte de verdade da sessão compartilhada
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("URL_KEYDB", "redis://keydb:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "TIMEOUT": int(os.getenv("KEYDB_DEFAULT_TIMEOUT", "300")),
    }
}

# ---------------------------------------------------------------------------
# Integração com o SME-Identidade-Gateway-Microsservico
# ---------------------------------------------------------------------------
GATEWAY_MS_URL = os.getenv("GATEWAY_MS_URL", "http://gateway-ms:8000")
GATEWAY_MS_TIMEOUT = float(os.getenv("GATEWAY_MS_TIMEOUT", "10"))
API_KEY_GATEWAY_MS = os.getenv("API_KEY_GATEWAY_MS", "")
API_KEY_GATEWAY_MS_HEADER = os.getenv("API_KEY_GATEWAY_MS_HEADER", "X-API-Key")

# ---------------------------------------------------------------------------
# Configuração da sessão compartilhada
# ---------------------------------------------------------------------------
SESSAO_TEMPO_INATIVIDADE_SEGUNDOS = int(
    os.getenv("SESSAO_TEMPO_INATIVIDADE_SEGUNDOS", "1800")
)
SESSAO_DURACAO_MAXIMA_SEGUNDOS = int(
    os.getenv("SESSAO_DURACAO_MAXIMA_SEGUNDOS", "28800")
)


def _parse_logout_callbacks(valor: str) -> dict[int, str]:
    """Converta a configuração de callbacks de logout em dicionário.

    Formato esperado: ``"sistema_id:url,sistema_id:url"``. Entradas mal
    formadas são ignoradas silenciosamente — a configuração de
    callbacks é uma dívida técnica intencional (não há ainda um
    cadastro de sistemas com metadados de URL), então não deve
    derrubar a inicialização da aplicação por um valor malformado.

    Args:
        valor: Valor bruto da variável de ambiente
            ``SSO_LOGOUT_CALLBACKS``.

    Returns:
        Mapa de ``sistema_id`` para a URL de notificação de logout.
    """
    callbacks: dict[int, str] = {}

    for item in valor.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue

        sistema_id_str, _, url = item.partition(":")

        try:
            sistema_id = int(sistema_id_str.strip())
        except ValueError:
            continue

        url = url.strip()
        if url:
            callbacks[sistema_id] = url

    return callbacks


SSO_LOGOUT_CALLBACKS = os.getenv("SSO_LOGOUT_CALLBACKS", "")
LOGOUT_CALLBACKS = _parse_logout_callbacks(SSO_LOGOUT_CALLBACKS)
SSO_LOGOUT_CALLBACK_TIMEOUT = float(
    os.getenv("SSO_LOGOUT_CALLBACK_TIMEOUT", "5")
)

# ---------------------------------------------------------------------------
# Logging (python-json-logger — padrão Ateliê)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "rename_fields": {
                "asctime": "timestamp",
                "levelname": "nivel",
                "name": "logger",
            },
            "json_ensure_ascii": False,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "identidade_sso": {
            "handlers": ["console"],
            "level": NIVEL_LOG,
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": NIVEL_LOG,
    },
}
