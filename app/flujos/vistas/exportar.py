"""Exportar evidencia (5.11, C18): AUD, dentro de su ventana, descarga un paquete por objeto. Lo
genera el sistema, lleva la identidad de quien lo pidió, no incluye datos personales de los
dueños, y su huella SHA-256 queda en la bitácora y en ExportacionAuditoria. El sello con la clave
de Verdeazul lo agrega el servicio de emisión en la fase 6 (tarea 6.10)."""

import hashlib
import json

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from autorizacion.proteccion import protegida
from bitacora.models import Registro
from flujos.comun import anotar
from negocio.models import (
    Alerta,
    Asignacion,
    Certificado,
    Enmienda,
    ExportacionAuditoria,
    Finca,
    Medicion,
    Periodo,
)


def _fecha(valor):
    return valor.isoformat() if valor else None


def _fincas():
    return [
        {
            "codigo": f.codigo, "nombre": f.nombre, "titular": f.titular.codigo, "estado": f.estado,
            "parcelas": [
                {"codigo": p.codigo, "version": p.version, "area_ha": str(p.area_ha or ""), "estado": p.estado,
                 "activa": p.activa}
                for p in f.parcelas.order_by("codigo", "version")
            ],
        }
        for f in Finca.objects.select_related("titular").order_by("codigo")
    ]


def _periodos():
    return [
        {
            "nombre": p.nombre, "inicio": _fecha(p.inicio), "fin_medicion": _fecha(p.fin_medicion),
            "cierre_registro": _fecha(p.cierre_registro), "estado": p.estado,
            "propuestas": [
                {"accion": x.accion, "estado": x.estado, "registrada_por": x.registrada_por.username,
                 "aprobada_por": x.aprobada_por.username if x.aprobada_por else None}
                for x in p.propuestas.select_related("registrada_por", "aprobada_por")
            ],
        }
        for p in Periodo.objects.order_by("inicio")
    ]


def _asignaciones():
    return [
        {"tecnico": a.tecnico.username, "finca": a.finca.codigo, "periodo": a.periodo.nombre, "tipo": a.tipo,
         "motivo": a.motivo, "desde": _fecha(a.desde), "hasta": _fecha(a.hasta), "creada_por": a.creada_por.username,
         "terminada_en": _fecha(a.terminada_en)}
        for a in Asignacion.objects.select_related("tecnico", "finca", "periodo", "creada_por").order_by("creada_en")
    ]


def _mediciones():
    return [
        {
            "id": str(m.pk), "finca": m.parcela.finca.codigo, "parcela": m.parcela.codigo, "periodo": m.periodo.nombre,
            "estado": m.estado, "aprobada_por": m.aprobada_por.username if m.aprobada_por else None,
            "versiones": [
                {"numero": v.numero, "autor": v.autor.username, "fecha_medicion": _fecha(v.fecha_medicion),
                 "fecha_registro": _fecha(v.fecha_registro), "toneladas_co2": str(v.toneladas_co2),
                 "es_propuesta": v.es_propuesta}
                for v in m.versiones.select_related("autor").order_by("numero")
            ],
        }
        for m in Medicion.objects.select_related("parcela__finca", "periodo", "aprobada_por").order_by("creada_en")
    ]


def _enmiendas():
    def u(x):
        return x.username if x else None

    return [
        {"id": str(e.pk), "medicion": str(e.medicion_id), "estado": e.estado, "solicitada_por": u(e.solicitada_por),
         "responsable": u(e.responsable), "corregida_por": u(e.corregida_por), "revisada_por": u(e.revisada_por),
         "material": e.material, "dictamen_favorable": e.dictamen_favorable, "autorizada_por": u(e.autorizada_por),
         "comercializado": e.comercializado}
        for e in Enmienda.objects.select_related(
            "solicitada_por", "responsable", "corregida_por", "revisada_por", "autorizada_por"
        ).order_by("solicitada_en")
    ]


def _certificados():
    return [
        {"codigo": c.codigo, "parcela": c.parcela.codigo, "finca": c.parcela.finca.codigo, "periodo": c.periodo.nombre,
         "toneladas_co2": str(c.toneladas_co2), "estado": c.estado, "emitido_en": _fecha(c.emitido_en),
         "revocado_en": _fecha(c.revocado_en), "reemplaza": c.reemplaza.codigo if c.reemplaza else None}
        for c in Certificado.objects.select_related("parcela__finca", "periodo", "reemplaza").order_by("emitido_en")
    ]


def _bitacora():
    return [
        {"numero": r.id, "instante": _fecha(r.instante), "usuario": str(r.usuario_id) if r.usuario_id else None,
         "rol": r.rol, "accion": r.accion, "objeto_tipo": r.objeto_tipo, "objeto_id": r.objeto_id,
         "resultado": r.resultado, "regla": r.regla, "huella_previa": r.huella_previa, "huella": r.huella}
        for r in Registro.objects.order_by("id")
    ]


def _alertas():
    return [
        {"sujeto": a.sujeto.username, "control": a.control, "nivel": a.nivel, "creada_en": _fecha(a.creada_en),
         "resuelta_por": a.resuelta_por.username if a.resuelta_por else None, "resuelta_en": _fecha(a.resuelta_en)}
        for a in Alerta.objects.select_related("sujeto", "resuelta_por").order_by("creada_en")
    ]


CONTENIDO = {
    "fincas": _fincas,
    "periodos": _periodos,
    "asignaciones": _asignaciones,
    "mediciones": _mediciones,
    "enmiendas": _enmiendas,
    "certificados": _certificados,
    "bitacora": _bitacora,
    "alertas": _alertas,
}


def _vista(tipo):
    @require_http_methods(["GET"])
    @protegida("exportar", tipo)
    def exportar(request):
        ahora = timezone.now()
        paquete = {
            "sistema": "Verdeazul Carbono",
            "objeto": tipo,
            "generado_en": ahora.isoformat(),
            "auditor": request.user.username,
            "sello": None,
            "filas": CONTENIDO[tipo](),
        }
        cuerpo = json.dumps(paquete, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        huella = hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()
        registro = ExportacionAuditoria.objects.create(auditor=request.user, objeto=tipo, huella=huella)
        anotar(request, "exportar", tipo, registro.pk, despues={"huella": huella, "filas": len(paquete["filas"])})
        respuesta = HttpResponse(cuerpo, content_type="application/json; charset=utf-8")
        respuesta["Content-Disposition"] = f'attachment; filename="verdeazul-{tipo}-{ahora:%Y%m%d-%H%M%S}.json"'
        respuesta["X-Verdeazul-Huella"] = huella
        return respuesta

    exportar.__name__ = f"exportar_{tipo}"
    return exportar


VISTAS = {tipo: _vista(tipo) for tipo in CONTENIDO}
