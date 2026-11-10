"""Lo que pasa al iniciar y al cerrar sesión: el inicio de la sesión para su máximo de 12 horas y
el registro en la bitácora (POL-BT-01)."""

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from bitacora.registro import anexar, origen_de
from cuentas.sesiones import marcar_inicio


@receiver(user_logged_in)
def al_iniciar_sesion(sender, request, user, **kwargs):
    marcar_inicio(request)
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
