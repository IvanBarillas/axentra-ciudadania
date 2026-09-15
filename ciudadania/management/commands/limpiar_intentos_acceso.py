from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ciudadania.models import IntentoAcceso


class Command(BaseCommand):
    help = (
        "Borra registros de IntentoAcceso (bitácora de fuerza bruta) más "
        "viejos que --dias (default 30). Esta tabla crece con cada intento "
        "de login/restablecimiento/reenvío y nunca se limpia sola — correr "
        "esto periódicamente (cron, o la cola de quien instale el paquete)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=30,
            help="Antigüedad mínima en días para borrar un registro (default: 30).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo cuenta cuántos registros borraría, sin borrar nada.",
        )

    def handle(self, *args, **options):
        dias = options["dias"]
        if dias < 1:
            self.stderr.write(self.style.ERROR("--dias debe ser al menos 1."))
            return

        limite = timezone.now() - timedelta(days=dias)
        queryset = IntentoAcceso.objects.filter(creado_en__lt=limite)
        total = queryset.count()

        if options["dry_run"]:
            self.stdout.write(
                f"Borraría {total} registro(s) de IntentoAcceso más viejos que {dias} día(s)."
            )
            return

        queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Borrados {total} registro(s) de IntentoAcceso más viejos que {dias} día(s)."
            )
        )
