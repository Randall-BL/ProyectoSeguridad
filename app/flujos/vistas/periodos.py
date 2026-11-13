"""Períodos (5.4): ADM crea el período y registra la apertura o el cierre con las fechas de la
coordinación; GER los aprueba (C14). No existe reabrir. Al cerrar, los borradores que nunca se
enviaron pasan a «excluida» (T-22)."""

from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from autorizacion.proteccion import protegida
from flujos import hechos as h
from flujos.comun import accion, anotar, celda, escribir, nombre, tabla, verbos, volver
from negocio.models import EstadoCatalogo, EstadoMedicion, EstadoPeriodo, Medicion, Periodo, PropuestaPeriodo

TRANSICION = {EstadoPeriodo.PLANIFICADO: PropuestaPeriodo.Accion.ABRIR, EstadoPeriodo.ABIERTO: PropuestaPeriodo.Accion.CERRAR}


class FormularioPeriodo(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=50, help_text="Por ejemplo 2027-I.")
    inicio = forms.DateField(label="Inicio", widget=forms.DateInput(attrs={"type": "date"}))
    fin_medicion = forms.DateField(label="Fin de medición", widget=forms.DateInput(attrs={"type": "date"}))
    cierre_registro = forms.DateField(label="Cierre de registro", widget=forms.DateInput(attrs={"type": "date"}))

    def clean_nombre(self):
        nombre_ = self.cleaned_data["nombre"].strip()
        if Periodo.objects.filter(nombre=nombre_).exists():
            raise forms.ValidationError("Ya hay un período con ese nombre.")
        return nombre_

    def clean(self):
        datos = super().clean()
        inicio, fin, cierre = datos.get("inicio"), datos.get("fin_medicion"), datos.get("cierre_registro")
        if inicio and fin and cierre and not (inicio <= fin <= cierre):
            raise forms.ValidationError("Las fechas van en orden: inicio, fin de medición y cierre de registro.")
        return datos


@require_http_methods(["GET"])
@protegida("leer", "periodos")
def lista(request):
    periodos = Periodo.objects.order_by("-inicio")
    filas = [[celda(p.nombre, reverse("periodo", args=[p.pk])), celda(p.inicio.strftime("%d/%m/%Y")),
              celda(p.fin_medicion.strftime("%d/%m/%Y")), celda(p.cierre_registro.strftime("%d/%m/%Y")),
              celda(estado=p.estado, estado_texto=p.get_estado_display())] for p in periodos]
    permitidos = verbos(request, "periodos")
    acciones = []
    if "crear" in permitidos:
        acciones.append(accion("Crear período", reverse("crear_periodo"), primaria=True))
    if "exportar" in permitidos:
        acciones.append(accion("Exportar", reverse("exportar_periodos")))
    return render(request, "flujos/lista.html", {
        "titulo": "Períodos de medición",
        "descripcion": "Abrir y cerrar un período lo registra Administración y lo aprueba Gerencia. No existe reabrir.",
        "migas": [("Períodos", None)],
        "tabla": tabla(["Período", "Inicio", "Fin de medición", "Cierre de registro", "Estado"], filas,
                       vacio_titulo="No hay períodos"),
        "acciones": acciones,
    })


@require_http_methods(["GET"])
@protegida("leer", "periodos", objeto=h.periodo)
def ficha(request, periodo):
    p = get_object_or_404(Periodo, pk=periodo)
    permitidos = verbos(request, "periodos")
    propuestas = p.propuestas.select_related("registrada_por", "aprobada_por").order_by("-registrada_en")
    filas = [[celda(x.get_accion_display()), celda(nombre(x.registrada_por)), celda(nombre(x.aprobada_por)),
              celda(estado=x.estado, estado_texto=x.get_estado_display())] for x in propuestas]
    acciones = []
    if "proponer" in permitidos and p.estado in TRANSICION:
        acciones.append(accion(f"Registrar {TRANSICION[p.estado].label.lower()}", reverse("proponer_periodo", args=[p.pk]), primaria=True))
    for x in propuestas:
        if x.estado == EstadoCatalogo.PROPUESTO and x.accion in permitidos:
            acciones.append(accion(f"Aprobar: {x.get_accion_display().lower()}", reverse(f"{x.accion}_periodo", args=[x.pk]),
                                   metodo="post", primaria=True))
    conteo = Medicion.objects.filter(periodo=p).values_list("estado", flat=True)
    return render(request, "flujos/ficha.html", {
        "titulo": f"Período {p.nombre}",
        "migas": [("Períodos", reverse("periodos")), (p.nombre, None)],
        "estado": p.estado, "estado_texto": p.get_estado_display(),
        "datos": [("Inicio", p.inicio.strftime("%d/%m/%Y")), ("Fin de medición", p.fin_medicion.strftime("%d/%m/%Y")),
                  ("Cierre de registro", p.cierre_registro.strftime("%d/%m/%Y")),
                  ("Mediciones", f"{len(conteo)} ({sum(1 for e in conteo if e == EstadoMedicion.BORRADOR)} en borrador)")],
        "acciones": acciones,
        "secciones": [tabla(["Acción", "Registrada por", "Aprobada por", "Estado"], filas, titulo="Apertura y cierre",
                            nota="Quien registra no aprueba (C14).", vacio_titulo="Sin registros de apertura o cierre")],
    })


