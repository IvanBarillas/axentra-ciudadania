"""
Lógica de negocio de identidad ciudadana, separada de las vistas (mismo
espíritu de capas que el Core, sección 14 de 000_core_architecture.md:
Services = mutaciones/reglas; Views = coordinación HTTP).
"""

from __future__ import annotations

import dataclasses
import email.policy
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMessage
from django.db.models import Q
from django.utils import timezone

from .models import Ciudadano, IntentoAcceso

# Hallazgo real (reportado por el usuario, probando contra el backend de
# consola): la política de correo moderna de Python pliega cualquier línea
# de más de 78 caracteres, y para hacerlo cambia el Content-Transfer-Encoding
# a quoted-printable — que inserta un salto "=\n" a la mitad de la línea.
# Nuestros tokens firmados miden 100+ caracteres, así que la URL de
# verificación/restablecimiento se cortaba a la mitad. En un cliente de
# correo real esto se decodifica solo (nunca se nota), pero rompe copiar y
# pegar la URL cruda — que es justo como se prueba a mano en desarrollo.
# Se desactiva el plegado (max_line_length=None) solo para estos correos.
_POLITICA_SIN_PLEGADO = email.policy.default.clone(max_line_length=None)


class _CorreoSinPlegado(EmailMessage):
    def message(self, *, policy=_POLITICA_SIN_PLEGADO):
        return super().message(policy=policy)


def _enviar_correo(*, subject: str, message: str, recipient: str) -> None:
    _CorreoSinPlegado(
        subject=subject,
        body=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[recipient],
    ).send()


TOKEN_SALT = "ciudadania.verificacion-email"
TOKEN_MAX_AGE_SEGUNDOS = 60 * 60 * 24 * 2  # 2 días

RESET_TOKEN_SALT = "ciudadania.restablecer-password"
RESET_TOKEN_MAX_AGE_SEGUNDOS = 60 * 60  # 1 hora — más corto que el de verificación a propósito

CAMBIO_EMAIL_TOKEN_SALT = "ciudadania.cambio-email"
CAMBIO_EMAIL_TOKEN_MAX_AGE_SEGUNDOS = 60 * 60 * 2  # 2 horas

SESSION_KEY = "ciudadano_id"


class TokenInvalido(Exception):
    """El token de verificación no es válido o ya expiró."""


class CredencialesInvalidas(Exception):
    """Correo o contraseña incorrectos — mensaje genérico a propósito, sin
    distinguir cuál de los dos falló (no se filtra si un correo existe)."""


class CorreoNoVerificado(Exception):
    """La cuenta existe y la contraseña es correcta, pero el correo
    todavía no se ha verificado — no se permite iniciar sesión."""


class DemasiadosIntentos(Exception):
    """Bloqueo temporal por fuerza bruta — ver IntentoAcceso en models.py."""


class CorreoYaRegistrado(Exception):
    """Ya existe otra cuenta (no esta misma) con ese correo."""


# Límites de fuerza bruta. Dos ejes a propósito: por correo (protege esa
# cuenta puntual, sin importar desde dónde ataquen) y por IP (frena a
# alguien probando muchas cuentas distintas desde el mismo origen).
MAX_INTENTOS_LOGIN_POR_CORREO = 5
MAX_INTENTOS_LOGIN_POR_IP = 20
MAX_SOLICITUDES_RESTABLECIMIENTO_POR_CORREO = 3
MAX_SOLICITUDES_RESTABLECIMIENTO_POR_IP = 10
MAX_REENVIOS_VERIFICACION_POR_CORREO = 3
MAX_REENVIOS_VERIFICACION_POR_IP = 10
VENTANA_BLOQUEO_MINUTOS = 15


def _demasiados_intentos(
    accion: str,
    email: str,
    ip: str | None,
    *,
    max_por_correo: int,
    max_por_ip: int,
    solo_fallidos: bool = True,
) -> bool:
    desde = timezone.now() - timedelta(minutes=VENTANA_BLOQUEO_MINUTOS)
    filtro = Q(accion=accion, creado_en__gte=desde)
    if solo_fallidos:
        filtro &= Q(exitoso=False)

    if IntentoAcceso.objects.filter(filtro, email=email).count() >= max_por_correo:
        return True

    if ip and IntentoAcceso.objects.filter(filtro, ip=ip).count() >= max_por_ip:
        return True

    return False


def _registrar_intento(accion: str, email: str, ip: str | None, *, exitoso: bool) -> None:
    IntentoAcceso.objects.create(accion=accion, email=email, ip=ip, exitoso=exitoso)


def registrar_ciudadano(*, email: str, password: str, nombre_completo: str = "") -> Ciudadano:
    return Ciudadano.objects.create_ciudadano(
        email=email, password=password, nombre_completo=nombre_completo
    )


def generar_token_verificacion(ciudadano: Ciudadano) -> str:
    return signing.dumps(str(ciudadano.id), salt=TOKEN_SALT)


