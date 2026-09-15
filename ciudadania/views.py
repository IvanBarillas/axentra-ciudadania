from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from . import services
from .forms import LoginForm, RegistroForm


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


def login_view(request):
    error = None
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                ciudadano = services.autenticar(
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                )
            except services.CorreoNoVerificado:
                error = "Verifica tu correo antes de iniciar sesión."
            except services.CredencialesInvalidas:
                error = "Correo o contraseña incorrectos."
            else:
                services.iniciar_sesion(request, ciudadano)
                return HttpResponseRedirect(reverse("ciudadania:cuenta"))
    else:
        form = LoginForm()

    return render(request, "ciudadania/login.html", {"form": form, "error": error})


def logout_view(request):
    services.cerrar_sesion(request)
    return HttpResponseRedirect(reverse("ciudadania:login"))


def cuenta_view(request):
    ciudadano = services.ciudadano_actual(request)
    if ciudadano is None:
        return HttpResponseRedirect(reverse("ciudadania:login"))

    return render(request, "ciudadania/cuenta.html", {"ciudadano": ciudadano})
