"""Asignaciones (5.5): SUP asigna fincas a técnicos, ordinarias por el período o temporales con
motivo y fin de 15 días como máximo (C19); nadie se asigna a sí mismo; un técnico tiene como
máximo 20 activas y la pantalla muestra cuántas lleva cada uno (K-1, T-38, T-39)."""

from datetime import timedelta

from django import forms
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from autorizacion.hechos import _json
from autorizacion.proteccion import protegida
from cuentas.models import EstadoPropuesta, Rol, Usuario
from flujos import hechos as h
from flujos.comun import accion, anotar, celda, escribir, nombre, tabla, verbos, volver
from negocio.models import Asignacion, EstadoPeriodo, Finca, ParametroRol, Periodo

MAXIMO_TEMPORAL = 15


def _tecnicos():
    hoy = timezone.localdate()
    return Usuario.objects.filter(is_active=True).filter(
        Q(rol=Rol.TEC) | Q(propuestas_rol__es_habilitacion=True, propuestas_rol__rol=Rol.TEC,
                           propuestas_rol__estado=EstadoPropuesta.APROBADA, propuestas_rol__fin_habilitacion__gte=hoy)
    ).distinct().order_by("username")


def _activas(tecnico_id):
    return _json("SELECT va_asignaciones_activas(%s)", [tecnico_id])


def _maximo():
    return ParametroRol.objects.filter(rol="TEC").values_list("max_asignaciones_activas", flat=True).first() or 20


def _vigente(a):
    if a.terminada_en:
        return "cerrado", "Terminada"
    if a.tipo == Asignacion.Tipo.TEMPORAL and a.hasta and a.hasta < timezone.localdate():
        return "cerrado", "Vencida"
    if a.tipo == Asignacion.Tipo.ORDINARIA and a.periodo.estado == EstadoPeriodo.CERRADO:
        return "cerrado", "Período cerrado"
    return "vigente", "Activa"


class FormularioAsignacion(forms.Form):
    tecnico = forms.ModelChoiceField(label="Técnico", queryset=Usuario.objects.none())
    finca = forms.ModelChoiceField(label="Finca", queryset=Finca.objects.none())
    periodo = forms.ModelChoiceField(label="Período", queryset=Periodo.objects.none())
    tipo = forms.ChoiceField(label="Tipo", choices=Asignacion.Tipo.choices)
    motivo = forms.CharField(label="Motivo (solo temporales)", max_length=300, required=False)
    dias = forms.IntegerField(label="Días de duración (solo temporales)", min_value=1, max_value=MAXIMO_TEMPORAL,
                              required=False, help_text=f"Desde hoy, {MAXIMO_TEMPORAL} como máximo; se puede renovar.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tecnico"].queryset = _tecnicos()
        self.fields["tecnico"].label_from_instance = lambda u: f"{nombre(u)} ({u.username})"
        self.fields["finca"].queryset = Finca.objects.order_by("codigo")
        self.fields["periodo"].queryset = Periodo.objects.exclude(estado=EstadoPeriodo.CERRADO).order_by("inicio")

    def clean(self):
        datos = super().clean()
        if datos.get("tipo") == Asignacion.Tipo.TEMPORAL and (not datos.get("motivo") or not datos.get("dias")):
            raise forms.ValidationError("Una asignación temporal lleva motivo y duración (C19).")
        return datos


@require_http_methods(["GET"])
@protegida("leer", "asignaciones")
def lista(request):
    asignaciones = Asignacion.objects.select_related("tecnico", "finca", "periodo").order_by("-creada_en")
    permitidos = verbos(request, "asignaciones")
    modificar = "modificar" in permitidos
    filas = []
    for a in asignaciones:
        estado, texto = _vigente(a)
        fila = [celda(a.finca.codigo), celda(nombre(a.tecnico)), celda(a.periodo.nombre), celda(a.get_tipo_display()),
                celda(a.hasta.strftime("%d/%m/%Y") if a.hasta else "Fin del período"), celda(estado=estado, estado_texto=texto)]
        if modificar:
            fila.append(celda("Gestionar", reverse("asignacion", args=[a.pk])) if estado == "vigente" else celda("—"))
        filas.append(fila)
    columnas = ["Finca", "Técnico", "Período", "Tipo", "Hasta", "Estado"] + (["Acción"] if modificar else [])
    acciones = []
    if "crear" in permitidos:
        acciones.append(accion("Nueva asignación", reverse("crear_asignacion"), primaria=True))
    if "exportar" in permitidos:
        acciones.append(accion("Exportar", reverse("exportar_asignaciones")))
    secciones = []
    if "crear" in permitidos:
        maximo = _maximo()
        secciones.append(tabla(["Técnico", "Activas", "Máximo"],
                               [[celda(nombre(t)), celda(str(_activas(t.pk)), numero=True), celda(str(maximo), numero=True)]
                                for t in _tecnicos()],
                               titulo="Asignaciones activas por técnico", numericas=("Activas", "Máximo"),
                               nota="K-1: las temporales vencidas y las de un período cerrado no cuentan."))
    return render(request, "flujos/lista.html", {
        "titulo": "Asignaciones",
        "descripcion": "Qué técnico mide qué finca. Las temporales vencen solas.",
        "migas": [("Asignaciones", None)],
        "tabla": tabla(columnas, filas, vacio_titulo="No hay asignaciones que pueda ver"),
        "acciones": acciones,
        "secciones": secciones,
    })


