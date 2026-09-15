from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from ciudadania import services
from ciudadania.models import Ciudadano


class RegistroYVerificacionTests(TestCase):
    def test_ciudadano_nuevo_no_esta_verificado(self):
        ciudadano = services.registrar_ciudadano(email="a@example.mx", password="clave1234")
        self.assertFalse(ciudadano.email_verificado)

    def test_token_valido_marca_verificado(self):
        ciudadano = services.registrar_ciudadano(email="a@example.mx", password="clave1234")
        token = services.generar_token_verificacion(ciudadano)

        verificado = services.verificar_email(token)

        self.assertEqual(verificado.id, ciudadano.id)
        self.assertTrue(Ciudadano.objects.get(id=ciudadano.id).email_verificado)

    def test_token_invalido_lanza_excepcion(self):
        with self.assertRaises(services.TokenInvalido):
            services.verificar_email("esto-no-es-un-token-real")

    def test_token_de_ciudadano_inexistente_lanza_excepcion(self):
        ciudadano = services.registrar_ciudadano(email="a@example.mx", password="clave1234")
        token = services.generar_token_verificacion(ciudadano)
        ciudadano.delete()

        with self.assertRaises(services.TokenInvalido):
            services.verificar_email(token)


class AutenticacionTests(TestCase):
    def setUp(self):
        self.ciudadano = services.registrar_ciudadano(
            email="vecino@example.mx", password="clave-correcta"
        )

    def test_no_deja_entrar_sin_verificar_correo(self):
        with self.assertRaises(services.CorreoNoVerificado):
            services.autenticar(email="vecino@example.mx", password="clave-correcta")

    def test_entra_despues_de_verificar(self):
        services.verificar_email(services.generar_token_verificacion(self.ciudadano))

        ciudadano = services.autenticar(email="vecino@example.mx", password="clave-correcta")

        self.assertEqual(ciudadano.id, self.ciudadano.id)

    def test_contrasena_incorrecta_no_distingue_el_motivo(self):
        services.verificar_email(services.generar_token_verificacion(self.ciudadano))

        with self.assertRaises(services.CredencialesInvalidas):
            services.autenticar(email="vecino@example.mx", password="clave-incorrecta")

    def test_correo_inexistente_da_el_mismo_error_generico(self):
        with self.assertRaises(services.CredencialesInvalidas):
            services.autenticar(email="no-existe@example.mx", password="lo-que-sea")


class RestablecimientoDeContrasenaTests(TestCase):
    def setUp(self):
        self.ciudadano = services.registrar_ciudadano(email="vecino@example.mx", password="clave-vieja")

    def test_token_valido_permite_restablecer(self):
        token = services.generar_token_restablecimiento(self.ciudadano)

        resuelto = services.resolver_token_restablecimiento(token)
        services.restablecer_contrasena(resuelto, "clave-nueva-segura")

        actualizado = Ciudadano.objects.get(id=self.ciudadano.id)
        self.assertTrue(actualizado.check_password("clave-nueva-segura"))
        self.assertFalse(actualizado.check_password("clave-vieja"))

    def test_token_es_de_un_solo_uso(self):
        token = services.generar_token_restablecimiento(self.ciudadano)
        ciudadano = services.resolver_token_restablecimiento(token)
        services.restablecer_contrasena(ciudadano, "clave-nueva-segura")

        with self.assertRaises(services.TokenInvalido):
            services.resolver_token_restablecimiento(token)

    def test_token_se_invalida_si_la_contrasena_ya_cambio_por_otro_medio(self):
        token = services.generar_token_restablecimiento(self.ciudadano)
        self.ciudadano.set_password("otra-clave-distinta")
        self.ciudadano.save()

        with self.assertRaises(services.TokenInvalido):
            services.resolver_token_restablecimiento(token)

    def test_token_basura_lanza_excepcion(self):
        with self.assertRaises(services.TokenInvalido):
            services.resolver_token_restablecimiento("esto-no-es-un-token-real")


class SesionTests(TestCase):
    def _request_con_sesion(self):
        request = RequestFactory().get("/")
        request.session = SessionStore()
        return request

    def test_iniciar_y_leer_sesion(self):
        ciudadano = services.registrar_ciudadano(email="a@example.mx", password="x")
        request = self._request_con_sesion()

        services.iniciar_sesion(request, ciudadano)

        self.assertEqual(services.ciudadano_actual(request).id, ciudadano.id)

    def test_sin_sesion_no_hay_ciudadano_actual(self):
        request = self._request_con_sesion()

        self.assertIsNone(services.ciudadano_actual(request))

    def test_cerrar_sesion_limpia_el_ciudadano_actual(self):
        ciudadano = services.registrar_ciudadano(email="a@example.mx", password="x")
        request = self._request_con_sesion()
        services.iniciar_sesion(request, ciudadano)

        services.cerrar_sesion(request)

        self.assertIsNone(services.ciudadano_actual(request))


class DatosPublicosTests(TestCase):
    def test_devuelve_snapshot_sin_contrasena(self):
        ciudadano = services.registrar_ciudadano(
            email="a@example.mx", password="secreta", nombre_completo="Ana Pérez"
        )

        datos = services.obtener_datos_publicos(ciudadano.id)

        self.assertEqual(datos.nombre_completo, "Ana Pérez")
        self.assertEqual(datos.email, "a@example.mx")
        self.assertFalse(datos.email_verificado)
        self.assertFalse(hasattr(datos, "password"))

    def test_id_inexistente_devuelve_none(self):
        self.assertIsNone(services.obtener_datos_publicos("00000000-0000-0000-0000-000000000000"))
