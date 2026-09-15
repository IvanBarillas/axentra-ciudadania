from django.urls import include, path

urlpatterns = [
    path("ciudadano/", include("ciudadania.urls")),
]
