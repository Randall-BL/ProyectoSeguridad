"""Los hechos del objeto para cada ruta de los flujos (tarea 4.6). Los identificadores de lo que
se quiere tocar vienen de la ruta o del formulario; todo lo que el motor revisa de ese objeto
(estado, autores, titular, quién propuso) sale de la base. Lo que la seguridad por fila esconde
a TEC y DUE lo calculan funciones SECURITY DEFINER, para que el motor pueda decir «C1» o «C5»."""

import uuid

from django.db.models import Q

from autorizacion.hechos import _json, de_finca, de_medicion, de_nueva_medicion
from cuentas.models import EstadoPropuesta, PropuestaRol, Usuario
from negocio.models import (
    Alerta,
    EstadoPeriodo,
    Periodo,
    PropuestaCatalogo,
    PropuestaPeriodo,
    Vinculo,
)
from nucleo.dias import dias_habiles


def _uuid(valor):
    try:
        return uuid.UUID(str(valor))
    except (TypeError, ValueError):
        return None


# --- Fincas y catálogo (C1, C5, C11) --------------------------------------------------------


def finca(request, finca):
    return de_finca(finca)


def propuesta_finca(request):
    """Proponer: la finca y el titular salen de la base cuando ya existen (C17)."""
    hechos = {}
    finca_id = _uuid(request.POST.get("finca"))
    if finca_id:
        datos = de_finca(finca_id) or {}
        hechos.update({k: datos.get(k) for k in ("finca", "titular") if datos.get(k)})
    titular = _uuid(request.POST.get("titular"))
    if titular and "titular" not in hechos:
        hechos["titular"] = str(titular)
    return hechos


def aprobacion_catalogo(request, propuesta):
    p = PropuestaCatalogo.objects.filter(pk=propuesta).values(
        "finca_id", "finca__titular_id", "estado", "propuesta_por_id"
    ).first()
    if p is None:
        return None
    return {
        "id": str(propuesta),
        "finca": str(p["finca_id"]),
        "titular": str(p["finca__titular_id"]),
        "propuesta": {"estado": p["estado"], "propuesta_por": str(p["propuesta_por_id"])},
    }


# --- Datos personales (C1, C5, C16) ---------------------------------------------------------


def titular(request, titular):
    return _json("SELECT va_hechos_titular(%s, %s)", [titular, request.user.pk])


# --- Períodos (C14) --------------------------------------------------------------------------


def periodo(request, periodo):
    p = Periodo.objects.filter(pk=periodo).values("estado").first()
    return {"id": str(periodo), "estado": p["estado"]} if p else None


def propuesta_periodo(request, propuesta):
    p = PropuestaPeriodo.objects.filter(pk=propuesta).values(
        "periodo_id", "periodo__estado", "accion", "estado", "registrada_por_id"
    ).first()
    if p is None:
        return None
    return {
        "id": str(p["periodo_id"]),
        "estado": p["periodo__estado"],
        "propuesta": {"accion": p["accion"], "estado": p["estado"], "registrada_por": str(p["registrada_por_id"])},
    }


def cambio_periodo(request, hechos):
    return {"accion": request.POST.get("accion", "")}


# --- Asignaciones (C1, C5, C19, K-1) ---------------------------------------------------------


def nueva_asignacion(request):
    tecnico, finca_id = _uuid(request.POST.get("tecnico")), _uuid(request.POST.get("finca"))
    if not tecnico or not finca_id:
        return {}
    return _json("SELECT va_hechos_asignacion(%s, %s)", [tecnico, finca_id]) or {}


def asignacion(request, asignacion):
    from negocio.models import Asignacion

    a = Asignacion.objects.filter(pk=asignacion).values("tecnico_id", "finca_id", "tipo").first()
    if a is None:
        return None
    hechos = _json("SELECT va_hechos_asignacion(%s, %s)", [a["tecnico_id"], a["finca_id"]]) or {}
    return {**hechos, "id": str(asignacion)}


def cambio_asignacion(request, hechos):
    tipo = request.POST.get("tipo", "ordinaria")
    dias = request.POST.get("dias") or "0"
    return {
        "tipo": tipo,
        "motivo": request.POST.get("motivo", ""),
        "dias": int(dias) if dias.lstrip("-").isdigit() else -1,
    }