@require_http_methods(["GET", "POST"])
@protegida("crear", "asignaciones", objeto=h.nueva_asignacion, cambio=h.cambio_asignacion, formulario=True)
def crear(request):
    form = FormularioAsignacion(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        hoy = timezone.localdate()
        temporal = datos["tipo"] == Asignacion.Tipo.TEMPORAL

        def crear_():
            a = Asignacion.objects.create(
                tecnico=datos["tecnico"], finca=datos["finca"], periodo=datos["periodo"], tipo=datos["tipo"],
                motivo=datos["motivo"] if temporal else "", desde=hoy,
                hasta=hoy + timedelta(days=datos["dias"]) if temporal else None, creada_por=request.user,
            )
            anotar(request, "crear", "asignaciones", a.pk,
                   despues={"tecnico": a.tecnico.username, "finca": a.finca.codigo, "tipo": a.tipo})
            return a

        if escribir(request, "crear", "asignaciones", "", crear_)[1]:
            return volver(request, reverse("asignaciones"), "Asignación creada.")
    return render(request, "flujos/formulario.html", {
        "titulo": "Nueva asignación",
        "descripcion": f"Nadie se asigna a sí mismo, la temporal dura {MAXIMO_TEMPORAL} días como máximo y un técnico "
                       f"tiene como máximo {_maximo()} asignaciones activas (C19, K-1).",
        "migas": [("Asignaciones", reverse("asignaciones")), ("Nueva", None)],
        "form": form, "boton": "Asignar", "cancelar": reverse("asignaciones"),
    })


@require_http_methods(["GET"])
@protegida("modificar", "asignaciones", objeto=h.asignacion)
def ficha(request, asignacion):
    a = get_object_or_404(Asignacion.objects.select_related("tecnico", "finca", "periodo", "creada_por"), pk=asignacion)
    estado, texto = _vigente(a)
    acciones = []
    if estado == "vigente":
        acciones.append(accion("Terminar hoy", reverse("terminar_asignacion", args=[a.pk]), metodo="post", peligro=True))
        if a.tipo == Asignacion.Tipo.TEMPORAL:
            acciones.append(accion(f"Renovar {MAXIMO_TEMPORAL} días desde hoy", reverse("renovar_asignacion", args=[a.pk]),
                                   metodo="post"))
    return render(request, "flujos/ficha.html", {
        "titulo": f"Asignación de {a.finca.codigo}",
        "migas": [("Asignaciones", reverse("asignaciones")), (a.finca.codigo, None)],
        "estado": estado, "estado_texto": texto,
        "datos": [("Técnico", nombre(a.tecnico)), ("Finca", a.finca.codigo), ("Período", a.periodo.nombre),
                  ("Tipo", a.get_tipo_display()), ("Motivo", a.motivo), ("Desde", a.desde.strftime("%d/%m/%Y")),
                  ("Hasta", a.hasta.strftime("%d/%m/%Y") if a.hasta else "Fin del período"),
                  ("Creada por", nombre(a.creada_por))],
        "acciones": acciones,
    })


def _cambio_existente(request, hechos):
    from negocio.models import Asignacion as A

    a = A.objects.filter(pk=hechos.get("id")).values("tipo", "motivo").first() or {}
    dias = MAXIMO_TEMPORAL if request.path.endswith("/renovar/") else 0
    return {"tipo": a.get("tipo", "ordinaria"), "motivo": a.get("motivo", ""), "dias": dias}


@require_POST
@protegida("modificar", "asignaciones", objeto=h.asignacion, cambio=_cambio_existente)
def terminar(request, asignacion):
    a = get_object_or_404(Asignacion, pk=asignacion)

    def terminar_():
        a.terminada_en = timezone.now()
        a.save(update_fields=["terminada_en"])
        anotar(request, "modificar", "asignaciones", a.pk, despues={"terminada": True})

    if escribir(request, "modificar", "asignaciones", a.pk, terminar_)[1]:
        return volver(request, reverse("asignaciones"), "Asignación terminada; el técnico perdió el acceso a la finca.")
    return redirect("asignacion", a.pk)


@require_POST
@protegida("modificar", "asignaciones", objeto=h.asignacion, cambio=_cambio_existente)
def renovar(request, asignacion):
    a = get_object_or_404(Asignacion, pk=asignacion, tipo=Asignacion.Tipo.TEMPORAL)
    hoy = timezone.localdate()

    def renovar_():
        antes = a.hasta
        a.desde, a.hasta = hoy, hoy + timedelta(days=MAXIMO_TEMPORAL)
        a.save(update_fields=["desde", "hasta"])
        anotar(request, "modificar", "asignaciones", a.pk, antes={"hasta": str(antes)}, despues={"hasta": str(a.hasta)})

    if escribir(request, "modificar", "asignaciones", a.pk, renovar_)[1]:
        return volver(request, reverse("asignacion", args=[a.pk]), "Asignación renovada.")
    return redirect("asignacion", a.pk)
