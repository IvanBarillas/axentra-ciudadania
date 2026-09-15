from django.urls import path

from . import views

app_name = "ciudadania"

urlpatterns = [
    path("registro/", views.registro_view, name="registro"),
    path("verificar/<str:token>/", views.verificar_email_view, name="verificar_email"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("cuenta/", views.cuenta_view, name="cuenta"),
]
