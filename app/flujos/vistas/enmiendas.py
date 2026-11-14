"""Enmiendas (5.7): cuatro pasos y al menos tres personas. Solicitar (TEC responsable, VER o GER,
C7); corregir en diez días hábiles como versión propuesta (C9); revisión técnica independiente con
el cálculo de materialidad (C10); autorización final de GER, que registra si el certificado ya fue
comercializado (C8). La versión corregida queda propuesta hasta la autorización."""

from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from autorizacion.proteccion import protegida
from cuentas.models import Usuario
from flujos import hechos as h
from flujos.comun import accion, anotar, celda, escribir, nombre, tabla, verbos, volver
from flujos.vistas.mediciones import FormularioVersion, _version
from flujos.vistas.asignaciones import _tecnicos
from negocio.models import Enmienda, EstadoEnmienda, Medicion, VersionMedicion
from nucleo import emision


class FormularioSolicitud(forms.Form):
    motivo = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 3}))
    evidencia = forms.CharField(label="Evidencia", widget=forms.Textarea(attrs={"rows": 3}),
                                help_text="Qué la respalda: documento, hoja de campo, fotografía o su huella.")
    responsable = forms.ModelChoiceField(label="Técnico que corrige", queryset=Usuario.objects.none(),
                                         help_text="El que registró la medición o, en su ausencia, el que designe supervisión.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable"].queryset = _tecnicos()
        self.fields["responsable"].label_from_instance = lambda u: f"{nombre(u)} ({u.username})"


class FormularioRevision(forms.Form):
    dictamen_favorable = forms.TypedChoiceField(label="Dictamen", coerce=lambda v: v == "si",
                                                choices=[("si", "Favorable"), ("no", "Desfavorable: se rechaza")])
    observaciones = forms.CharField(label="Observaciones de la revisión", widget=forms.Textarea(attrs={"rows": 3}))


class FormularioAutorizacion(forms.Form):
    comercializado = forms.TypedChoiceField(label="¿El certificado ya fue comercializado?", coerce=lambda v: v == "si",
                                            choices=[("no", "No"), ("si", "Sí")])
    acuerdo_dueno = forms.CharField(label="Acuerdo con el dueño", widget=forms.Textarea(attrs={"rows": 3}), required=False,
                                    help_text="Obligatorio si ya se comercializó.")

    def clean(self):
        datos = super().clean()
        if datos.get("comercializado") and not datos.get("acuerdo_dueno", "").strip():
            self.add_error("acuerdo_dueno", "Si ya se comercializó, registre qué se acordó con el dueño (C8).")
        return datos


def _propuesta(e):
    return e.versiones.order_by("-numero").first()


def _material(propuesta, vigente):
    """Es material si cambia cualquiera de los datos que entran en el cálculo de las toneladas."""
    return vigente is None or any(getattr(propuesta, c) != getattr(vigente, c) for c in VersionMedicion.CAMPOS_MATERIALES)


@require_http_methods(["GET"])
@protegida("leer", "enmiendas")
def lista(request):
    enmiendas = Enmienda.objects.select_related("medicion__parcela__finca", "solicitada_por", "responsable").order_by("-solicitada_en")
    filas = [[celda(f"{e.medicion.parcela.finca.codigo} · {e.medicion.parcela.codigo}", reverse("enmienda", args=[e.pk])),
              celda(nombre(e.solicitada_por)), celda(nombre(e.responsable)), celda(e.solicitada_en.strftime("%d/%m/%Y")),
              celda(estado=e.estado, estado_texto=e.get_estado_display())] for e in enmiendas]
    acciones = [accion("Exportar", reverse("exportar_enmiendas"))] if "exportar" in verbos(request, "enmiendas") else []
    return render(request, "flujos/lista.html", {
        "titulo": "Enmiendas",
        "descripcion": "Para solicitar una, entre a la medición. Corregir, revisar y autorizar los dan personas distintas.",
        "migas": [("Enmiendas", None)],
        "tabla": tabla(["Medición", "Solicitada por", "Corrige", "Fecha", "Estado"], filas,
                       vacio_titulo="No hay enmiendas que pueda ver"),
        "acciones": acciones,
    })


