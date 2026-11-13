"""Piezas que comparten las pantallas de los flujos: tablas, acciones según la celda del rol y la
escritura con su registro en la bitácora."""

import re

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.shortcuts import redirect

from autorizacion import motor
from bitacora.registro import anexar, origen_de

# Los disparadores de la base nombran la regla al negar («C3: …», «K-1: …»).
_REGLA = re.compile(r"\b([CHK]-?\d{1,2})\b")


def celda(texto="", url=None, *, estado=None, estado_texto=None, numero=False):
    return {"texto": texto, "url": url, "estado": estado, "estado_texto": estado_texto, "numero": numero}


def tabla(columnas, filas, *, titulo="", nota="", numericas=(), vacio_titulo="", vacio_texto="", pie=""):
    return {
        "titulo": titulo,
        "nota": nota,
        "columnas": columnas,
        "filas": filas,
        "numericas": numericas,
        "vacio_titulo": vacio_titulo,
        "vacio_texto": vacio_texto,
        "pie": pie,
    }


def verbos(request, tipo):
    """Los verbos que la celda del rol activo tiene sobre el objeto. Sirve para mostrar solo las
    acciones posibles; cada una se vuelve a decidir con los hechos al ejecutarla."""
    if not hasattr(request, "_celdas"):
        request._celdas = motor.permisos_del_rol(request.rol_activo)
    return {permiso["verbo"] for permiso in request._celdas.get(tipo, [])}


def accion(texto, url, *, metodo="get", primaria=False, peligro=False):
    return {"texto": texto, "url": url, "metodo": metodo, "primaria": primaria, "peligro": peligro}


def anotar(request, accion_, tipo, objeto_id, *, resultado="concedido", regla=None, antes=None, despues=None):
    """Un registro de bitácora por cada acción (POL-BT-01): sin registro no hay acción, porque va en
    la misma transacción que el cambio."""
    decision = getattr(request, "decision", None)
    anexar(
        accion=accion_,
        resultado=resultado,
        usuario=request.user,
        rol=getattr(request, "rol_activo", ""),
        objeto_tipo=tipo,
        objeto_id=objeto_id,
        regla=regla or (decision.regla if decision else ""),
        origen=origen_de(request),
        sesion=request.session.session_key or "",
        antes=antes,
        despues=despues,
    )


def escribir(request, accion_, tipo, objeto_id, cambio):
    """Ejecuta el cambio en un punto de guardado. Si un disparador de la base lo niega (el segundo
    candado), se deshace solo el cambio, la negación queda en la bitácora y se avisa con la regla."""
    try:
        with transaction.atomic():
            resultado = cambio()
    except DatabaseError as error:
        texto = str(error).splitlines()[0]
        encontrada = _REGLA.search(texto)
        anotar(request, accion_, tipo, objeto_id, resultado="denegado",
               regla=f"base: {encontrada.group(1) if encontrada else 'restricción'}")
        messages.error(request, f"La base de datos rechazó la operación: {texto}")
        return None, False
    return resultado, True


def volver(request, destino, mensaje):
    messages.success(request, mensaje)
    return redirect(destino)


def nombre(usuario):
    return usuario.get_full_name() or usuario.username if usuario else ""
