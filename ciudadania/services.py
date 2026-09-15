"""
Lógica de negocio de identidad ciudadana, separada de las vistas (mismo
espíritu de capas que el Core, sección 14 de 000_core_architecture.md:
Services = mutaciones/reglas; Views = coordinación HTTP).
"""

from __future__ import annotations

import dataclasses

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

from .models import Ciudadano

TOKEN_SALT = "ciudadania.verificacion-email"
TOKEN_MAX_AGE_SEGUNDOS = 60 * 60 * 24 * 2  # 2 días

RESET_TOKEN_SALT = "ciudadania.restablecer-password"
RESET_TOKEN_MAX_AGE_SEGUNDOS = 60 * 60  # 1 hora — más corto que el de verificación a propósito

SESSION_KEY = "ciudadano_id"


class TokenInvalido(Exception):
    """El token de verificación no es válido o ya expiró."""


class CredencialesInvalidas(Exception):
    """Correo o contraseña incorrectos — mensaje genérico a propósito, sin
    distinguir cuál de los dos falló (no se filtra si un correo existe)."""


class CorreoNoVerificado(Exception):
    """La cuenta existe y la contraseña es correcta, pero el correo
    todavía no se ha verificado — no se permite iniciar sesión."""


def registrar_ciudadano(*, email: str, password: str, nombre_completo: str = "") -> Ciudadano:
    return Ciudadano.objects.create_ciudadano(
        email=email, password=password, nombre_completo=nombre_completo
    )


def generar_token_verificacion(ciudadano: Ciudadano) -> str:
    return signing.dumps(str(ciudadano.id), salt=TOKEN_SALT)


def enviar_correo_verificacion(ciudadano: Ciudadano, url_verificacion: str) -> None:
    # Django estándar (send_mail), no apps.shared.notifications.enqueue_email
    # del Core — este paquete debe funcionar instalado en cualquier
    # proyecto Django, no solo en axentra-core-django. Si quien lo instala
    # quiere que el correo pase por su propia cola, lo resuelve con su
    # propio EMAIL_BACKEND (un backend Django normal), sin tocar este código.
    send_mail(
        subject="Verifica tu correo",
        message=(
            f"Hola {ciudadano.nombre_completo or ciudadano.email}:\n\n"
            "Confirma tu correo para activar tu cuenta:\n"
            f"{url_verificacion}\n\n"
            "Si tú no solicitaste esto, ignora este mensaje."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[ciudadano.email],
    )


def verificar_email(token: str) -> Ciudadano:
    try:
        ciudadano_id = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE_SEGUNDOS)
    except signing.BadSignature as exc:
        raise TokenInvalido from exc

    try:
        ciudadano = Ciudadano.objects.get(id=ciudadano_id)
    except (Ciudadano.DoesNotExist, ValueError, TypeError) as exc:
        raise TokenInvalido from exc

    if not ciudadano.email_verificado:
        ciudadano.email_verificado = True
        ciudadano.save(update_fields=["email_verificado", "actualizado_en"])

    return ciudadano


def autenticar(*, email: str, password: str) -> Ciudadano:
    email_normalizado = Ciudadano.objects.normalize_email(email)
    try:
        ciudadano = Ciudadano.objects.get(email=email_normalizado)
    except Ciudadano.DoesNotExist as exc:
        raise CredencialesInvalidas from exc

    if not ciudadano.is_active or not ciudadano.check_password(password):
        raise CredencialesInvalidas

    if not ciudadano.email_verificado:
        raise CorreoNoVerificado

    return ciudadano


def generar_token_restablecimiento(ciudadano: Ciudadano) -> str:
    # Se firma también un fragmento del hash actual de la contraseña —
    # así el token se autoinvalida solo en cuanto se usa (o si la
    # contraseña cambió por cualquier otro medio mientras tanto), sin
    # necesitar una tabla aparte de "tokens ya usados".
    return signing.dumps(
        {"id": str(ciudadano.id), "firma_password": ciudadano.password[-12:]},
        salt=RESET_TOKEN_SALT,
    )


def enviar_correo_restablecimiento(ciudadano: Ciudadano, url_restablecimiento: str) -> None:
    send_mail(
        subject="Restablece tu contraseña",
        message=(
            f"Hola {ciudadano.nombre_completo or ciudadano.email}:\n\n"
            "Para elegir una nueva contraseña, entra aquí (el enlace vence en 1 hora):\n"
            f"{url_restablecimiento}\n\n"
            "Si tú no solicitaste esto, ignora este mensaje — tu contraseña actual sigue funcionando."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[ciudadano.email],
    )


def resolver_token_restablecimiento(token: str) -> Ciudadano:
    try:
        datos = signing.loads(token, salt=RESET_TOKEN_SALT, max_age=RESET_TOKEN_MAX_AGE_SEGUNDOS)
        ciudadano_id = datos["id"]
        firma_password = datos["firma_password"]
    except (signing.BadSignature, KeyError, TypeError) as exc:
        raise TokenInvalido from exc

    try:
        ciudadano = Ciudadano.objects.get(id=ciudadano_id)
    except (Ciudadano.DoesNotExist, ValueError) as exc:
        raise TokenInvalido from exc

    if ciudadano.password[-12:] != firma_password:
        # La contraseña ya no es la misma que cuando se generó el enlace
        # — ya se usó este token, o se cambió la contraseña por otro
        # camino. En cualquier caso, este enlace ya no sirve.
        raise TokenInvalido

    return ciudadano


def restablecer_contrasena(ciudadano: Ciudadano, nueva_password: str) -> None:
    ciudadano.set_password(nueva_password)
    ciudadano.save(update_fields=["password", "actualizado_en"])


def iniciar_sesion(request, ciudadano: Ciudadano) -> None:
    request.session[SESSION_KEY] = str(ciudadano.id)


def cerrar_sesion(request) -> None:
    request.session.pop(SESSION_KEY, None)


def ciudadano_actual(request) -> Ciudadano | None:
    ciudadano_id = request.session.get(SESSION_KEY)
    if not ciudadano_id:
        return None
    return Ciudadano.objects.filter(id=ciudadano_id).first()


@dataclasses.dataclass(frozen=True)
class CiudadanoPublico:
    """
    Snapshot de solo lectura — para que OTROS satélites (Trámites,
    Reportes Ciudadanos) resuelvan un UUID a datos básicos sin importar el
    modelo `Ciudadano` ni ver la contraseña. Ver sección 12 de
    000_core_architecture.md del Core: "contratos; adaptadores;
    identificadores UUID; snapshots cuando sea necesario".
    """

    id: str
    nombre_completo: str
    email: str
    email_verificado: bool


def obtener_datos_publicos(ciudadano_id) -> CiudadanoPublico | None:
    ciudadano = Ciudadano.objects.filter(id=ciudadano_id).first()
    if ciudadano is None:
        return None

    return CiudadanoPublico(
        id=str(ciudadano.id),
        nombre_completo=ciudadano.nombre_completo,
        email=ciudadano.email,
        email_verificado=ciudadano.email_verificado,
    )
