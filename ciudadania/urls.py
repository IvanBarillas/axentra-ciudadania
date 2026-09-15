from django.urls import path

from . import views

app_name = "ciudadania"

urlpatterns = [
    path("registro/", views.registro_view, name="registro"),
    path("verificar/<str:token>/", views.verificar_email_view, name="verificar_email"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("restablecer/", views.solicitar_restablecimiento_view, name="solicitar_restablecimiento"),
    path("restablecer/<str:token>/", views.restablecer_contrasena_view, name="restablecer_contrasena"),
    path("cuenta/", views.cuenta_view, name="cuenta"),
]
