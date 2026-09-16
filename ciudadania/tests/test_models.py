from django.db import IntegrityError, transaction
from django.test import TestCase

from ciudadania.models import Ciudadano, Documento, EventoExpediente, TipoDocumento


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


class DocumentoModelTests(TestCase):
    def setUp(self):
        self.ciudadano = Ciudadano.objects.create_ciudadano(email="vecino@example.mx", password="x")
        self.tipo_rfc = TipoDocumento.objects.get(clave="rfc")

    def test_es_unico_por_tipo_y_ciudadano(self):
        Documento.objects.create(
            ciudadano=self.ciudadano, tipo_documento=self.tipo_rfc, archivo="expedientes/x.pdf"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Documento.objects.create(
                    ciudadano=self.ciudadano, tipo_documento=self.tipo_rfc, archivo="expedientes/y.pdf"
                )

    def test_mismo_tipo_para_otro_ciudadano_no_choca(self):
        Documento.objects.create(
            ciudadano=self.ciudadano, tipo_documento=self.tipo_rfc, archivo="expedientes/x.pdf"
        )
        otro = Ciudadano.objects.create_ciudadano(email="otro@example.mx", password="x")

        documento_otro = Documento.objects.create(
            ciudadano=otro, tipo_documento=self.tipo_rfc, archivo="expedientes/y.pdf"
        )

        self.assertIsNotNone(documento_otro.id)

    def test_estado_por_defecto_es_pendiente(self):
        documento = Documento.objects.create(
            ciudadano=self.ciudadano, tipo_documento=self.tipo_rfc, archivo="expedientes/x.pdf"
        )

        self.assertEqual(documento.estado, Documento.Estado.PENDIENTE)

    def test_se_borra_en_cascada_con_el_ciudadano(self):
        Documento.objects.create(
            ciudadano=self.ciudadano, tipo_documento=self.tipo_rfc, archivo="expedientes/x.pdf"
        )

        self.ciudadano.delete()

        self.assertFalse(Documento.objects.exists())


class SemillaTipoDocumentoTests(TestCase):
    """Bug real reportado (probando en vivo): el selector de "Mi
    expediente" salía vacío — nadie sembraba TipoDocumento. La migración
    0006 la siembra sola, sin pasar por el Admin ni por el Hub."""

    def test_los_tipos_comunes_ya_existen_tras_migrar(self):
        claves_esperadas = {
            "rfc",
            "curp",
            "acta-de-nacimiento",
            "identificacion-oficial",
            "comprobante-de-domicilio",
        }
        claves_reales = set(TipoDocumento.objects.values_list("clave", flat=True))

        self.assertTrue(claves_esperadas.issubset(claves_reales))
