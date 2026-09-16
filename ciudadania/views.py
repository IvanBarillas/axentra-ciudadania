from functools import wraps

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from . import services
from .forms import (
    CambiarPasswordForm,
    DocumentoUploadForm,
    LoginForm,
    NuevaPasswordForm,
    RegistroForm,
    SolicitarCambioEmailForm,
    SolicitarReenvioVerificacionForm,
    SolicitarRestablecimientoForm,
)
from .models import Ciudadano


def requiere_ciudadania_habilitada(view_func):
    """
    404, no 403: cuando está apagada, la ruta debe comportarse como si no
    existiera — no revelar que la función está ahí pero deshabilitada.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not services.ciudadania_habilitada():
            raise Http404
        return view_func(request, *args, **kwargs)

    return wrapper


@requiere_ciudadania_habilitada
def registro_view(request):
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            ciudadano = services.registrar_ciudadano(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                nombre_completo=form.cleaned_data["nombre_completo"],
            )
            token = services.generar_token_verificacion(ciudadano)
            url_verificacion = request.build_absolute_uri(
                reverse("ciudadania:verificar_email", args=[token])
            )
            services.enviar_correo_verificacion(ciudadano, url_verificacion)
            return render(request, "ciudadania/registro_exitoso.html", {"ciudadano": ciudadano})
    else:
        form = RegistroForm()

    return render(request, "ciudadania/registro.html", {"form": form})


@requiere_ciudadania_habilitada
def verificar_email_view(request, token):
    try:
        ciudadano = services.verificar_email(token)
    except services.TokenInvalido:
        return render(request, "ciudadania/token_invalido.html", status=400)

    return render(request, "ciudadania/email_verificado.html", {"ciudadano": ciudadano})


@requiere_ciudadania_habilitada
def reenviar_verificacion_view(request):
    if request.method == "POST":
        form = SolicitarReenvioVerificacionForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            ip = request.META.get("REMOTE_ADDR")

            # Misma respuesta exista, esté ya verificada o esté bloqueada
            # — nada de esto debe distinguirse desde afuera.
            if services.puede_solicitar_reenvio_verificacion(email, ip):
                ciudadano = services.buscar_ciudadano_sin_verificar(email)
                if ciudadano is not None:
                    token = services.generar_token_verificacion(ciudadano)
                    url_verificacion = request.build_absolute_uri(
                        reverse("ciudadania:verificar_email", args=[token])
                    )
                    services.enviar_correo_verificacion(ciudadano, url_verificacion)

            services.registrar_solicitud_reenvio_verificacion(email, ip)
            return render(request, "ciudadania/reenvio_verificacion_solicitado.html")
    else:
        form = SolicitarReenvioVerificacionForm()

    return render(request, "ciudadania/reenviar_verificacion.html", {"form": form})


@requiere_ciudadania_habilitada
def login_view(request):
    error = None
    correo_no_verificado = False
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                ciudadano = services.autenticar(
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    ip=request.META.get("REMOTE_ADDR"),
                )
            except services.DemasiadosIntentos:
                error = "Demasiados intentos. Espera unos minutos antes de volver a intentar."
            except services.CorreoNoVerificado:
                error = "Verifica tu correo antes de iniciar sesión."
                correo_no_verificado = True
            except services.CredencialesInvalidas:
                error = "Correo o contraseña incorrectos."
            else:
                services.iniciar_sesion(request, ciudadano)
                return HttpResponseRedirect(reverse("ciudadania:cuenta"))
    else:
        form = LoginForm()

    return render(
        request,
        "ciudadania/login.html",
        {"form": form, "error": error, "correo_no_verificado": correo_no_verificado},
    )


@requiere_ciudadania_habilitada
def logout_view(request):
    services.cerrar_sesion(request)
    return HttpResponseRedirect(reverse("ciudadania:login"))


@requiere_ciudadania_habilitada
def solicitar_restablecimiento_view(request):
    if request.method == "POST":
        form = SolicitarRestablecimientoForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            ip = request.META.get("REMOTE_ADDR")

            # El límite se registra y se respeta IGUAL exista o no la
            # cuenta — y la respuesta es la misma en los tres casos (no
            # existe / bloqueado / se mandó el correo). Nada de esto debe
            # distinguirse desde afuera.
            if services.puede_solicitar_restablecimiento(email, ip):
                ciudadano = Ciudadano.objects.filter(
                    email=Ciudadano.objects.normalize_email(email)
                ).first()
                if ciudadano is not None:
                    token = services.generar_token_restablecimiento(ciudadano)
                    url_restablecimiento = request.build_absolute_uri(
                        reverse("ciudadania:restablecer_contrasena", args=[token])
                    )
                    services.enviar_correo_restablecimiento(ciudadano, url_restablecimiento)

            services.registrar_solicitud_restablecimiento(email, ip)
            return render(request, "ciudadania/restablecimiento_solicitado.html")
    else:
        form = SolicitarRestablecimientoForm()

    return render(request, "ciudadania/solicitar_restablecimiento.html", {"form": form})


@requiere_ciudadania_habilitada
def restablecer_contrasena_view(request, token):
    try:
        ciudadano = services.resolver_token_restablecimiento(token)
    except services.TokenInvalido:
        return render(request, "ciudadania/token_invalido.html", status=400)

    if request.method == "POST":
        form = NuevaPasswordForm(request.POST)
        if form.is_valid():
            services.restablecer_contrasena(ciudadano, form.cleaned_data["password"])
            return render(request, "ciudadania/contrasena_restablecida.html")
    else:
        form = NuevaPasswordForm()

    return render(request, "ciudadania/restablecer_contrasena.html", {"form": form})


# Metadatos de presentación, opcionales, para satélites ya conocidos —
# un satélite nuevo que empiece a llamar registrar_evento() y no esté
# aquí simplemente usa el valor por defecto (su propio nombre técnico
# convertido a título, ícono genérico). Nunca hace falta tocar esto para
# que un satélite nuevo aparezca en el panel — es solo para que se vea
# más pulido, no un requisito.
_METADATOS_SATELITE = {
    "tramites": {"titulo": "Mis trámites", "icono": "file-text"},
    "situaciones_de_vida": {"titulo": "Mis situaciones de vida", "icono": "signpost"},
}
_ICONO_POR_DEFECTO = "activity"


def _titulo_e_icono_satelite(satelite_origen):
    metadatos = _METADATOS_SATELITE.get(satelite_origen, {})
    titulo = metadatos.get("titulo") or satelite_origen.replace("_", " ").replace("-", " ").title()
    return titulo, metadatos.get("icono", _ICONO_POR_DEFECTO)


def _construir_items_sidebar(ciudadano_id, *, activo):
    """
    Bug real señalado en vivo: el panel apilaba TODO en una sola
    página (cuenta + cada satélite con su actividad completa, uno tras
    otro) — con 20 módulos que un ciudadano pueda usar, eso deja de
    ser navegable, aunque las secciones ya salieran solas (ver el
    cambio anterior). La corrección real no es solo "que las
    secciones no estén hardcodeadas" — es que cada categoría viva en
    su propia página, con una navegación real entre ellas (mismo
    espíritu que el sidebar contextual del Core, aquí propio del panel
    del ciudadano, nunca del Hub).

    `activo` es el identificador del item actual ("resumen",
    "expediente", o el satelite_origen de la página de actividad que
    se está viendo) — para resaltarlo en la plantilla. Se construye en
    cada vista en vez de vivir en un context processor a propósito:
    este paquete debe seguir siendo instalable en cualquier proyecto
    Django sin tocar su settings.py.
    """
    items = [
        {
            "id": "resumen",
            "titulo": "Resumen",
            "icono": "home",
            "url": reverse("ciudadania:cuenta"),
            "activo": activo == "resumen",
        },
        {
            "id": "expediente",
            "titulo": "Mi expediente",
            "icono": "folder-open",
            "url": reverse("ciudadania:mi_expediente"),
            "activo": activo == "expediente",
        },
    ]
    for grupo in services.obtener_linea_de_tiempo_agrupada(ciudadano_id):
        titulo, icono = _titulo_e_icono_satelite(grupo.satelite_origen)
        items.append({
            "id": grupo.satelite_origen,
            "titulo": titulo,
            "icono": icono,
            "url": reverse("ciudadania:panel_actividad", args=[grupo.satelite_origen]),
            "activo": activo == grupo.satelite_origen,
        })
    return items


@requiere_ciudadania_habilitada
def cuenta_view(request):
    ciudadano = services.ciudadano_actual(request)
    if ciudadano is None:
        return HttpResponseRedirect(reverse("ciudadania:login"))

    return render(
        request,
        "ciudadania/cuenta.html",
        {
            "ciudadano": ciudadano,
            "nav_items": _construir_items_sidebar(ciudadano.id, activo="resumen"),
        },
    )


@requiere_ciudadania_habilitada
def panel_actividad_view(request, satelite):
    ciudadano = services.ciudadano_actual(request)
    if ciudadano is None:
        return HttpResponseRedirect(reverse("ciudadania:login"))

    titulo, icono = _titulo_e_icono_satelite(satelite)

    return render(
        request,
        "ciudadania/actividad.html",
        {
            "ciudadano": ciudadano,
            "nav_items": _construir_items_sidebar(ciudadano.id, activo=satelite),
            "titulo_categoria": titulo,
            "icono_categoria": icono,
            "eventos": services.obtener_linea_de_tiempo(ciudadano.id, satelite_origen=satelite),
        },
    )


@requiere_ciudadania_habilitada
def cambiar_password_view(request):
    ciudadano = services.ciudadano_actual(request)
    if ciudadano is None:
        return HttpResponseRedirect(reverse("ciudadania:login"))

    error = None
    if request.method == "POST":
        form = CambiarPasswordForm(request.POST)
        if form.is_valid():
            try:
                services.cambiar_password(
                    ciudadano,
                    password_actual=form.cleaned_data["password_actual"],
                    password_nueva=form.cleaned_data["password"],
                    ip=request.META.get("REMOTE_ADDR"),
                )
            except services.DemasiadosIntentos:
                error = "Demasiados intentos. Espera unos minutos antes de volver a intentar."
            except services.CredencialesInvalidas:
                error = "Tu contraseña actual no es correcta."
            else:
                return render(request, "ciudadania/password_cambiada.html")
    else:
        form = CambiarPasswordForm()

    return render(request, "ciudadania/cambiar_password.html", {"form": form, "error": error})


@requiere_ciudadania_habilitada
def solicitar_cambio_email_view(request):
    ciudadano = services.ciudadano_actual(request)
    if ciudadano is None:
        return HttpResponseRedirect(reverse("ciudadania:login"))

    error = None
    if request.method == "POST":
        form = SolicitarCambioEmailForm(request.POST)
        if form.is_valid():
            nuevo_email = form.cleaned_data["nuevo_email"]
            try:
                token = services.solicitar_cambio_de_email(
                    ciudadano,
                    password_actual=form.cleaned_data["password_actual"],
                    nuevo_email=nuevo_email,
                    ip=request.META.get("REMOTE_ADDR"),
                )
            except services.DemasiadosIntentos:
                error = "Demasiados intentos. Espera unos minutos antes de volver a intentar."
            except services.CredencialesInvalidas:
                error = "Tu contraseña actual no es correcta."
            except services.CorreoYaRegistrado:
                error = "Ya existe otra cuenta con ese correo."
            else:
                url_confirmacion = request.build_absolute_uri(
                    reverse("ciudadania:confirmar_cambio_email", args=[token])
                )
                services.enviar_correo_confirmacion_cambio_email(nuevo_email, url_confirmacion)
                return render(
                    request, "ciudadania/cambio_email_solicitado.html", {"nuevo_email": nuevo_email}
                )
    else:
        form = SolicitarCambioEmailForm()

    return render(request, "ciudadania/solicitar_cambio_email.html", {"form": form, "error": error})


@requiere_ciudadania_habilitada
def confirmar_cambio_email_view(request, token):
    try:
        ciudadano = services.confirmar_cambio_de_email(token)
    except services.TokenInvalido:
        return render(request, "ciudadania/token_invalido.html", status=400)
    except services.CorreoYaRegistrado:
        return render(request, "ciudadania/correo_ya_registrado.html", status=400)

    return render(request, "ciudadania/email_cambiado.html", {"ciudadano": ciudadano})


@requiere_ciudadania_habilitada
def mi_expediente_view(request):
    ciudadano = services.ciudadano_actual(request)
    if ciudadano is None:
        return HttpResponseRedirect(reverse("ciudadania:login"))

    mensaje_sobrescritura = None
    if request.method == "POST":
        form = DocumentoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            tipo_documento = form.cleaned_data["tipo_documento"]
            ya_existia = (
                services.existe_documento_de_tipo(ciudadano.id, tipo_documento.clave) is not None
            )
            try:
                services.subir_documento_a_expediente(
                    ciudadano.id, tipo_documento.clave, form.cleaned_data["archivo"]
                )
            except services.FormatoNoSoportado as exc:
                form.add_error("archivo", str(exc))
            else:
                if ya_existia:
                    mensaje_sobrescritura = tipo_documento.nombre
                form = DocumentoUploadForm()
    else:
        form = DocumentoUploadForm()

    return render(
        request,
        "ciudadania/mi_expediente.html",
        {
            "ciudadano": ciudadano,
            "nav_items": _construir_items_sidebar(ciudadano.id, activo="expediente"),
            "expediente": services.obtener_expediente(ciudadano.id),
            "form": form,
            "mensaje_sobrescritura": mensaje_sobrescritura,
        },
    )
