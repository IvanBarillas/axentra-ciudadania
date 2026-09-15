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


class FuerzaBrutaEnLoginTests(TestCase):
    def setUp(self):
        self.ciudadano = services.registrar_ciudadano(
            email="vecino@example.mx", password="clave-correcta"
        )
        services.verificar_email(services.generar_token_verificacion(self.ciudadano))

    def test_se_bloquea_tras_varios_intentos_fallidos_con_el_mismo_correo(self):
        for _ in range(services.MAX_INTENTOS_LOGIN_POR_CORREO):
            with self.assertRaises(services.CredencialesInvalidas):
                services.autenticar(email="vecino@example.mx", password="incorrecta", ip="10.0.0.1")

        with self.assertRaises(services.DemasiadosIntentos):
            services.autenticar(email="vecino@example.mx", password="clave-correcta", ip="10.0.0.1")

    def test_intentos_fallidos_a_otro_correo_no_bloquean_este(self):
        otro = services.registrar_ciudadano(email="otro@example.mx", password="x")
        for _ in range(services.MAX_INTENTOS_LOGIN_POR_CORREO):
            with self.assertRaises(services.CredencialesInvalidas):
                services.autenticar(email="otro@example.mx", password="mal", ip="10.0.0.1")

        # vecino@example.mx sigue pudiendo entrar normal.
        ciudadano = services.autenticar(
            email="vecino@example.mx", password="clave-correcta", ip="10.0.0.1"
        )
        self.assertEqual(ciudadano.id, self.ciudadano.id)

    def test_se_bloquea_por_ip_aunque_pruebe_correos_distintos(self):
        for i in range(services.MAX_INTENTOS_LOGIN_POR_IP):
            with self.assertRaises(services.CredencialesInvalidas):
                services.autenticar(email=f"inventado{i}@example.mx", password="x", ip="10.0.0.9")

        with self.assertRaises(services.DemasiadosIntentos):
            services.autenticar(email="vecino@example.mx", password="clave-correcta", ip="10.0.0.9")

    def test_un_login_exitoso_no_cuenta_como_fallido(self):
        services.autenticar(email="vecino@example.mx", password="clave-correcta", ip="10.0.0.1")
        services.autenticar(email="vecino@example.mx", password="clave-correcta", ip="10.0.0.1")

        # Sigue funcionando — los éxitos no acercan al límite de fallidos.
        ciudadano = services.autenticar(
            email="vecino@example.mx", password="clave-correcta", ip="10.0.0.1"
        )
        self.assertEqual(ciudadano.id, self.ciudadano.id)


class LimiteDeSolicitudesDeRestablecimientoTests(TestCase):
    def test_se_bloquea_tras_varias_solicitudes_al_mismo_correo(self):
        for _ in range(services.MAX_SOLICITUDES_RESTABLECIMIENTO_POR_CORREO):
            self.assertTrue(services.puede_solicitar_restablecimiento("vecino@example.mx", "10.0.0.1"))
            services.registrar_solicitud_restablecimiento("vecino@example.mx", "10.0.0.1")

        self.assertFalse(services.puede_solicitar_restablecimiento("vecino@example.mx", "10.0.0.1"))

    def test_el_limite_aplica_igual_si_la_cuenta_no_existe(self):
        # A propósito: así el límite mismo no delata si una cuenta es real.
        for _ in range(services.MAX_SOLICITUDES_RESTABLECIMIENTO_POR_CORREO):
            services.registrar_solicitud_restablecimiento("no-existe@example.mx", "10.0.0.1")

        self.assertFalse(services.puede_solicitar_restablecimiento("no-existe@example.mx", "10.0.0.1"))


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


