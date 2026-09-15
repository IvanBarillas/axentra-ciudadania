from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase

from ciudadania import services
from ciudadania.models import Ciudadano, IntentoAcceso


class RegistroEnAdminTests(TestCase):
    def test_ciudadano_esta_registrado(self):
        self.assertIn(Ciudadano, admin.site._registry)

    def test_intento_acceso_esta_registrado(self):
        self.assertIn(IntentoAcceso, admin.site._registry)


class CiudadanoAdminChangelistTests(TestCase):
    """
    Prueba real contra el sitio de Admin (no solo que esté registrado) —
    usa django.contrib.auth.models.User como superusuario de prueba
    (Ciudadano no puede serlo, no tiene esa relación con el Admin).
    """

    def setUp(self):
        self.superusuario = User.objects.create_superuser(
            username="root", email="root@example.mx", password="clave-de-soporte-987"
        )
        self.client.force_login(self.superusuario)

    def test_changelist_de_ciudadano_carga(self):
        services.registrar_ciudadano(email="a@example.mx", password="x", nombre_completo="Ana")

        respuesta = self.client.get("/admin/ciudadania/ciudadano/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "a@example.mx")

    def test_no_se_puede_dar_de_alta_desde_admin(self):
        respuesta = self.client.get("/admin/ciudadania/ciudadano/add/")

        self.assertEqual(respuesta.status_code, 403)

    def test_changelist_de_intentoacceso_carga_y_es_solo_lectura(self):
        services.registrar_solicitud_restablecimiento("a@example.mx", "10.0.0.1")

        respuesta = self.client.get("/admin/ciudadania/intentoacceso/")
        self.assertEqual(respuesta.status_code, 200)

        respuesta = self.client.get("/admin/ciudadania/intentoacceso/add/")
        self.assertEqual(respuesta.status_code, 403)
