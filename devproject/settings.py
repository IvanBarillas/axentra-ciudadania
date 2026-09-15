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
    "django.contrib.contenttypes",
    "django.contrib.auth",  # requerido por el framework de Django aunque
    # Ciudadano no sea AUTH_USER_MODEL — algunas apps internas de Django
    # (contenttypes/sessions) lo esperan instalado.
    "django.contrib.sessions",
    "ciudadania",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "devproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {},
    },
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
