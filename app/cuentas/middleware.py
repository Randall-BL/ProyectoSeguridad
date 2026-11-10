"""El segundo factor es obligatorio para todos los roles (POL-AU-05)."""

from allauth.account.authentication import get_authentication_records
from allauth.mfa.models import Authenticator
from allauth.mfa.utils import is_mfa_enabled
from django.contrib import messages
from django.shortcuts import redirect

# Lo único que puede hacer quien todavía no tiene TOTP: activarlo (con la reautenticación que
# allauth pide antes), guardar sus códigos de recuperación o salir.
PERMITIDAS_SIN_SEGUNDO_FACTOR = {
    "mfa_activate_totp",
    "mfa_view_recovery_codes",
    "mfa_download_recovery_codes",
    "account_reauthenticate",
    "account_logout",
    "salud",
}


class ExigirSegundoFactor:
    """Una sesión iniciada sin TOTP solo sirve para activarlo. Las cuentas nuevas entran por
    primera vez con su contraseña y tienen que enrolarse antes de ver o hacer cualquier cosa."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, vista, args, kwargs):
        if not request.user.is_authenticated:
            return None
        if request.resolver_match and request.resolver_match.url_name in PERMITIDAS_SIN_SEGUNDO_FACTOR:
            return None
        if _paso_segundo_factor(request):
            return None
        messages.info(request, "El segundo factor es obligatorio: actívelo para continuar.")
        return redirect("mfa_activate_totp")


def _paso_segundo_factor(request):
    """En esta sesión ya usó el segundo factor, o lo acaba de activar."""
    if any(r.get("method") == "mfa" for r in get_authentication_records(request, request.user)):
        return True
    return is_mfa_enabled(request.user, types=[Authenticator.Type.TOTP])
