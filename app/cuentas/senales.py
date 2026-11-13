"""Lo que pasa al iniciar y al cerrar sesión: el inicio de la sesión para su máximo de 12 horas y
el registro en la bitácora (POL-BT-01)."""

from allauth.account.internal.flows.login import record_authentication
from allauth.mfa.models import Authenticator
from allauth.mfa.utils import is_mfa_enabled
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from bitacora.registro import anexar, origen_de
from cuentas.sesiones import marcar_inicio


@receiver(user_logged_in)
def al_iniciar_sesion(sender, request, user, **kwargs):
    marcar_inicio(request)
    if not is_mfa_enabled(user, types=[Authenticator.Type.TOTP]):
        # Quien entra sin TOTP va directo a activarlo, y allauth pide la contraseña otra vez para
        # eso. La acaba de escribir: vale como reautenticación durante los cinco minutos de
        # siempre, y solo mientras no tenga el segundo factor.
        record_authentication(request, user, "password", reauthenticated=True)
    anexar(
        accion="iniciar_sesion",
        resultado="concedido",
        usuario=user,
        rol=user.rol,
        objeto_tipo="cuenta",
        objeto_id=user.pk,
        origen=origen_de(request),
        sesion=request.session.session_key or "",
    )


@receiver(user_logged_out)
def al_cerrar_sesion(sender, request, user, **kwargs):
    if user is None:
        return
    anexar(
        accion="cerrar_sesion",
        resultado="concedido",
        usuario=user,
        rol=user.rol,
        objeto_tipo="cuenta",
        objeto_id=user.pk,
        origen=origen_de(request),
        sesion=request.session.session_key or "",
    )