# --- Mediciones (C1, C2, C3, C5) -------------------------------------------------------------


def medicion(request, medicion):
    return de_medicion(medicion, request.user.pk)


def periodo_abierto():
    return Periodo.objects.filter(estado=EstadoPeriodo.ABIERTO).order_by("-inicio").first()


def nueva_medicion(request, parcela):
    periodo_ = periodo_abierto() or Periodo.objects.order_by("-inicio").first()
    if periodo_ is None:
        return None
    return de_nueva_medicion(parcela, periodo_.pk, request.user.pk)


def cambio_medicion(request, hechos):
    fecha = request.POST.get("fecha_medicion")
    return {"fecha_medicion": fecha} if fecha else {}


# --- Enmiendas (C1, C5, C7 a C10) ------------------------------------------------------------


def enmienda(request, enmienda):
    return _json("SELECT va_hechos_enmienda(%s)", [enmienda])


def solicitud_enmienda(request, medicion):
    m = de_medicion(medicion, request.user.pk)
    if m is None:
        return None
    return {
        "finca": m["finca"],
        "titular": m["titular"],
        "medicion": {"estado": m["estado"], "periodo_estado": m["periodo_estado"], "responsable": m["responsable"]},
    }


# --- Certificados (C5) ----------------------------------------------------------------------


def certificado(request, certificado):
    return _json("SELECT va_hechos_certificado(%s)", [certificado])


# --- Cuentas (C12, C13) ----------------------------------------------------------------------


def cuenta(request, cuenta):
    return {"id": str(cuenta), "cuenta": str(cuenta)} if Usuario.objects.filter(pk=cuenta).exists() else None


def cuenta_nueva(request):
    return {"cuenta": ""}


def cuenta_propia(request):
    return {"id": str(request.user.pk), "cuenta": str(request.user.pk)}


def propuesta_rol(request, propuesta):
    p = PropuestaRol.objects.filter(pk=propuesta).values("usuario_id", "estado", "propuesta_por_id").first()
    if p is None:
        return None
    return {
        "id": str(propuesta),
        "cuenta": str(p["usuario_id"]),
        "propuesta": {"estado": p["estado"], "propuesta_por": str(p["propuesta_por_id"])},
    }


def retiro_vinculo(request, vinculo):
    """Retirar un vínculo lo pide la persona y lo aprueba GER: es la segunda firma de C12."""
    v = Vinculo.objects.filter(pk=vinculo, retiro_solicitado_en__isnull=False, retirado_en__isnull=True).values(
        "usuario_id"
    ).first()
    if v is None:
        return None
    return {
        "id": str(vinculo),
        "cuenta": str(v["usuario_id"]),
        "propuesta": {"estado": EstadoPropuesta.PROPUESTA, "propuesta_por": str(v["usuario_id"])},
    }


# --- Alertas (C15) --------------------------------------------------------------------------


def alerta(request, alerta):
    a = Alerta.objects.filter(pk=alerta).select_related("sujeto").first()
    if a is None:
        return None
    escalada = a.resuelta_en is None and dias_habiles(a.creada_en, None) > 2
    return {
        "id": str(alerta),
        "sujeto_alerta": str(a.sujeto_id),
        "supervisor_del_sujeto": str(a.sujeto.supervisor_id) if a.sujeto.supervisor_id else None,
        "escalada": escalada,
    }


def alertas_visibles(request, consulta):
    """C15 sobre la lista: SUP ve las de sus técnicos; GER, las de quien no tiene supervisor y las
    escaladas; AUD, todas. Nadie ve en esta lista las suyas."""
    rol = request.rol_activo
    consulta = consulta.exclude(sujeto=request.user)
    if rol == "SUP":
        return consulta.filter(sujeto__supervisor=request.user)
    if rol == "GER":
        escaladas = [a.pk for a in consulta.filter(resuelta_en__isnull=True) if dias_habiles(a.creada_en, None) > 2]
        return consulta.filter(Q(sujeto__supervisor__isnull=True) | Q(pk__in=escaladas))
    return consulta
