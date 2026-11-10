"""Historial de lecturas y alertas (tareas 4.8 y 4.9).

Cada consulta del detalle de algo que pertenece a una finca queda como evento de lectura: es la
materia prima de H1 (fincas distintas en 24 horas) y H3 (fincas nuevas en una hora). Las
denegadas por alcance (C1, C5) cuentan doble, y eso lo hace la cuenta en la base. Los umbrales
están en negocio.ParametroRol, que aprueba GER (P-02): no son constantes del código."""

from negocio.models import Alerta, EventoLectura

ALCANCE = {"C1", "C5"}
CONTROLES = {"H1", "H2", "H3"}


def anotar_lectura(request, objeto, decision):
    if objeto.get("coleccion") or not objeto.get("finca"):
        return
    EventoLectura.objects.create(
        usuario=request.user,
        finca_id=objeto["finca"],
        denegado=not decision.concedida and decision.regla in ALCANCE,
    )


def alertar(request, accion, objeto, decision, motivo):
    """Conceder y avisar, o restringir: queda una alerta sobre la persona para su supervisor o
    para GER (C15)."""
    if decision.resultado == "restringir":
        nivel = Alerta.Nivel.RESTRICCION
    elif motivo:
        nivel = Alerta.Nivel.VERIFICACION
    else:
        nivel = Alerta.Nivel.AVISO
    Alerta.objects.create(
        sujeto=request.user,
        control=decision.regla if decision.regla in CONTROLES else "H1",
        nivel=nivel,
        detalle={
            "accion": accion,
            "objeto": objeto.get("tipo", ""),
            "finca": objeto.get("finca", ""),
            "motivo": motivo,
        },
    )
