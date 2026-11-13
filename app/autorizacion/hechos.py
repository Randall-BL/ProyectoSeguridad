"""Los hechos que recibe el motor, armados desde la base y nunca desde la petición (tarea 4.6).

El id del sujeto sale de la sesión del servidor (K-2) y su rol, del rol activo de la sesión (3.8).
Lo demás lo calcula la base con funciones propias (autorizacion/sql/0001_hechos.sql), que ven la
verdad de las filas aunque la seguridad por fila se las esconda a quien pregunta."""

import json

from django.db import connection

from cuentas.decisiones import segundo_factor_reciente


def _json(sql, parametros):
    """Ejecuta una función de hechos. Django deja el jsonb como texto: se decodifica aquí."""
    with connection.cursor() as cursor:
        cursor.execute(sql, parametros)
        fila = cursor.fetchone()
    if not fila or fila[0] is None:
        return None
    return json.loads(fila[0]) if isinstance(fila[0], str) else fila[0]


def del_sujeto(request, finca=None):
    """El sujeto, su historial y los parámetros de su rol."""
    usuario = request.user
    rol = request.rol_activo
    datos = _json("SELECT va_hechos_sujeto(%s, %s, %s)", [usuario.pk, rol, finca])
    sujeto = {
        "id": str(usuario.pk),
        "rol": rol,
        "segundo_factor_reciente": segundo_factor_reciente(request),
        "ventana_vigente": usuario.puede_entrar(),
        "fincas_asignadas": datos["fincas_asignadas"],
        "titulares_representados": datos["titulares_representados"],
        "titulares_con_vinculo": datos["titulares_con_vinculo"],
        "tecnicos_a_cargo": datos["tecnicos_a_cargo"],
    }
    return sujeto, datos["historial"], datos["parametros"], datos["hoy"]


def de_medicion(medicion_id, usuario_id):
    return _json("SELECT va_hechos_medicion(%s, %s)", [medicion_id, usuario_id])


def de_nueva_medicion(parcela_id, periodo_id, usuario_id):
    return _json("SELECT va_hechos_nueva_medicion(%s, %s, %s)", [parcela_id, periodo_id, usuario_id])


def de_finca(finca_id):
    return _json("SELECT va_hechos_finca(%s)", [finca_id])


def entrada(request, accion, objeto, cambio=None, motivo=""):
    """La entrada completa del motor para una petición."""
    sujeto, historial, parametros, hoy = del_sujeto(request, objeto.get("finca"))
    datos = {
        "sujeto": sujeto,
        "accion": accion,
        "objeto": objeto,
        "historial": historial,
        "parametros": parametros,
        "hoy": hoy,
        "motivo": motivo,
    }
    if cambio is not None:
        datos["cambio"] = cambio
    return datos
