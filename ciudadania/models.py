import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class CiudadanoManager(BaseUserManager):
    """
    No hereda comportamiento de `django.contrib.auth` más allá del hash de
    contraseña — `Ciudadano` nunca es `AUTH_USER_MODEL` (ver README), así
    que no hay `create_superuser` ni nada pensado para Django Admin/staff.
    """

    def create_ciudadano(self, email, password, nombre_completo="", **extra_fields):
        if not email:
            raise ValueError("Se requiere un correo.")

        email = self.normalize_email(email)
        ciudadano = self.model(email=email, nombre_completo=nombre_completo, **extra_fields)
        ciudadano.set_password(password)
        ciudadano.save(using=self._db)
        return ciudadano

    def get_queryset(self):
        # Baja lógica (mismo patrón que el Core, sección 15 de
        # 000_core_architecture.md): las consultas normales nunca ven
        # cuentas eliminadas.
        return super().get_queryset().filter(is_deleted=False)


class Ciudadano(AbstractBaseUser):
    """
    Identidad ciudadana — deliberadamente separada de `security.User`
    (personal). No usa `PermissionsMixin`: un ciudadano no tiene roles,
    pesos ni acceso administrativo, nunca entra al Hub de Axentra OS.

    UUID como identidad estable, igual que el resto del sistema (ver
    docs/apps/administrative-authority.md del Core: "la identidad estable
    es User.id (UUID), nunca el correo").
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    nombre_completo = models.CharField(max_length=255, blank=True)

    email_verificado = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = CiudadanoManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "ciudadano"
        verbose_name_plural = "ciudadanos"

    def __str__(self):
        return self.email


class EventoExpediente(models.Model):
    """
    Evento genérico de la línea de tiempo del ciudadano — ver
    docs/apps/panel-ciudadano-y-flujo-de-solicitudes.md, punto 2.
    `ciudadania` es dueño de este modelo porque ya es dueño de la
    identidad; otros satélites (trámites, situaciones de vida) escriben
    aquí vía `registrar_evento()` en vez de llevar su propio historial
    por separado, para no repetir la fragmentación ya documentada en
    axentra-core-django/docs/apps/public-municipal-portal.md.

    `satelite_origen` y `tipo_evento` son texto libre a propósito: este
    paquete no debe conocer qué satélites existen ni sus tipos de evento
    (mismo desacoplo que ya tiene el resto de `ciudadania` respecto a
    otros módulos), solo los guarda y los devuelve.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ciudadano = models.ForeignKey(
        Ciudadano, on_delete=models.CASCADE, related_name="eventos_expediente"
    )
    satelite_origen = models.CharField(max_length=50)
    tipo_evento = models.CharField(max_length=50)
    referencia = models.CharField(max_length=255, blank=True)
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["ciudadano", "satelite_origen", "creado_en"])]
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.satelite_origen}: {self.titulo}"


class TipoDocumento(models.Model):
    """
    Catálogo de tipos de documento de identidad que un ciudadano puede
    guardar en su expediente (RFC, CURP, Acta de nacimiento...) — ver
    docs/apps/panel-ciudadano-y-flujo-de-solicitudes.md, punto 3.

    Vive en `ciudadania`, no en un satélite como `axentra-mod-tramites`
    (decisión corregida en esa misma sesión, ver el commit que revierte
    el intento original en ese repo): son documentos de identidad del
    ciudadano, reutilizables entre trámites y entre cualquier otro
    satélite futuro que también necesite leerlos — igual criterio que
    ya se usó para `EventoExpediente`.

    `clave` es el identificador estable que cruza el límite hacia otros
    paquetes (ellos lo usan como texto libre, sin FK real — ver
    `services.subir_documento_a_expediente`); nunca el `id` interno.
    """

    clave = models.SlugField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)

    class Meta:
        verbose_name = "tipo de documento"
        verbose_name_plural = "tipos de documento"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Documento(models.Model):
    """
    Un documento del expediente del ciudadano. Un tipo de documento es
    único por ciudadano (UniqueConstraint más abajo): subir uno nuevo
    del mismo tipo SOBRESCRIBE este registro (ver
    services.subir_documento_a_expediente) — no se guarda historial de
    versiones del archivo en sí, solo el estado de revisión se resetea
    a PENDIENTE en cada sobrescritura.

    `archivo` siempre es un PDF: todo lo que sube el ciudadano se
    convierte al subirlo (ver services.convertir_a_pdf) — un solo
    formato de almacenamiento/revisión sin importar el formato de
    origen.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de revisión"
        ACEPTADO = "aceptado", "Aceptado"
        RECHAZADO = "rechazado", "Rechazado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ciudadano = models.ForeignKey(Ciudadano, on_delete=models.CASCADE, related_name="documentos")
    tipo_documento = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT, related_name="documentos"
    )
    archivo = models.FileField(upload_to="expedientes/%Y/%m/")
    nombre_original = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo_rechazo = models.TextField(blank=True, default="")
    subido_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        constraints = [
            models.UniqueConstraint(
                fields=["ciudadano", "tipo_documento"], name="un_documento_por_tipo_y_ciudadano"
            )
        ]
        ordering = ["-actualizado_en"]

    def __str__(self):
        return f"{self.tipo_documento.nombre} ({self.ciudadano.email})"


class IntentoAcceso(models.Model):
    """
    Bitácora mínima para frenar fuerza bruta — el equivalente a lo que
    `django-axes` hace para personal en el Core, pero `axes` está atado a
    `django.contrib.auth` (señales de `authenticate()`/`AUTH_USER_MODEL`)
    y `ciudadania` nunca pasa por ahí (ver README). Se implementa a mano
    y en BD (no en caché): así funciona igual con varios workers/procesos
    y sobrevive un reinicio, sin exigir que quien instale este paquete
    configure un backend de caché en particular.
    """

    class Accion(models.TextChoices):
        LOGIN = "login", "Inicio de sesión"
        RESTABLECIMIENTO = "restablecimiento", "Solicitud de restablecimiento"
        REENVIO_VERIFICACION = "reenvio_verificacion", "Reenvío de verificación de correo"

    accion = models.CharField(max_length=20, choices=Accion.choices)
    email = models.EmailField()
    # GenericIPAddressField porque REMOTE_ADDR puede no reflejar la IP real
    # detrás de un proxy inverso — mismo punto pendiente que ya tiene el
    # propio Core (ver docs/deployment/audit-continuity.md: "revisar
    # confianza en cabeceras IP del proxy"). Quien despliegue detrás de un
    # proxy debe configurar ProxyFix/similar para que esto sea confiable.
    ip = models.GenericIPAddressField(null=True, blank=True)
    exitoso = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["accion", "email", "creado_en"])]
