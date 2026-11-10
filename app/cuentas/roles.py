"""Rol activo de la sesión (tarea 3.8): la exclusión dinámica entre técnico y verificador.

Cada cuenta tiene un solo rol. La excepción es la habilitación temporal de técnico para un
verificador (P-01, C12): mientras está vigente, al entrar la persona elige si trabaja como
verificadora o como técnica, y lo que eligió vale hasta que cierre la sesión. Nunca los dos en la
misma sesión: para cambiar, sale y vuelve a entrar. El rol activo es el que reciben la base
(app.rol) y el motor de decisión; C3 compara además el id de usuario, así que cambiar de rol no
evade la separación (K-2, T-26)."""

from django.contrib import messages
from django.contrib.auth import logout
from django.db import connection
from django.shortcuts import redirect

from cuentas.models import Rol

ROL_ACTIVO = "va_rol"

# Qué hace cada rol, en una línea (Parte 1, Entregable 2).
QUE_HACE = {
    Rol.TEC: "Mide las parcelas de las fincas que tiene asignadas y envía las mediciones a revisión.",
    Rol.VER: "Revisa las mediciones de otros y las aprueba o las devuelve con observaciones.",
    Rol.SUP: "Asigna fincas a los técnicos y atiende las alertas de su equipo.",
    Rol.GER: "Aprueba el catálogo, las cuentas y los períodos, y autoriza las enmiendas.",
    Rol.ADM: "Propone fincas, cuentas y períodos, y mantiene los datos personales de los dueños.",
    Rol.AUD: "Consulta todo durante su ventana y exporta evidencia sellada, sin modificar nada.",
    Rol.DUE: "Consulta sus fincas, sus mediciones aprobadas y sus certificados.",
}

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
    """Si tiene una habilitación de técnico aprobada y vigente. Se pregunta a la base con una
    función propia porque, antes de elegir el rol, la seguridad por fila no deja leer las
    propuestas de rol (cuentas/sql/0005)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT va_habilitacion_vigente(%s)", [usuario.pk])
        return cursor.fetchone()[0]


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
