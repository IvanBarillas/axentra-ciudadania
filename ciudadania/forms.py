from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Ciudadano, TipoDocumento

# Mismo patrón que ya usan axentra-mod-tramites/axentra-mod-situaciones-de-vida
# para sus propios formularios: clase de Tailwind directa en el widget, en vez
# de un ModelForm/mixin genérico — este paquete no tiene uno propio todavía y
# son pocos campos.
_INPUT_CLASS = (
    "w-full rounded-xl border border-gray-200 bg-gray-50/60 px-4 py-2.5 text-sm "
    "text-gray-900 outline-none transition-all focus:border-brand-primary "
    "focus:bg-white focus:ring-1 focus:ring-brand-primary"
)


class ConfirmacionDePasswordMixin:
    """
    Comparte, entre RegistroForm/NuevaPasswordForm/CambiarPasswordForm
    (todas declaran su campo nuevo como "password"):

    - la fortaleza de la contraseña, vía los validadores estándar de
      Django (AUTH_PASSWORD_VALIDATORS) — la política real (longitud,
      contraseñas comunes, etc.) la define quien instala este paquete,
      igual que ya hace Django para AUTH_USER_MODEL. Hallazgo real: como
      `Ciudadano` no es AUTH_USER_MODEL, estos validadores nunca se
      ejecutaban solos — hay que llamarlos a mano.
    - la regla "las dos contraseñas deben coincidir".
    """

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            try:
                validate_password(password)
            except DjangoValidationError as exc:
                raise forms.ValidationError(list(exc.messages))
        return password

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirmacion = cleaned.get("password_confirmacion")
        if password and confirmacion and password != confirmacion:
            self.add_error("password_confirmacion", "Las contraseñas no coinciden.")
        return cleaned


class RegistroForm(ConfirmacionDePasswordMixin, forms.Form):
    email = forms.EmailField(label="Correo", widget=forms.EmailInput(attrs={"class": _INPUT_CLASS}))
    nombre_completo = forms.CharField(label="Nombre completo", max_length=255, required=False, widget=forms.TextInput(attrs={"class": _INPUT_CLASS}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"class": _INPUT_CLASS}), min_length=8)
    password_confirmacion = forms.CharField(label="Confirma tu contraseña", widget=forms.PasswordInput(attrs={"class": _INPUT_CLASS}))

    def clean_email(self):
        email = self.cleaned_data["email"]
        if Ciudadano.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo.")
        return email


class LoginForm(forms.Form):
    email = forms.EmailField(label="Correo", widget=forms.EmailInput(attrs={"class": _INPUT_CLASS}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"class": _INPUT_CLASS}))


class SolicitarRestablecimientoForm(forms.Form):
    email = forms.EmailField(label="Correo", widget=forms.EmailInput(attrs={"class": _INPUT_CLASS}))


class SolicitarReenvioVerificacionForm(forms.Form):
    email = forms.EmailField(label="Correo", widget=forms.EmailInput(attrs={"class": _INPUT_CLASS}))


class NuevaPasswordForm(ConfirmacionDePasswordMixin, forms.Form):
    password = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput(attrs={"class": _INPUT_CLASS}), min_length=8)
    password_confirmacion = forms.CharField(label="Confirma tu nueva contraseña", widget=forms.PasswordInput(attrs={"class": _INPUT_CLASS}))


class CambiarPasswordForm(ConfirmacionDePasswordMixin, forms.Form):
    password_actual = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput(attrs={"class": _INPUT_CLASS}))
    password = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput(attrs={"class": _INPUT_CLASS}), min_length=8)
    password_confirmacion = forms.CharField(label="Confirma tu nueva contraseña", widget=forms.PasswordInput(attrs={"class": _INPUT_CLASS}))


class SolicitarCambioEmailForm(forms.Form):
    password_actual = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput(attrs={"class": _INPUT_CLASS}))
    nuevo_email = forms.EmailField(label="Nuevo correo", widget=forms.EmailInput(attrs={"class": _INPUT_CLASS}))


class DocumentoUploadForm(forms.Form):
    """Subida al expediente — no es ModelForm porque el archivo se
    convierte a PDF en el servicio (services.subir_documento_a_expediente)
    antes de tocar el modelo Documento."""

    tipo_documento = forms.ModelChoiceField(
        queryset=TipoDocumento.objects.all(), label="Tipo de documento",
        widget=forms.Select(attrs={"class": _INPUT_CLASS}),
    )
    archivo = forms.FileField(
        label="Archivo (imagen o PDF)",
        widget=forms.ClearableFileInput(attrs={
            "class": (
                "block w-full text-xs text-gray-500 "
                "file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 "
                "file:text-xs file:font-black file:uppercase file:tracking-widest "
                "file:bg-brand-primary file:text-white hover:file:brightness-110 "
                "file:transition-colors file:cursor-pointer"
            )
        }),
    )
