from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Ciudadano


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
    email = forms.EmailField(label="Correo")
    nombre_completo = forms.CharField(label="Nombre completo", max_length=255, required=False)
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput, min_length=8)
    password_confirmacion = forms.CharField(label="Confirma tu contraseña", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"]
        if Ciudadano.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo.")
        return email


class LoginForm(forms.Form):
    email = forms.EmailField(label="Correo")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)


class SolicitarRestablecimientoForm(forms.Form):
    email = forms.EmailField(label="Correo")


class SolicitarReenvioVerificacionForm(forms.Form):
    email = forms.EmailField(label="Correo")


class NuevaPasswordForm(ConfirmacionDePasswordMixin, forms.Form):
    password = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput, min_length=8)
    password_confirmacion = forms.CharField(label="Confirma tu nueva contraseña", widget=forms.PasswordInput)


class CambiarPasswordForm(ConfirmacionDePasswordMixin, forms.Form):
    password_actual = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput)
    password = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput, min_length=8)
    password_confirmacion = forms.CharField(label="Confirma tu nueva contraseña", widget=forms.PasswordInput)


class SolicitarCambioEmailForm(forms.Form):
    password_actual = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput)
    nuevo_email = forms.EmailField(label="Nuevo correo")
