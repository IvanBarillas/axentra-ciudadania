"""Urlconf de prueba que imita cómo el Core monta la superficie pública de ciudadania."""
from django.urls import include, path

urlpatterns = [path("ciudadano/", include("ciudadania.urls"))]  # PUBLIC_URLCONF / PUBLIC_PREFIX
