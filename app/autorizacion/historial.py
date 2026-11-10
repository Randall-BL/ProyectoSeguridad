"""Historial de lecturas y alertas (tareas 4.8 y 4.9).

Cada consulta del detalle de algo que pertenece a una finca queda como evento de lectura: es la
materia prima de H1 (fincas distintas en 24 horas) y H3 (fincas nuevas en una hora). Las
denegadas por alcance (C1, C5) cuentan doble, y eso lo hace la cuenta en la base. Los umbrales
están en negocio.ParametroRol, que aprueba GER (P-02): no son constantes del código."""

from negocio.models import EventoLectura

ALCANCE = {"C1", "C5"}


def anotar_lectura(request, objeto, decision):
    if objeto.get("coleccion") or not objeto.get("finca"):
        return
    EventoLectura.objects.create(
        usuario=request.user,
        finca_id=objeto["finca"],
        denegado=not decision.concedida and decision.regla in ALCANCE,
    )

