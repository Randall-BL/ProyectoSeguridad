"""Ajustes de django-allauth a las políticas de autenticación (POL-AU-05, POL-AU-10, C12)."""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from cryptography.fernet import Fernet
from django.conf import settings


class AdaptadorCuentas(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Nadie se registra solo: ADM propone la cuenta y su rol, y GER lo aprueba (C12)."""
        return False


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