@require_http_methods(["GET"])
@protegida("leer", "enmiendas", objeto=h.enmienda)
def ficha(request, enmienda):
    e = get_object_or_404(Enmienda.objects.select_related(
        "medicion__parcela__finca", "medicion__version_vigente", "solicitada_por", "responsable", "corregida_por",
        "revisada_por", "autorizada_por"), pk=enmienda)
    permitidos = verbos(request, "enmiendas")
    propuesta = _propuesta(e)
    vigente = e.medicion.version_vigente
    filas = []
    for etiqueta, campo in (("Árboles", "arboles"), ("DAP (cm)", "dap_promedio_cm"), ("Altura (m)", "altura_promedio_m"),
                            ("Toneladas de CO₂", "toneladas_co2")):
        filas.append([celda(etiqueta), celda(str(getattr(vigente, campo)) if vigente else "—", numero=True),
                      celda(str(getattr(propuesta, campo)) if propuesta else "—", numero=True)])
    acciones = []
    if e.estado == EstadoEnmienda.SOLICITADA and "corregir" in permitidos:
        acciones.append(accion("Corregir", reverse("corregir_enmienda", args=[e.pk]), primaria=True))
    if e.estado == EstadoEnmienda.CORREGIDA and "revisar" in permitidos:
        acciones.append(accion("Revisar", reverse("revisar_enmienda", args=[e.pk]), primaria=True))
    if e.estado == EstadoEnmienda.REVISADA and "autorizar" in permitidos:
        acciones.append(accion("Autorizar", reverse("autorizar_enmienda", args=[e.pk]), primaria=True))
    return render(request, "flujos/ficha.html", {
        "titulo": f"Enmienda de {e.medicion.parcela.finca.codigo} · {e.medicion.parcela.codigo}",
        "migas": [("Enmiendas", reverse("enmiendas")), ("Enmienda", None)],
        "estado": e.estado, "estado_texto": e.get_estado_display(),
        "datos": [("Medición", e.medicion.parcela.finca.codigo + " · " + e.medicion.parcela.codigo),
                  ("Solicitó", nombre(e.solicitada_por)), ("Motivo", e.motivo), ("Evidencia", e.evidencia),
                  ("Corrige", nombre(e.responsable)), ("Corrigió", nombre(e.corregida_por)),
                  ("Material", {True: "Sí", False: "No"}.get(e.material)), ("Revisó", nombre(e.revisada_por)),
                  ("Dictamen", {True: "Favorable", False: "Desfavorable"}.get(e.dictamen_favorable)),
                  ("Autorizó", nombre(e.autorizada_por)),
                  ("Comercializado", {True: "Sí", False: "No"}.get(e.comercializado))],
        "acciones": acciones,
        "secciones": [tabla(["Dato", "Versión vigente", "Versión propuesta"], filas, titulo="Corrección",
                            numericas=("Versión vigente", "Versión propuesta"),
                            nota="Si cambia un dato del cálculo de toneladas, la enmienda es material (C10).")],
    })


@require_http_methods(["GET", "POST"])
@protegida("solicitar", "enmiendas", objeto=h.solicitud_enmienda)
def solicitar(request, medicion):
    m = get_object_or_404(Medicion.objects.select_related("parcela__finca"), pk=medicion)
    form = FormularioSolicitud(request.POST or None, initial={"responsable": m.creada_por_id})
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data

        def solicitar_():
            e = Enmienda.objects.create(medicion=m, solicitada_por=request.user, motivo=datos["motivo"],
                                        evidencia=datos["evidencia"], responsable=datos["responsable"])
            anotar(request, "solicitar", "enmiendas", e.pk, despues={"medicion": str(m.pk), "responsable": datos["responsable"].username})
            return e

        e, hecho = escribir(request, "solicitar", "enmiendas", m.pk, solicitar_)
        if hecho:
            return volver(request, reverse("enmienda", args=[e.pk]), "Enmienda solicitada.")
    return render(request, "flujos/formulario.html", {
        "titulo": "Solicitar enmienda",
        "descripcion": "Se pide sobre una medición aprobada, o devuelta o excluida con el período cerrado (C7).",
        "migas": [("Mediciones", reverse("mediciones")), ("Medición", reverse("medicion", args=[m.pk])), ("Enmienda", None)],
        "form": form, "boton": "Solicitar", "cancelar": reverse("medicion", args=[m.pk]),
    })


