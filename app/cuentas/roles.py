"""Rol activo de la sesión (tarea 3.8): la exclusión dinámica entre técnico y verificador.

Cada cuenta tiene un solo rol. La excepción es la habilitación temporal de técnico para un
verificador (P-01, C12): mientras está vigente, al entrar la persona elige si trabaja como
verificadora o como técnica, y lo que eligió vale hasta que cierre la sesión. Nunca los dos en la
misma sesión: para cambiar, sale y vuelve a entrar. El rol activo es el que reciben la base
(app.rol) y el motor de decisión; C3 compara además el id de usuario, así que cambiar de rol no
evade la separación (K-2, T-26)."""

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone

from cuentas.models import EstadoPropuesta, PropuestaRol, Rol

ROL_ACTIVO = "va_rol"

# Lo que se puede hacer antes de elegir el rol.
PERMITIDAS_SIN_ROL = {
    "elegir_rol",
    "account_logout",
    "salud",
    "mfa_activate_totp",
    "mfa_view_recovery_codes",
    "mfa_download_recovery_codes",
    "account_reauthenticate",
}


def habilitacion_vigente(usuario):
    return PropuestaRol.objects.filter(
        usuario=usuario,
        es_habilitacion=True,
        rol=Rol.TEC,
        estado=EstadoPropuesta.APROBADA,
        fin_habilitacion__gte=timezone.localdate(),
    ).exists()


def roles_posibles(usuario):
    """Los roles con los que la persona puede trabajar hoy: el suyo y, si es verificadora con una
    habilitación vigente, también el de técnico."""
    if not usuario.rol:
        return []
    roles = [usuario.rol]
    if usuario.rol == Rol.VER and habilitacion_vigente(usuario):
        roles.append(Rol.TEC)
    return roles


class FijarRolActivo:
    """Pone en request.rol_activo el rol de la sesión. Con un solo rol posible lo fija solo; con
    dos, manda a elegir. Si el rol elegido dejó de ser posible (venció la habilitación), cierra la
    sesión."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.rol_activo = ""
        if request.user.is_authenticated:
            posibles = roles_posibles(request.user)
            elegido = request.session.get(ROL_ACTIVO, "")
            if elegido and elegido not in posibles:
                logout(request)
                messages.info(request, "Su habilitación o su rol cambió. Inicie sesión de nuevo.")
                return redirect("account_login")
            if not elegido and len(posibles) == 1:
                elegido = request.session[ROL_ACTIVO] = posibles[0]
            request.rol_activo = elegido
        return self.get_response(request)

    def process_view(self, request, vista, args, kwargs):
        if not request.user.is_authenticated or request.rol_activo:
            return None
        if request.resolver_match and request.resolver_match.url_name in PERMITIDAS_SIN_ROL:
            return None
        return redirect("elegir_rol")