class CambiarPasswordTests(TestCase):
    def setUp(self):
        self.ciudadano = services.registrar_ciudadano(email="a@example.mx", password="clave-vieja-larga")

    def test_cambia_con_la_contrasena_actual_correcta(self):
        services.cambiar_password(
            self.ciudadano, password_actual="clave-vieja-larga", password_nueva="clave-nueva-larga"
        )

        actualizado = Ciudadano.objects.get(id=self.ciudadano.id)
        self.assertTrue(actualizado.check_password("clave-nueva-larga"))

    def test_rechaza_si_la_contrasena_actual_es_incorrecta(self):
        with self.assertRaises(services.CredencialesInvalidas):
            services.cambiar_password(
                self.ciudadano, password_actual="esta-mal", password_nueva="clave-nueva-larga"
            )

        # No se tocó nada.
        actualizado = Ciudadano.objects.get(id=self.ciudadano.id)
        self.assertTrue(actualizado.check_password("clave-vieja-larga"))


class CambiarEmailTests(TestCase):
    def setUp(self):
        self.ciudadano = services.registrar_ciudadano(email="viejo@example.mx", password="clave-larga")

    def test_el_correo_no_cambia_hasta_confirmar(self):
        token = services.solicitar_cambio_de_email(
            self.ciudadano, password_actual="clave-larga", nuevo_email="nuevo@example.mx"
        )

        self.assertEqual(Ciudadano.objects.get(id=self.ciudadano.id).email, "viejo@example.mx")

        services.confirmar_cambio_de_email(token)

        actualizado = Ciudadano.objects.get(id=self.ciudadano.id)
        self.assertEqual(actualizado.email, "nuevo@example.mx")
        self.assertTrue(actualizado.email_verificado)

    def test_rechaza_si_la_contrasena_actual_es_incorrecta(self):
        with self.assertRaises(services.CredencialesInvalidas):
            services.solicitar_cambio_de_email(
                self.ciudadano, password_actual="mal", nuevo_email="nuevo@example.mx"
            )

    def test_rechaza_si_el_correo_nuevo_ya_lo_tiene_otra_cuenta(self):
        services.registrar_ciudadano(email="nuevo@example.mx", password="x")

        with self.assertRaises(services.CorreoYaRegistrado):
            services.solicitar_cambio_de_email(
                self.ciudadano, password_actual="clave-larga", nuevo_email="nuevo@example.mx"
            )

    def test_token_se_invalida_si_el_correo_ya_cambio_por_otro_camino(self):
        token = services.solicitar_cambio_de_email(
            self.ciudadano, password_actual="clave-larga", nuevo_email="nuevo@example.mx"
        )
        # El correo cambia por otra vía mientras el token seguía pendiente.
        self.ciudadano.email = "otro-camino@example.mx"
        self.ciudadano.save()

        with self.assertRaises(services.TokenInvalido):
            services.confirmar_cambio_de_email(token)

    def test_cambiar_password_no_invalida_un_cambio_de_correo_pendiente(self):
        # A diferencia del token de restablecimiento, este no depende de
        # la contraseña — cambiarla no debe tumbar un cambio de correo ya
        # en curso.
        token = services.solicitar_cambio_de_email(
            self.ciudadano, password_actual="clave-larga", nuevo_email="nuevo@example.mx"
        )
        services.cambiar_password(self.ciudadano, password_actual="clave-larga", password_nueva="otra-clave-larga")

        confirmado = services.confirmar_cambio_de_email(token)

        self.assertEqual(confirmado.email, "nuevo@example.mx")

    def test_token_de_un_solo_uso(self):
        token = services.solicitar_cambio_de_email(
            self.ciudadano, password_actual="clave-larga", nuevo_email="nuevo@example.mx"
        )
        services.confirmar_cambio_de_email(token)

        with self.assertRaises(services.TokenInvalido):
            services.confirmar_cambio_de_email(token)

    def test_alguien_mas_toma_el_correo_antes_de_que_se_confirme(self):
        token = services.solicitar_cambio_de_email(
            self.ciudadano, password_actual="clave-larga", nuevo_email="nuevo@example.mx"
        )
        services.registrar_ciudadano(email="nuevo@example.mx", password="x")

        with self.assertRaises(services.CorreoYaRegistrado):
            services.confirmar_cambio_de_email(token)