def enviar_correo_verificacion(ciudadano: Ciudadano, url_verificacion: str) -> None:
    # Django estándar (send_mail/EmailMessage), no
    # apps.shared.notifications.enqueue_email del Core — este paquete debe
    # funcionar instalado en cualquier proyecto Django, no solo en
    # axentra-core-django. Si quien lo instala quiere que el correo pase
    # por su propia cola, lo resuelve con su propio EMAIL_BACKEND (un
    # backend Django normal), sin tocar este código.
    _enviar_correo(
        subject="Verifica tu correo",
        message=(
            f"Hola {ciudadano.nombre_completo or ciudadano.email}:\n\n"
            "Confirma tu correo para activar tu cuenta:\n"
            f"{url_verificacion}\n\n"
            "Si tú no solicitaste esto, ignora este mensaje."
        ),
        recipient=ciudadano.email,
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


def puede_solicitar_reenvio_verificacion(email: str, ip: str | None = None) -> bool:
    """Mismo motivo que puede_solicitar_restablecimiento: el límite se
    aplica igual exista o no la cuenta, y esté o no ya verificada — así
    el límite mismo nunca delata nada."""
    email_normalizado = Ciudadano.objects.normalize_email(email)
    return not _demasiados_intentos(
        IntentoAcceso.Accion.REENVIO_VERIFICACION,
        email_normalizado,
        ip,
        max_por_correo=MAX_REENVIOS_VERIFICACION_POR_CORREO,
        max_por_ip=MAX_REENVIOS_VERIFICACION_POR_IP,
        solo_fallidos=False,
    )


def registrar_solicitud_reenvio_verificacion(email: str, ip: str | None = None) -> None:
    email_normalizado = Ciudadano.objects.normalize_email(email)
    _registrar_intento(IntentoAcceso.Accion.REENVIO_VERIFICACION, email_normalizado, ip, exitoso=True)


def buscar_ciudadano_sin_verificar(email: str) -> Ciudadano | None:
    return Ciudadano.objects.filter(
        email=Ciudadano.objects.normalize_email(email), email_verificado=False
    ).first()


def autenticar(*, email: str, password: str, ip: str | None = None) -> Ciudadano:
    email_normalizado = Ciudadano.objects.normalize_email(email)

    if _demasiados_intentos(
        IntentoAcceso.Accion.LOGIN,
        email_normalizado,
        ip,
        max_por_correo=MAX_INTENTOS_LOGIN_POR_CORREO,
        max_por_ip=MAX_INTENTOS_LOGIN_POR_IP,
    ):
        raise DemasiadosIntentos

    try:
        ciudadano = Ciudadano.objects.get(email=email_normalizado)
    except Ciudadano.DoesNotExist as exc:
        _registrar_intento(IntentoAcceso.Accion.LOGIN, email_normalizado, ip, exitoso=False)
        raise CredencialesInvalidas from exc

    if not ciudadano.is_active or not ciudadano.check_password(password):
        _registrar_intento(IntentoAcceso.Accion.LOGIN, email_normalizado, ip, exitoso=False)
        raise CredencialesInvalidas

    if not ciudadano.email_verificado:
        # La contraseña sí era correcta — no cuenta como intento fallido
        # de fuerza bruta, pero tampoco se deja entrar.
        raise CorreoNoVerificado

    _registrar_intento(IntentoAcceso.Accion.LOGIN, email_normalizado, ip, exitoso=True)
    return ciudadano


def puede_solicitar_restablecimiento(email: str, ip: str | None = None) -> bool:
    """
    Límite parejo exista o no la cuenta — a propósito: si solo limitara
    cuando la cuenta existe, alguien podría usar el propio límite como
    otra forma de adivinar qué correos están registrados.
    """
    email_normalizado = Ciudadano.objects.normalize_email(email)
    return not _demasiados_intentos(
        IntentoAcceso.Accion.RESTABLECIMIENTO,
        email_normalizado,
        ip,
        max_por_correo=MAX_SOLICITUDES_RESTABLECIMIENTO_POR_CORREO,
        max_por_ip=MAX_SOLICITUDES_RESTABLECIMIENTO_POR_IP,
        solo_fallidos=False,
    )


def registrar_solicitud_restablecimiento(email: str, ip: str | None = None) -> None:
    email_normalizado = Ciudadano.objects.normalize_email(email)
    _registrar_intento(IntentoAcceso.Accion.RESTABLECIMIENTO, email_normalizado, ip, exitoso=True)


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
    _enviar_correo(
        subject="Restablece tu contraseña",
        message=(
            f"Hola {ciudadano.nombre_completo or ciudadano.email}:\n\n"
            "Para elegir una nueva contraseña, entra aquí (el enlace vence en 1 hora):\n"
            f"{url_restablecimiento}\n\n"
            "Si tú no solicitaste esto, ignora este mensaje — tu contraseña actual sigue funcionando."
        ),
        recipient=ciudadano.email,
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


def cambiar_password(ciudadano: Ciudadano, *, password_actual: str, password_nueva: str, ip: str | None = None) -> None:
    """Ya logueado — reusa el mismo candado de fuerza bruta del login
    (misma cuenta, mismo tipo de ataque: adivinar la contraseña actual)."""
    if _demasiados_intentos(
        IntentoAcceso.Accion.LOGIN,
        ciudadano.email,
        ip,
        max_por_correo=MAX_INTENTOS_LOGIN_POR_CORREO,
        max_por_ip=MAX_INTENTOS_LOGIN_POR_IP,
    ):
        raise DemasiadosIntentos

    if not ciudadano.check_password(password_actual):
        _registrar_intento(IntentoAcceso.Accion.LOGIN, ciudadano.email, ip, exitoso=False)
        raise CredencialesInvalidas

    ciudadano.set_password(password_nueva)
    ciudadano.save(update_fields=["password", "actualizado_en"])


def solicitar_cambio_de_email(
    ciudadano: Ciudadano, *, password_actual: str, nuevo_email: str, ip: str | None = None
) -> str:
    if _demasiados_intentos(
        IntentoAcceso.Accion.LOGIN,
        ciudadano.email,
        ip,
        max_por_correo=MAX_INTENTOS_LOGIN_POR_CORREO,
        max_por_ip=MAX_INTENTOS_LOGIN_POR_IP,
    ):
        raise DemasiadosIntentos

    if not ciudadano.check_password(password_actual):
        _registrar_intento(IntentoAcceso.Accion.LOGIN, ciudadano.email, ip, exitoso=False)
        raise CredencialesInvalidas

    nuevo_email = Ciudadano.objects.normalize_email(nuevo_email)
    if Ciudadano.objects.filter(email__iexact=nuevo_email).exclude(id=ciudadano.id).exists():
        raise CorreoYaRegistrado

    # El correo NO cambia todavía — solo cuando se confirme el enlace
    # (ver confirmar_cambio_de_email). Así nunca queda la cuenta con un
    # correo que nadie puede confirmar por un error de dedo.
    #
    # Autoinvalidación: aquí NO sirve firmar un fragmento de la contraseña
    # (a diferencia del token de restablecimiento) — confirmar un cambio
    # de correo no toca la contraseña, así que ese fragmento nunca
    # cambiaría y el token se podría reusar indefinidamente (hallazgo
    # real, cubierto por test_token_de_un_solo_uso). En vez de eso se
    # firma el correo ACTUAL: en cuanto se confirma una vez, el correo de
    # la cuenta ya no es ese, y el mismo token deja de servir solo.
    return signing.dumps(
        {"id": str(ciudadano.id), "nuevo_email": nuevo_email, "correo_al_solicitar": ciudadano.email},
        salt=CAMBIO_EMAIL_TOKEN_SALT,
    )


def enviar_correo_confirmacion_cambio_email(nuevo_email: str, url_confirmacion: str) -> None:
    _enviar_correo(
        subject="Confirma tu nuevo correo",
        message=(
            "Confirma que este es tu nuevo correo para tu cuenta ciudadana:\n"
            f"{url_confirmacion}\n\n"
            "Si tú no solicitaste esto, ignora este mensaje — tu correo actual sigue siendo el mismo."
        ),
        recipient=nuevo_email,
    )


def confirmar_cambio_de_email(token: str) -> Ciudadano:
    try:
        datos = signing.loads(token, salt=CAMBIO_EMAIL_TOKEN_SALT, max_age=CAMBIO_EMAIL_TOKEN_MAX_AGE_SEGUNDOS)
        ciudadano_id = datos["id"]
        nuevo_email = datos["nuevo_email"]
        correo_al_solicitar = datos["correo_al_solicitar"]
    except (signing.BadSignature, KeyError, TypeError) as exc:
        raise TokenInvalido from exc

    try:
        ciudadano = Ciudadano.objects.get(id=ciudadano_id)
    except (Ciudadano.DoesNotExist, ValueError) as exc:
        raise TokenInvalido from exc

    if ciudadano.email != correo_al_solicitar:
        # El correo de la cuenta ya no es el mismo que cuando se pidió
        # este cambio — ya se usó este token, o el correo cambió por otro
        # camino mientras tanto. En cualquier caso, ya no sirve.
        raise TokenInvalido

    if Ciudadano.objects.filter(email__iexact=nuevo_email).exclude(id=ciudadano.id).exists():
        # Alguien más tomó ese correo mientras tanto.
        raise CorreoYaRegistrado

    ciudadano.email = nuevo_email
    ciudadano.email_verificado = True  # ya se verificó al hacer clic en el enlace
    ciudadano.save(update_fields=["email", "email_verificado", "actualizado_en"])
    return ciudadano


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


def ciudadania_habilitada() -> bool:
    """
    El interruptor real que motivó este paquete desde el inicio: quien
    instale `ciudadania` puede apagar el registro/login/etc. sin tocar
    código ni desinstalar el paquete — solo cambiando este setting. No
    hay `module_manifest.py`/panel de Hub para esto a propósito (un
    ciudadano nunca entra ahí), así que este es el único interruptor.
    """
    return getattr(settings, "CIUDADANIA_HABILITADA", True)


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
