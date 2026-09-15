from django.urls import path

from . import views

app_name = "ciudadania"

urlpatterns = [
    path("registro/", views.registro_view, name="registro"),
    # El path literal "reenviar/" va ANTES del <str:token>/ — si no, ese
    # catch-all lo captura primero (hallazgo real: "reenviar" se colaba
    # como si fuera un token, y tronaba con "token inválido").
    path("verificar/reenviar/", views.reenviar_verificacion_view, name="reenviar_verificacion"),
    path("verificar/<str:token>/", views.verificar_email_view, name="verificar_email"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("restablecer/", views.solicitar_restablecimiento_view, name="solicitar_restablecimiento"),
    path("restablecer/<str:token>/", views.restablecer_contrasena_view, name="restablecer_contrasena"),
    path("cuenta/", views.cuenta_view, name="cuenta"),
    path("cuenta/password/", views.cambiar_password_view, name="cambiar_password"),
    path("cuenta/email/", views.solicitar_cambio_email_view, name="solicitar_cambio_email"),
    path(
        "cuenta/email/confirmar/<str:token>/",
        views.confirmar_cambio_email_view,
        name="confirmar_cambio_email",
    ),
]
