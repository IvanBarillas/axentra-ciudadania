import re

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from ciudadania.models import Ciudadano


class FlujoCompletoTests(TestCase):
    def test_registro_login_y_cuenta_de_principio_a_fin(self):
        # 1. Registro.
        respuesta = self.client.post(
            reverse("ciudadania:registro"),
            {
                "email": "vecino@example.mx",
                "nombre_completo": "Vecino de Prueba",
                "password": "clave-super-larga",
                "password_confirmacion": "clave-super-larga",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Ciudadano.objects.filter(email="vecino@example.mx").exists())
        self.assertEqual(len(mail.outbox), 1)

        # 2. Sin verificar, el login debe rechazarse con el mensaje correcto.
        respuesta = self.client.post(
            reverse("ciudadania:login"),
            {"email": "vecino@example.mx", "password": "clave-super-larga"},
        )
        self.assertContains(respuesta, "Verifica tu correo")

        # 3. Extraer el enlace real del correo enviado y "hacer clic".
        match = re.search(r"http\S+/ciudadano/verificar/\S+/", mail.outbox[0].body)
        self.assertIsNotNone(match, "El correo debe incluir el enlace de verificación.")
        url_verificacion = match.group(0)
        respuesta = self.client.get(url_verificacion)
        self.assertContains(respuesta, "Correo verificado")

        # 4. Ahora sí debe poder iniciar sesión.
        respuesta = self.client.post(
            reverse("ciudadania:login"),
            {"email": "vecino@example.mx", "password": "clave-super-larga"},
            follow=True,
        )
        self.assertContains(respuesta, "Vecino de Prueba")

        # 5. Cerrar sesión bloquea de nuevo el acceso a /cuenta/.
        self.client.post(reverse("ciudadania:logout"))
        respuesta = self.client.get(reverse("ciudadania:cuenta"))
        self.assertRedirects(respuesta, reverse("ciudadania:login"))

    def test_no_deja_registrar_el_mismo_correo_dos_veces(self):
        datos = {
            "email": "duplicado@example.mx",
            "password": "clave-super-larga",
            "password_confirmacion": "clave-super-larga",
        }
        self.client.post(reverse("ciudadania:registro"), datos)
        respuesta = self.client.post(reverse("ciudadania:registro"), datos)

        self.assertContains(respuesta, "Ya existe una cuenta")
        self.assertEqual(Ciudadano.objects.filter(email="duplicado@example.mx").count(), 1)

    def test_token_invalido_responde_400(self):
        respuesta = self.client.get(reverse("ciudadania:verificar_email", args=["basura"]))
        self.assertEqual(respuesta.status_code, 400)
