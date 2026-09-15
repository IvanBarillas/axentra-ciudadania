"""
Settings mínimos SOLO para desarrollar/probar el paquete `ciudadania` de
forma aislada — no es lo que se despliega. Quien instale este paquete de
verdad (p. ej. axentra-core-django) define sus propios settings; este
archivo no se instala como parte del paquete distribuible.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "solo-para-desarrollo-local-de-este-paquete"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",  # solo para probar aquí que Ciudadano se
    # registra bien en Admin — el Admin de verdad lo sirve quien instale
    # este paquete (p. ej. axentra-core-django, que ya lo trae).
    "django.contrib.auth",  # requerido por el framework de Django aunque
    # Ciudadano no sea AUTH_USER_MODEL — algunas apps internas de Django
    # (contenttypes/sessions/admin) lo esperan instalado.
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",  # requerido por django.contrib.admin.
    "ciudadania",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "devproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

STATIC_URL = "static/"

# Hallazgo real: Ciudadano no es AUTH_USER_MODEL, así que estos
# validadores nunca corrían solos (ver ConfirmacionDePasswordMixin en
# forms.py, que ahora los llama a mano). Aquí, valores razonables para
# desarrollar/probar este paquete — quien lo instale define los suyos.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Consola en desarrollo — quien instale este paquete de verdad define su
# propio EMAIL_BACKEND (ver nota en ciudadania/services.py).
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@example.mx"

# Mismo orden que el Core (Argon2 primero) — ver AGENTS.md de axentra-core-django.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

USE_TZ = True
LANGUAGE_CODE = "es-mx"
