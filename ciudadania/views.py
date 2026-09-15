from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from . import services
from .forms import (
    CambiarPasswordForm,
    LoginForm,
    NuevaPasswordForm,
    RegistroForm,
    SolicitarCambioEmailForm,
    SolicitarReenvioVerificacionForm,
    SolicitarRestablecimientoForm,
)
from .models import Ciudadano


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


def verificar_email_view(request, token):
    try:
        ciudadano = services.verificar_email(token)
    except services.TokenInvalido:
        return render(request, "ciudadania/token_invalido.html", status=400)

    return render(request, "ciudadania/email_verificado.html", {"ciudadano": ciudadano})


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


def logout_view(request):
    services.cerrar_sesion(request)
    return HttpResponseRedirect(reverse("ciudadania:login"))


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


def cuenta_view(request):
    ciudadano = services.ciudadano_actual(request)
    if ciudadano is None:
        return HttpResponseRedirect(reverse("ciudadania:login"))

    return render(request, "ciudadania/cuenta.html", {"ciudadano": ciudadano})


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


def confirmar_cambio_email_view(request, token):
    try:
        ciudadano = services.confirmar_cambio_de_email(token)
    except services.TokenInvalido:
        return render(request, "ciudadania/token_invalido.html", status=400)
    except services.CorreoYaRegistrado:
        return render(request, "ciudadania/correo_ya_registrado.html", status=400)

    return render(request, "ciudadania/email_cambiado.html", {"ciudadano": ciudadano})
