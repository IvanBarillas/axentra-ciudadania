"""Superficie pública de ciudadania en una instalación real."""
import importlib
import sys
import types
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings


def cargar_public_entry():
    """`ciudadania.public_entry` con un SDK falso (el devproject no tiene apps.shared)."""
    sdk = types.ModuleType("apps.shared.module_sdk")
    sdk.PublicEntry = lambda **kwargs: types.SimpleNamespace(**kwargs)
    modulos = {"apps": types.ModuleType("apps"), "apps.shared": types.ModuleType("apps.shared"), "apps.shared.module_sdk": sdk}
    with patch.dict(sys.modules, modulos):
        sys.modules.pop("ciudadania.public_entry", None)
        modulo = importlib.import_module("ciudadania.public_entry")
        sys.modules.pop("ciudadania.public_entry", None)
    return modulo


class ConstantesDeSuperficiePublicaTests(SimpleTestCase):
    def test_declara_urlconf_y_prefijo_estaticos(self):
        modulo = cargar_public_entry()
        self.assertEqual((modulo.PUBLIC_URLCONF, modulo.PUBLIC_PREFIX), ("ciudadania.urls", "ciudadano/"))

    def test_el_urlconf_declarado_es_importable_y_tiene_rutas(self):
        self.assertTrue(importlib.import_module(cargar_public_entry().PUBLIC_URLCONF).urlpatterns)


@override_settings(ROOT_URLCONF="ciudadania.tests.urls_superficie")
class MontadoBajoPrefijoTests(TestCase):
    def test_la_cuenta_funciona_bajo_el_prefijo_que_declara(self):
        from django.urls import reverse

        self.assertEqual(reverse("ciudadania:login"), "/ciudadano/login/")
        self.assertEqual(self.client.get("/ciudadano/login/").status_code, 200)
        self.assertEqual(self.client.get("/ciudadano/registro/").status_code, 200)
