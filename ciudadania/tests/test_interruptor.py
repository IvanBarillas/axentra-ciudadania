from django.test import TestCase, override_settings
from django.urls import reverse

from ciudadania import services


class InterruptorTests(TestCase):
    def test_habilitado_por_default(self):
        self.assertTrue(services.ciudadania_habilitada())

    @override_settings(CIUDADANIA_HABILITADA=False)
    def test_se_puede_apagar(self):
        self.assertFalse(services.ciudadania_habilitada())


@override_settings(CIUDADANIA_HABILITADA=False)
class VistasApagadasTests(TestCase):
    """
    Con el interruptor apagado, TODAS las vistas públicas deben
    comportarse como si no existieran (404, no 403 — no delatar que la
    función está ahí pero deshabilitada).
    """

    def test_registro_da_404(self):
        respuesta = self.client.get(reverse("ciudadania:registro"))
        self.assertEqual(respuesta.status_code, 404)

    def test_login_da_404(self):
        respuesta = self.client.get(reverse("ciudadania:login"))
        self.assertEqual(respuesta.status_code, 404)

    def test_solicitar_restablecimiento_da_404(self):
        respuesta = self.client.get(reverse("ciudadania:solicitar_restablecimiento"))
        self.assertEqual(respuesta.status_code, 404)

    def test_reenviar_verificacion_da_404(self):
        respuesta = self.client.get(reverse("ciudadania:reenviar_verificacion"))
        self.assertEqual(respuesta.status_code, 404)

    def test_cuenta_da_404_incluso_con_sesion_activa(self):
        ciudadano = services.registrar_ciudadano(email="a@example.mx", password="Clave-Larga-987")
        services.verificar_email(services.generar_token_verificacion(ciudadano))

        # Se habilita solo para poder iniciar sesión, y se apaga después
        # — simula una cuenta creada antes de apagar el interruptor.
        with override_settings(CIUDADANIA_HABILITADA=True):
            self.client.post(
                reverse("ciudadania:login"),
                {"email": "a@example.mx", "password": "Clave-Larga-987"},
            )

        respuesta = self.client.get(reverse("ciudadania:cuenta"))
        self.assertEqual(respuesta.status_code, 404)