@require_http_methods(["GET", "POST"])
@protegida("corregir", "enmiendas", objeto=h.enmienda)
def corregir(request, enmienda):
    e = get_object_or_404(Enmienda.objects.select_related("medicion__version_vigente"), pk=enmienda)
    v = e.medicion.version_vigente
    inicial = {k: getattr(v, k) for k in ("fecha_medicion", "arboles", "dap_promedio_cm", "altura_promedio_m",
                                          "toneladas_co2")} if v else {}
    form = FormularioVersion(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        def corregir_():
            numero = (e.medicion.versiones.order_by("-numero").values_list("numero", flat=True).first() or 0) + 1
            propuesta = _version(e.medicion, numero, request.user, form.cleaned_data, enmienda=e)
            material = _material(propuesta, v)
            Enmienda.objects.filter(pk=e.pk).update(estado=EstadoEnmienda.CORREGIDA, corregida_por=request.user,
                                                    corregida_en=timezone.now(), material=material)
            anotar(request, "corregir", "enmiendas", e.pk, despues={"version": numero, "material": material})

        if escribir(request, "corregir", "enmiendas", e.pk, corregir_)[1]:
            return volver(request, reverse("enmienda", args=[e.pk]), "Corrección registrada como versión propuesta.")
    return render(request, "flujos/formulario.html", {
        "titulo": "Corregir la medición",
        "descripcion": "Dentro de los diez días hábiles desde la solicitud (C9). Queda como versión propuesta.",
        "migas": [("Enmiendas", reverse("enmiendas")), ("Enmienda", reverse("enmienda", args=[e.pk])), ("Corregir", None)],
        "form": form, "boton": "Registrar corrección", "cancelar": reverse("enmienda", args=[e.pk]),
    })


@require_http_methods(["GET", "POST"])
@protegida("revisar", "enmiendas", objeto=h.enmienda)
def revisar(request, enmienda):
    e = get_object_or_404(Enmienda, pk=enmienda)
    form = FormularioRevision(request.POST or None)
    if request.method == "POST" and form.is_valid():
        favorable = form.cleaned_data["dictamen_favorable"]

        def revisar_():
            Enmienda.objects.filter(pk=e.pk).update(
                estado=EstadoEnmienda.REVISADA if favorable else EstadoEnmienda.RECHAZADA, revisada_por=request.user,
                revisada_en=timezone.now(), dictamen_favorable=favorable,
                observaciones_revision=form.cleaned_data["observaciones"])
            anotar(request, "revisar", "enmiendas", e.pk, despues={"dictamen_favorable": favorable})

        if escribir(request, "revisar", "enmiendas", e.pk, revisar_)[1]:
            return volver(request, reverse("enmienda", args=[e.pk]), "Revisión registrada.")
    return render(request, "flujos/formulario.html", {
        "titulo": "Revisión técnica",
        "descripcion": "La da alguien que no es autor ni solicitante; si es material, tampoco quien aprobó (C10).",
        "migas": [("Enmiendas", reverse("enmiendas")), ("Enmienda", reverse("enmienda", args=[e.pk])), ("Revisar", None)],
        "datos": [("Material", "Sí" if e.material else "No")],
        "form": form, "boton": "Registrar dictamen", "cancelar": reverse("enmienda", args=[e.pk]),
    })


@require_http_methods(["GET", "POST"])
@protegida("autorizar", "enmiendas", objeto=h.enmienda)
def autorizar(request, enmienda):
    e = get_object_or_404(Enmienda.objects.select_related("medicion"), pk=enmienda)
    form = FormularioAutorizacion(request.POST or None)
    if request.method == "POST" and form.is_valid():
        def autorizar_():
            propuesta = e.versiones.order_by("-numero").first() or _propuesta(e)
            Enmienda.objects.filter(pk=e.pk).update(
                estado=EstadoEnmienda.AUTORIZADA, autorizada_por=request.user, autorizada_en=timezone.now(),
                comercializado=form.cleaned_data["comercializado"], acuerdo_dueno=form.cleaned_data["acuerdo_dueno"])
            if propuesta:
                Medicion.objects.filter(pk=e.medicion_id).update(version_vigente=propuesta)
            anotar(request, "autorizar", "enmiendas", e.pk,
                   despues={"version_vigente": propuesta.numero if propuesta else None, "material": e.material})

        if escribir(request, "autorizar", "enmiendas", e.pk, autorizar_)[1]:
            # 6.5: si cambian las toneladas, el sistema revoca y reemite; si no, anota la enmienda.
            emision.despues_de_confirmar("/reemitir", {"enmienda": str(e.pk)})
            mensaje = "Enmienda autorizada; la versión corregida es la vigente."
            if e.material:
                mensaje += " Si la medición tenía certificado, el sistema lo revoca y emite su reemplazo."
            return volver(request, reverse("enmienda", args=[e.pk]), mensaje)
        return redirect("enmienda", e.pk)
    return render(request, "flujos/formulario.html", {
        "titulo": "Autorización final",
        "descripcion": "Con dictamen favorable, y la da alguien que no solicitó, no revisó y no escribió la medición (C8).",
        "migas": [("Enmiendas", reverse("enmiendas")), ("Enmienda", reverse("enmienda", args=[e.pk])), ("Autorizar", None)],
        "form": form, "boton": "Autorizar", "cancelar": reverse("enmienda", args=[e.pk]),
    })
