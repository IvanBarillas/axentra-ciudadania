from django.test import TestCase

from ciudadania.models import Ciudadano, EventoExpediente


class CiudadanoModelTests(TestCase):
    def test_create_ciudadano_hashea_la_contrasena(self):
        ciudadano = Ciudadano.objects.create_ciudadano(
            email="vecino@example.mx",
            password="clave-super-secreta",
            nombre_completo="Vecino de Prueba",
        )

        self.assertNotEqual(ciudadano.password, "clave-super-secreta")
        self.assertTrue(ciudadano.check_password("clave-super-secreta"))
        self.assertFalse(ciudadano.check_password("clave-incorrecta"))

    def test_email_se_normaliza(self):
        ciudadano = Ciudadano.objects.create_ciudadano(
            email="Vecino@Example.MX",
            password="clave-super-secreta",
        )

        self.assertEqual(ciudadano.email, "Vecino@example.mx")

    def test_baja_logica_se_excluye_del_manager(self):
        ciudadano = Ciudadano.objects.create_ciudadano(email="baja@example.mx", password="x")
        ciudadano.is_deleted = True
        ciudadano.save()

        self.assertFalse(Ciudadano.objects.filter(email="baja@example.mx").exists())

    def test_identidad_es_uuid_no_el_correo(self):
        ciudadano = Ciudadano.objects.create_ciudadano(email="id@example.mx", password="x")

        self.assertIsNotNone(ciudadano.id)
        self.assertEqual(len(str(ciudadano.id)), 36)  # forma de un UUID


class EventoExpedienteModelTests(TestCase):
    def test_se_ordena_del_mas_reciente_al_mas_antiguo_por_defecto(self):
        ciudadano = Ciudadano.objects.create_ciudadano(email="vecino@example.mx", password="x")
        primero = EventoExpediente.objects.create(
            ciudadano=ciudadano, satelite_origen="tramites", tipo_evento="x", titulo="Primero"
        )
        segundo = EventoExpediente.objects.create(
            ciudadano=ciudadano, satelite_origen="tramites", tipo_evento="x", titulo="Segundo"
        )

        self.assertEqual(list(EventoExpediente.objects.all()), [segundo, primero])

    def test_se_borra_en_cascada_con_el_ciudadano(self):
        ciudadano = Ciudadano.objects.create_ciudadano(email="vecino@example.mx", password="x")
        EventoExpediente.objects.create(
            ciudadano=ciudadano, satelite_origen="tramites", tipo_evento="x", titulo="Evento"
        )

        ciudadano.delete()

        self.assertFalse(EventoExpediente.objects.exists())