@require_http_methods(["GET", "POST"])
@protegida("crear", "periodos", formulario=True)
def crear(request):
    form = FormularioPeriodo(request.POST or None)
    if request.method == "POST" and form.is_valid():
        def crear_():
            p = Periodo.objects.create(**form.cleaned_data)
            anotar(request, "crear", "periodos", p.pk, despues={"nombre": p.nombre})
            return p

        p, hecho = escribir(request, "crear", "periodos", "", crear_)
        if hecho:
            return volver(request, reverse("periodo", args=[p.pk]), "Período creado como planificado.")
    return render(request, "flujos/formulario.html", {
        "titulo": "Crear período", "descripcion": "Queda planificado; la apertura se registra aparte y la aprueba Gerencia.",
        "migas": [("Períodos", reverse("periodos")), ("Crear", None)],
        "form": form, "boton": "Crear", "cancelar": reverse("periodos"),
    })


class FormularioPropuesta(forms.Form):
    accion = forms.ChoiceField(label="Acción", choices=PropuestaPeriodo.Accion.choices)


@require_http_methods(["GET", "POST"])
@protegida("proponer", "periodos", objeto=h.periodo, cambio=h.cambio_periodo, formulario=True)
def proponer(request, periodo):
    p = get_object_or_404(Periodo, pk=periodo)
    form = FormularioPropuesta(request.POST or None, initial={"accion": TRANSICION.get(p.estado)})
    if request.method == "POST" and form.is_valid():
        def proponer_():
            x = PropuestaPeriodo.objects.create(periodo=p, accion=form.cleaned_data["accion"], registrada_por=request.user)
            anotar(request, "proponer", "periodos", p.pk, despues={"accion": x.accion})

        if escribir(request, "proponer", "periodos", p.pk, proponer_)[1]:
            return volver(request, reverse("periodo", args=[p.pk]), "Registrado: espera la aprobación de Gerencia.")
    return render(request, "flujos/formulario.html", {
        "titulo": f"Apertura o cierre de {p.nombre}",
        "descripcion": "Con las fechas que acordó la coordinación. Lo aprueba otra persona, de Gerencia.",
        "migas": [("Períodos", reverse("periodos")), (p.nombre, reverse("periodo", args=[p.pk])), ("Registrar", None)],
        "datos": [("Estado actual", p.get_estado_display())],
        "form": form, "boton": "Registrar", "cancelar": reverse("periodo", args=[p.pk]),
    })


def _aplicar(request, propuesta, verbo):
    x = get_object_or_404(PropuestaPeriodo.objects.select_related("periodo"), pk=propuesta)

    def aplicar():
        antes = x.periodo.estado
        excluidas = 0
        if verbo == "abrir":
            Periodo.objects.filter(pk=x.periodo_id).update(estado=EstadoPeriodo.ABIERTO)
        else:
            Periodo.objects.filter(pk=x.periodo_id).update(estado=EstadoPeriodo.CERRADO)
            # Los borradores nunca enviados no pasan al período siguiente (T-22).
            excluidas = Medicion.objects.filter(periodo_id=x.periodo_id, estado=EstadoMedicion.BORRADOR).update(
                estado=EstadoMedicion.EXCLUIDA
            )
        PropuestaPeriodo.objects.filter(pk=x.pk).update(estado=EstadoCatalogo.APROBADO, aprobada_por=request.user,
                                                        aprobada_en=timezone.now())
        anotar(request, verbo, "periodos", x.periodo_id, antes={"estado": antes},
               despues={"estado": "abierto" if verbo == "abrir" else "cerrado", "excluidas": excluidas})

    if escribir(request, verbo, "periodos", x.periodo_id, aplicar)[1]:
        return volver(request, reverse("periodo", args=[x.periodo_id]),
                      "Período abierto." if verbo == "abrir" else "Período cerrado; los borradores pasaron a excluida.")
    return redirect("periodo", x.periodo_id)


@require_POST
@protegida("abrir", "periodos", objeto=h.propuesta_periodo)
def abrir(request, propuesta):
    return _aplicar(request, propuesta, "abrir")


@require_POST
@protegida("cerrar", "periodos", objeto=h.propuesta_periodo)
def cerrar(request, propuesta):
    return _aplicar(request, propuesta, "cerrar")
