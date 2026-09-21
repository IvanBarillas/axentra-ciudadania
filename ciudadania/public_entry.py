# ciudadania/public_entry.py
"""
Entrada de Ciudadanía al directorio público del Core (/directorio/).

Descubierto por apps.shared.module_sdk.registry (busca <app>.public_entry
para cada app instalada). NO es un module_manifest.py a propósito: este
paquete no tiene panel en el Hub, así que no genera AppModule ni tarjeta
de personal — solo esta entrada para el ciudadano.

El Core llama a get_public_entry() en cada petición, por eso el
interruptor CIUDADANIA_HABILITADA la oculta sin reiniciar. La URL es un
enlace entre dominios: base por settings (CIUDADANIA_PUBLIC_BASE_URL),
nunca reverse(). Sin esa setting no aparece.
"""
from django.conf import settings

from apps.shared.module_sdk import PublicEntry

# Superficie pública (vistas de la cuenta ciudadana) que el Core monta en el
# dominio del ciudadano, junto a Trámites y Situaciones (una sola sesión).
# Constantes ESTÁTICAS a propósito: el urlconf se arma una vez al arrancar, y
# get_public_entry() se evalúa por petición y puede devolver None (interruptor
# CIUDADANIA_HABILITADA) sin que las rutas deban desmontarse. Con este prefijo,
# CIUDADANIA_PUBLIC_BASE_URL debe incluirlo (https://<ciudadano>/ciudadano).
PUBLIC_URLCONF = "ciudadania.urls"
PUBLIC_PREFIX = "ciudadano/"


def get_public_entry():
    from .services import ciudadania_habilitada

    if not ciudadania_habilitada():
        return None
    base = getattr(settings, "CIUDADANIA_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base:
        return None
    return PublicEntry(
        code="ciudadania",
        name="Mi cuenta ciudadana",
        description=(
            "Crea tu cuenta o inicia sesión para dar seguimiento a tus trámites "
            "y guías desde un solo lugar."
        ),
        url=f"{base}/cuenta/",
        icon="user-round",
    )
