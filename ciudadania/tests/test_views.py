import re

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from ciudadania import services
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


class RestablecimientoDeContrasenaViewTests(TestCase):
    def _registrar_y_verificar(self, email="vecino@example.mx", password="clave-vieja-larga"):
        self.client.post(
            reverse("ciudadania:registro"),
            {"email": email, "password": password, "password_confirmacion": password},
        )
        match = re.search(r"http\S+/ciudadano/verificar/\S+/", mail.outbox[-1].body)
        self.client.get(match.group(0))

    def test_flujo_completo_de_restablecimiento(self):
        self._registrar_y_verificar()
        mail.outbox.clear()

        # 1. Pide el enlace.
        respuesta = self.client.post(
            reverse("ciudadania:solicitar_restablecimiento"), {"email": "vecino@example.mx"}
        )
        self.assertContains(respuesta, "Revisa tu correo")
        self.assertEqual(len(mail.outbox), 1)

        # 2. Extrae el enlace real y pone una contraseña nueva.
        match = re.search(r"http\S+/ciudadano/restablecer/\S+/", mail.outbox[0].body)
        self.assertIsNotNone(match, "El correo debe incluir el enlace de restablecimiento.")
        url_restablecimiento = match.group(0)
        respuesta = self.client.post(
            url_restablecimiento,
            {"password": "clave-nueva-larga", "password_confirmacion": "clave-nueva-larga"},
        )
        self.assertContains(respuesta, "Contraseña actualizada")

        # 3. La contraseña vieja ya no sirve; la nueva sí.
        respuesta = self.client.post(
            reverse("ciudadania:login"),
            {"email": "vecino@example.mx", "password": "clave-vieja-larga"},
        )
        self.assertContains(respuesta, "Correo o contraseña incorrectos")

        respuesta = self.client.post(
            reverse("ciudadania:login"),
            {"email": "vecino@example.mx", "password": "clave-nueva-larga"},
            follow=True,
        )
        self.assertContains(respuesta, "vecino@example.mx")

    def test_no_revela_si_el_correo_existe_o_no(self):
        respuesta_existe = self.client.post(
            reverse("ciudadania:solicitar_restablecimiento"), {"email": "no-existe@example.mx"}
        )
        self.assertContains(respuesta_existe, "Revisa tu correo")
        self.assertEqual(len(mail.outbox), 0)  # nadie a quien mandarle nada

    def test_enlace_ya_usado_no_sirve_dos_veces(self):
        self._registrar_y_verificar()
        mail.outbox.clear()
        self.client.post(reverse("ciudadania:solicitar_restablecimiento"), {"email": "vecino@example.mx"})
        match = re.search(r"http\S+/ciudadano/restablecer/\S+/", mail.outbox[0].body)
        url_restablecimiento = match.group(0)
        self.client.post(
            url_restablecimiento,
            {"password": "clave-nueva-larga", "password_confirmacion": "clave-nueva-larga"},
        )

        respuesta = self.client.get(url_restablecimiento)

        self.assertEqual(respuesta.status_code, 400)


class FuerzaBrutaViewTests(TestCase):
    def setUp(self):
        self.ciudadano = services.registrar_ciudadano(
            email="vecino@example.mx", password="clave-correcta"
        )
        services.verificar_email(services.generar_token_verificacion(self.ciudadano))

    def test_login_se_bloquea_tras_varios_intentos_y_lo_dice(self):
        for _ in range(services.MAX_INTENTOS_LOGIN_POR_CORREO):
            self.client.post(
                reverse("ciudadania:login"),
                {"email": "vecino@example.mx", "password": "incorrecta"},
            )

        respuesta = self.client.post(
            reverse("ciudadania:login"),
            {"email": "vecino@example.mx", "password": "clave-correcta"},
        )

        self.assertContains(respuesta, "Demasiados intentos")

    def test_restablecimiento_repetido_sigue_dando_la_misma_respuesta(self):
        for _ in range(services.MAX_SOLICITUDES_RESTABLECIMIENTO_POR_CORREO + 2):
            respuesta = self.client.post(
                reverse("ciudadania:solicitar_restablecimiento"), {"email": "vecino@example.mx"}
            )
            self.assertContains(respuesta, "Revisa tu correo")

        # Aun así, no se mandó un correo por cada solicitud una vez bloqueado.
        self.assertLess(len(mail.outbox), services.MAX_SOLICITUDES_RESTABLECIMIENTO_POR_CORREO + 2)


class CuentaLogueadaTests(TestCase):
    def setUp(self):
        self.ciudadano = services.registrar_ciudadano(
            email="vecino@example.mx", password="clave-vieja-larga", nombre_completo="Vecino"
        )
        services.verificar_email(services.generar_token_verificacion(self.ciudadano))
        self.client.post(
            reverse("ciudadania:login"),
            {"email": "vecino@example.mx", "password": "clave-vieja-larga"},
        )

    def test_cambiar_password_sin_sesion_redirige_a_login(self):
        self.client.post(reverse("ciudadania:logout"))

        respuesta = self.client.get(reverse("ciudadania:cambiar_password"))

        self.assertRedirects(respuesta, reverse("ciudadania:login"))

    def test_cambia_la_contrasena_y_sirve_para_el_siguiente_login(self):
        respuesta = self.client.post(
            reverse("ciudadania:cambiar_password"),
            {
                "password_actual": "clave-vieja-larga",
                "password": "clave-nueva-larga",
                "password_confirmacion": "clave-nueva-larga",
            },
        )
        self.assertContains(respuesta, "Contraseña actualizada")

        self.client.post(reverse("ciudadania:logout"))
        respuesta = self.client.post(
            reverse("ciudadania:login"),
            {"email": "vecino@example.mx", "password": "clave-nueva-larga"},
            follow=True,
        )
        self.assertContains(respuesta, "Vecino")

    def test_cambio_de_email_de_principio_a_fin(self):
        respuesta = self.client.post(
            reverse("ciudadania:solicitar_cambio_email"),
            {"password_actual": "clave-vieja-larga", "nuevo_email": "nuevo@example.mx"},
        )
        self.assertContains(respuesta, "Confirma tu nuevo correo")

        # El correo viejo sigue siendo el vigente hasta confirmar.
        self.assertEqual(
            Ciudadano.objects.get(id=self.ciudadano.id).email, "vecino@example.mx"
        )

        match = re.search(r"http\S+/ciudadano/cuenta/email/confirmar/\S+/", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        respuesta = self.client.get(match.group(0))

        self.assertContains(respuesta, "nuevo@example.mx")
        self.assertEqual(Ciudadano.objects.get(id=self.ciudadano.id).email, "nuevo@example.mx")
