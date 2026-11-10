"""Ajustes de django-allauth a las políticas de autenticación (POL-AU-05, POL-AU-10, C12)."""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from cryptography.fernet import Fernet
from django import forms
from django.conf import settings

from bitacora.registro import anexar, origen_de
from cuentas import intentos


class AdaptadorCuentas(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Nadie se registra solo: ADM propone la cuenta y su rol, y GER lo aprueba (C12)."""
        return False

    def pre_authenticate(self, request, **credenciales):
        """Antes de mirar la contraseña: si ese nombre está en espera o bloqueado, no se intenta
        (POL-AU-07)."""
        hasta = intentos.espera_pendiente(credenciales.get("username", ""))
        if hasta:
            self._anotar_fallo(request, credenciales, "POL-AU-07")
            raise forms.ValidationError(intentos.mensaje_de_espera(hasta))
        super().pre_authenticate(request, **credenciales)

    def authenticate(self, request, **credenciales):
        usuario = super().authenticate(request, **credenciales)
        if usuario is not None:
            intentos.olvidar(credenciales.get("username", ""))
        return usuario

    def authentication_failed(self, request, **credenciales):
        fallos = intentos.registrar_fallo(credenciales.get("username", ""))
        self._anotar_fallo(request, credenciales, "POL-AU-07" if fallos >= intentos.DEMORA_DESDE else "")

    def _anotar_fallo(self, request, credenciales, regla):
        """El intento fallido va a la bitácora con la cuenta, si existe; el nombre escrito no."""
        from cuentas.models import Usuario

        cuenta = (
            Usuario.objects.filter(username__iexact=credenciales.get("username", ""))
            .values_list("pk", flat=True)
            .first()
        )
        anexar(
            accion="iniciar_sesion",
            resultado="denegado",
            objeto_tipo="cuenta",
            objeto_id=cuenta or "",
            regla=regla,
            origen=origen_de(request),
        )


class AdaptadorSegundoFactor(DefaultMFAAdapter):
    def encrypt(self, text):
        """El secreto TOTP y la semilla de los códigos de recuperación se guardan cifrados, con una
        clave que vive en Secret Manager y no en la base: una copia de la base no basta para
        generar códigos válidos."""
        return Fernet(settings.MFA_CLAVE).encrypt(text.encode()).decode()

    def decrypt(self, encrypted_text):
        return Fernet(settings.MFA_CLAVE).decrypt(encrypted_text.encode()).decode()

    def can_delete_authenticator(self, authenticator):
        """El segundo factor es obligatorio para todos los roles (POL-AU-05): nadie lo quita desde
        su sesión. Restablecerlo lo hace ADM con aprobación de GER (POL-AU-10)."""
        return False

    def get_totp_label(self, user):
        return user.get_username()
