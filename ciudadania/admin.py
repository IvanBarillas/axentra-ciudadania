from django.contrib import admin

from .models import (
    Ciudadano,
    Documento,
    EventoExpediente,
    IntentoAcceso,
    SeguimientoProceso,
    TipoDocumento,
)


@admin.register(Ciudadano)
class CiudadanoAdmin(admin.ModelAdmin):
    """
    Para soporte puntual (desactivar/dar de baja una cuenta, revisar un
    caso), no para altas — esas siempre pasan por el flujo público de
    registro (hashea la contraseña, manda verificación). `password` queda
    de solo lectura: nunca se edita un hash a mano desde aquí.
    """

    list_display = ("email", "nombre_completo", "email_verificado", "is_active", "is_deleted", "creado_en")
    list_filter = ("email_verificado", "is_active", "is_deleted")
    search_fields = ("email", "nombre_completo")
    readonly_fields = ("id", "password", "creado_en", "actualizado_en", "last_login")
    ordering = ("-creado_en",)

    def has_add_permission(self, request):
        return False


@admin.register(IntentoAcceso)
class IntentoAccesoAdmin(admin.ModelAdmin):
    """
    Bitácora de solo lectura — mismo criterio que el Core con
    DepartmentAccessGrant: sirve para que soporte entienda por qué alguien
    quedó bloqueado, no se edita ni se borra desde aquí (la purga es el
    comando de gestión limpiar_intentos_acceso, no el Admin).
    """

    list_display = ("accion", "email", "ip", "exitoso", "creado_en")
    list_filter = ("accion", "exitoso")
    search_fields = ("email", "ip")
    ordering = ("-creado_en",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "clave")
    search_fields = ("nombre", "clave")
    prepopulated_fields = {"clave": ("nombre",)}


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    """
    Solo lectura — esto lo escriben los ciudadanos vía el flujo público
    de expediente, y lo acepta/rechaza el panel de revisión de un
    satélite (vía `services.actualizar_estado_documento`), no una
    persona a mano desde aquí.
    """

    list_display = ("tipo_documento", "ciudadano", "estado", "subido_en", "actualizado_en")
    list_filter = ("estado", "tipo_documento")
    search_fields = ("ciudadano__email",)
    ordering = ("-actualizado_en",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoExpediente)
class EventoExpedienteAdmin(admin.ModelAdmin):
    """
    Solo lectura, igual que IntentoAcceso: esto lo escriben los
    satélites vía `registrar_evento()`, no una persona a mano desde
    el Admin.
    """

    list_display = ("ciudadano", "satelite_origen", "tipo_evento", "titulo", "creado_en")
    list_filter = ("satelite_origen", "tipo_evento")
    search_fields = ("titulo", "descripcion", "ciudadano__email")
    ordering = ("-creado_en",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SeguimientoProceso)
class SeguimientoProcesoAdmin(admin.ModelAdmin):
    """
    Solo lectura, mismo criterio que EventoExpediente: esto lo escriben
    los satélites vía iniciar_seguimiento()/marcar_paso_en_seguimiento(),
    no una persona a mano desde el Admin.
    """

    list_display = ("ciudadano", "satelite_origen", "titulo", "estado", "iniciado_en", "actualizado_en")
    list_filter = ("satelite_origen", "estado")
    search_fields = ("titulo", "referencia_proceso", "ciudadano__email")
    ordering = ("-actualizado_en",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
