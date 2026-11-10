"""Ajustes de la aplicación. Todo lo sensible llega por variables de entorno: en Cloud Run las
inyecta Secret Manager; en local salen de .env, que git ignora."""

import base64
import hashlib
import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _entorno(nombre):
    valor = os.environ.get(nombre)
    if not valor:
        raise ImproperlyConfigured(f"Falta la variable de entorno {nombre}")
    return valor


def _lista(nombre):
    return [v.strip() for v in os.environ.get(nombre, "").split(",") if v.strip()]


def _base_desde_url(url):
    """Convierte la cadena de conexión (usuario, clave, host, puerto y base) en los ajustes de
    Django. Sus parámetros (sslmode, sslrootcert, channel_binding) van tal cual a psycopg."""
    partes = urlsplit(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": partes.path.lstrip("/"),
        "USER": unquote(partes.username or ""),
        "PASSWORD": unquote(partes.password or ""),
        "HOST": partes.hostname or "",
        "PORT": str(partes.port or ""),
        "OPTIONS": dict(parse_qsl(partes.query)),
        "CONN_HEALTH_CHECKS": True,
    }


SECRET_KEY = _entorno("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DJANGO_DEBUG") == "True"
ALLOWED_HOSTS = _lista("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = _lista("DJANGO_CSRF_TRUSTED_ORIGINS")

# Qué versión está corriendo: la etiqueta de la imagen y el commit del que salió.
VERSION_APP = os.environ.get("APP_VERSION", "local")
COMMIT_APP = os.environ.get("APP_COMMIT", "")

# Sin django.contrib.admin: su sitio edita cualquier tabla saltándose las reglas (tarea 5.14).
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "nucleo",
    "cuentas",
    "negocio",
    "bitacora",
]

AUTH_USER_MODEL = "cuentas.Usuario"
AUTHENTICATION_BACKENDS = ["allauth.account.auth_backends.AuthenticationBackend"]
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "hola"

# --- Inicio de sesión y segundo factor (POL-AU-05, POL-AU-06, POL-AU-10) ----------------------
# Se entra con el nombre de usuario; el correo no sirve para entrar ni para recuperar la cuenta.
ACCOUNT_ADAPTER = "cuentas.adaptadores.AdaptadorCuentas"
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_REAUTHENTICATION_TIMEOUT = 5 * 60
# Segundo factor obligatorio: código temporal (TOTP) con códigos de recuperación de respaldo. Sin
# SMS ni correo. Las llaves de acceso (WebAuthn) quedan para después (desviación D-07).
MFA_ADAPTER = "cuentas.adaptadores.AdaptadorSegundoFactor"
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Verdeazul Carbono"
# Clave Fernet con la que se cifran los secretos TOTP en la base. En Cloud Run llega de Secret
# Manager; en local, sin la variable, se deriva de la llave de Django.
MFA_CLAVE = os.environ.get("MFA_CLAVE") or (
    base64.urlsafe_b64encode(hashlib.sha256(f"mfa:{SECRET_KEY}".encode()).digest()).decode()
    if DEBUG
    else _entorno("MFA_CLAVE")
)

# --- Contraseñas (POL-AU-01 a 03 y 09) --------------------------------------------------------
# Argon2id con sal por usuario: lento y con mucha memoria a propósito (Morris y Thompson, 1979).
# Los demás quedan solo para leer resúmenes viejos y convertirlos al iniciar sesión.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
# Longitud mínima de 12 y sin reglas de composición: se rechazan las comunes y las que contienen
# nombres propios, no las que «les falta un símbolo».
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "cuentas.validadores.SinNombresPropios"},
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "cuentas.middleware.ExigirSegundoFactor",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

ROOT_URLCONF = "verdeazul.urls"
WSGI_APPLICATION = "verdeazul.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Plantillas propias que reemplazan las de allauth.
        "DIRS": [BASE_DIR / "plantillas"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {"default": _base_desde_url(_entorno("DATABASE_URL"))}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Costa_Rica"
USE_I18N = True
USE_TZ = True

# --- Seguridad del transporte y de las cookies (tarea 1.19, desviación D-01) ------------------
# Cloud Run termina el TLS y reenvía con X-Forwarded-Proto; el contenedor no es alcanzable de
# otra forma, así que esa cabecera la pone siempre el frente de Google.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r"^salud$"]
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# La lista de precarga de HSTS solo admite dominios propios; un subdominio de run.app no se puede
# inscribir, así que ese aviso de check --deploy no aplica.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Límite de tamaño de lo que se recibe: lo hacía el proxy Caddy del diseño (D-01).
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"consola": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["consola"], "level": "INFO"},
}
