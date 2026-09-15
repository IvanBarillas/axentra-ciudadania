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
