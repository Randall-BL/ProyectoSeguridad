"""Lo que recibe la persona cuando el motor no deja seguir."""

from django.shortcuts import render

from bitacora.registro import anexar, origen_de


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


def sin_motor(request, accion="", objeto=None, causa=""):
    """K-3: el motor no respondió. La petición se frena con 503 y la denegación queda en la
    bitácora con la causa «motor sin respuesta»; no se ejecuta nada más."""
    _anotar(request, accion, objeto or {}, "denegado", f"K-3 motor sin respuesta: {causa}"[:200])
    return render(request, "autorizacion/sin_motor.html", status=503)


def denegada(request, accion, objeto, decision):
    _anotar(request, accion, objeto, "restringido" if decision.resultado == "restringir" else "denegado", decision.regla)
    return render(
        request,
        "autorizacion/denegado.html",
        {"regla": decision.regla, "restringida": decision.resultado == "restringir"},
        status=403,
    )
