from django.db import migrations

# Bug real reportado (probando en vivo): el selector "tipo de documento"
# del formulario de "Mi expediente" salía vacío — TipoDocumento nunca
# tenía filas. Esperar a que un funcionario las cree a mano en el Admin
# antes de que CUALQUIER ciudadano pueda usar la función es al revés:
# son catálogo, no datos de negocio de una instalación particular.
# Sembrados aquí (RunPython, corre solo con `migrate`, sin tocar el
# Hub) los tipos de identidad más comunes en trámites municipales
# mexicanos. Cualquier instalación puede agregar más desde el Admin
# (TipoDocumentoAdmin ya lo permite) — esto es solo el punto de partida.
TIPOS_INICIALES = [
    ("rfc", "RFC"),
    ("curp", "CURP"),
    ("acta-de-nacimiento", "Acta de nacimiento"),
    ("identificacion-oficial", "Identificación oficial (INE)"),
    ("comprobante-de-domicilio", "Comprobante de domicilio"),
]


def sembrar_tipos(apps, schema_editor):
    TipoDocumento = apps.get_model("ciudadania", "TipoDocumento")
    for clave, nombre in TIPOS_INICIALES:
        TipoDocumento.objects.get_or_create(clave=clave, defaults={"nombre": nombre})


def quitar_tipos(apps, schema_editor):
    TipoDocumento = apps.get_model("ciudadania", "TipoDocumento")
    claves = [clave for clave, _ in TIPOS_INICIALES]
    TipoDocumento.objects.filter(clave__in=claves).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ciudadania", "0005_tipodocumento_documento"),
    ]

    operations = [
        migrations.RunPython(sembrar_tipos, quitar_tipos),
    ]
