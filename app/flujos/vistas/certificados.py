"""Certificados: los leen VER y GER (con H1 a H3), AUD dentro de su ventana y DUE los suyos (C5).
Emitirlos y revocarlos es solo del sistema (fila SIS, C4): lo hace el servicio de emisión. Quien
puede leer un certificado puede descargar su archivo firmado y comprobarlo en el servicio público."""

import json
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from autorizacion.proteccion import protegida
from flujos import hechos as h
from flujos.comun import accion, celda, tabla, verbos
from negocio.models import Certificado


@require_http_methods(["GET"])
@protegida("leer", "certificados")
def lista(request):
    certificados = Certificado.objects.select_related("parcela__finca", "periodo").order_by("-emitido_en")
    filas = [[celda(c.codigo, reverse("certificado", args=[c.pk])), celda(f"{c.parcela.finca.codigo} · {c.parcela.codigo}"),
              celda(c.periodo.nombre), celda(str(c.toneladas_co2), numero=True),
              celda(estado=c.estado, estado_texto=c.get_estado_display())] for c in certificados]
    acciones = [accion("Exportar", reverse("exportar_certificados"))] if "exportar" in verbos(request, "certificados") else []
    return render(request, "flujos/lista.html", {
        "titulo": "Certificados",
        "descripcion": "Los emite y los revoca solo el sistema, a partir de una medición aprobada (C4).",
        "migas": [("Certificados", None)],
        "tabla": tabla(["Código", "Finca y parcela", "Período", "Toneladas de CO₂", "Estado"], filas,
                       numericas=("Toneladas de CO₂",), vacio_titulo="Todavía no hay certificados",
                       vacio_texto="El servicio de emisión los firma con Ed25519 a partir de las mediciones aprobadas."),
        "acciones": acciones,
    })


@require_http_methods(["GET"])
@protegida("leer", "certificados", objeto=h.certificado)
def ficha(request, certificado):
    c = get_object_or_404(Certificado.objects.select_related("parcela__finca", "periodo", "reemplaza"), pk=certificado)
    return render(request, "flujos/ficha.html", {
        "titulo": f"Certificado {c.codigo}",
        "migas": [("Certificados", reverse("certificados")), (c.codigo, None)],
        "estado": c.estado, "estado_texto": c.get_estado_display(),
        "datos": [("Finca", c.parcela.finca.codigo), ("Parcela", c.parcela.codigo), ("Período", c.periodo.nombre),
                  ("Toneladas de CO₂", c.toneladas_co2), ("Emitido", c.emitido_en.strftime("%d/%m/%Y %H:%M")),
                  ("Revocado", c.revocado_en.strftime("%d/%m/%Y %H:%M") if c.revocado_en else None),
                  ("Reemplaza a", c.reemplaza.codigo if c.reemplaza else None),
                  ("Lo reemplaza", getattr(getattr(c, "reemplazado_por", None), "codigo", None)),
                  ("Clave", c.clave_id)],
        "acciones": _acciones(c),
    })


def _acciones(c):
    acciones = [accion("Descargar el certificado", reverse("descargar_certificado", args=[c.pk]), primaria=True)]
    if settings.PUBLICO_URL:
        enlace = f"{settings.PUBLICO_URL.rstrip('/')}/comprobar?{urlencode({'codigo': c.codigo})}"
        acciones.append(accion("Comprobar en el servicio público", enlace))
    return acciones


@require_http_methods(["GET"])
@protegida("leer", "certificados", objeto=h.certificado)
def descargar(request, certificado):
    """El archivo firmado tal cual: contenido y firma. Es lo que se entrega al comprador."""
    c = get_object_or_404(Certificado, pk=certificado)
    cuerpo = json.dumps({"contenido": c.contenido, "firma": c.firma}, ensure_ascii=False, indent=2, sort_keys=True)
    respuesta = HttpResponse(cuerpo, content_type="application/json; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="{c.codigo}.json"'
    return respuesta
