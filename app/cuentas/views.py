from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from bitacora.registro import anexar, origen_de
from cuentas.models import Rol
from cuentas.roles import ROL_ACTIVO, roles_posibles


@login_required
@require_http_methods(["GET", "POST"])
def elegir_rol(request):
    """Una sola vez por sesión: lo elegido no se cambia sin salir y volver a entrar (3.8)."""
    if request.session.get(ROL_ACTIVO):
        return redirect("hola")
    posibles = roles_posibles(request.user)
    if request.method == "POST" and request.POST.get("rol") in posibles:
        rol = request.POST["rol"]
        request.session[ROL_ACTIVO] = rol
        anexar(
            accion="elegir_rol",
            resultado="concedido",
            usuario=request.user,
            rol=rol,
            objeto_tipo="cuenta",
            objeto_id=request.user.pk,
            regla="C12",
            origen=origen_de(request),
            sesion=request.session.session_key or "",
        )
        return redirect("hola")
    return render(
        request,
        "cuentas/elegir_rol.html",
        {"posibles": [(rol, Rol(rol).label) for rol in posibles]},
    )
