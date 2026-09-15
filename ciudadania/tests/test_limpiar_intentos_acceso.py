from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ciudadania.models import IntentoAcceso


def _crear_intento(hace_dias):
    intento = IntentoAcceso.objects.create(accion=IntentoAcceso.Accion.LOGIN, email="a@example.mx")
    # auto_now_add solo aplica en save() — .update() a nivel de queryset lo
    # sortea, que es justo lo que se necesita para simular un registro viejo.
    fecha = timezone.now() - timedelta(days=hace_dias)
    IntentoAcceso.objects.filter(pk=intento.pk).update(creado_en=fecha)
    return intento


class LimpiarIntentosAccesoTests(TestCase):
    def test_borra_solo_lo_mas_viejo_que_el_limite(self):
        _crear_intento(hace_dias=45)
        _crear_intento(hace_dias=1)

        call_command("limpiar_intentos_acceso", "--dias=30", stdout=StringIO())

        self.assertEqual(IntentoAcceso.objects.count(), 1)
        self.assertEqual(IntentoAcceso.objects.first().creado_en.date(), (timezone.now() - timedelta(days=1)).date())

    def test_dry_run_no_borra_nada(self):
        _crear_intento(hace_dias=45)

        salida = StringIO()
        call_command("limpiar_intentos_acceso", "--dias=30", "--dry-run", stdout=salida)

        self.assertEqual(IntentoAcceso.objects.count(), 1)
        self.assertIn("Borraría 1", salida.getvalue())

    def test_dias_personalizado(self):
        _crear_intento(hace_dias=10)

        call_command("limpiar_intentos_acceso", "--dias=5", stdout=StringIO())

        self.assertEqual(IntentoAcceso.objects.count(), 0)

    def test_nada_que_borrar_no_revienta(self):
        salida = StringIO()
        call_command("limpiar_intentos_acceso", stdout=salida)

        self.assertIn("Borrados 0", salida.getvalue())
