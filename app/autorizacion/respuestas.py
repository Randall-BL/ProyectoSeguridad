"""Lo que recibe la persona cuando el motor no deja seguir, y lo que queda en la bitácora."""

from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode

from bitacora.registro import anexar, origen_de
from cuentas.decisiones import segundo_factor_reciente


def _anotar(request, accion, objeto, resultado, regla):
    anexar(
        accion=accion,
        resultado=resultado,
        usuario=request.user if request.user.is_authenticated else None,
        rol=getattr(request, "rol_activo", ""),
        objeto_tipo=objeto.get("tipo", ""),
        objeto_id=objeto.get("id", ""),
        regla=regla,
        origen=origen_de(request),
        sesion=request.session.session_key or "",
    )


def anotar_denegacion(request, accion, objeto, decision):
    resultado = "restringido" if decision.resultado == "restringir" else "denegado"
    _anotar(request, accion, objeto, resultado, decision.regla)


def sin_motor(request, accion="", objeto=None, causa=""):
    """K-3: el motor no respondió. La petición se frena con 503 y la denegación queda en la
    bitácora con la causa «motor sin respuesta»; no se ejecuta nada más."""
    _anotar(request, accion, objeto or {}, "denegado", f"K-3 motor sin respuesta: {causa}"[:200])
    return render(request, "autorizacion/sin_motor.html", status=503)


def denegada(request, accion, objeto, decision):
    anotar_denegacion(request, accion, objeto, decision)
    return render(
        request,
        "autorizacion/denegado.html",
        {"regla": decision.regla, "restringida": decision.resultado == "restringir"},
        status=403,
    )


def pedir_motivo(request, accion, objeto, decision):
    """H1 en su segundo nivel, H2 y H3: segundo factor reciente y un motivo escrito. Primero el
    código; después, el motivo, que viaja con la misma petición."""
    if not segundo_factor_reciente(request):
        destino = request.get_full_path() if request.method == "GET" else request.path
        return redirect(f"{reverse('mfa_reauthenticate')}?{urlencode({'next': destino})}")
    _anotar(request, accion, objeto, "restringido", f"{decision.regla}: falta el motivo")
    campos = [(k, v) for k, v in request.POST.items() if k not in {"csrfmiddlewaretoken", "motivo"}]
    return render(
        request,
        "autorizacion/motivo.html",
        {"regla": decision.regla, "metodo": request.method, "campos": campos},
    )
