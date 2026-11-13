"""Mediciones (5.6): TEC crea, modifica (versión nueva) y envía, con la fecha de medición que declara
y la de registro que pone el servidor (C2, T-30). VER aprueba o devuelve con observaciones (C3). El
formulario de aprobación no tiene campo de aprobador: sale de la sesión (K-2, T-40). Más de cinco
días hábiles entre la medición y el registro piden un motivo."""

from decimal import Decimal

from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from autorizacion.proteccion import protegida
from flujos import hechos as h
from flujos.comun import accion, anotar, celda, escribir, nombre, tabla, verbos, volver
from negocio.models import EstadoMedicion, Medicion, Parcela, VersionMedicion
from nucleo.dias import dias_habiles

DIAS_SIN_MOTIVO = 5
EDITABLE = (EstadoMedicion.BORRADOR, EstadoMedicion.DEVUELTA)


class FormularioVersion(forms.Form):
    fecha_medicion = forms.DateField(label="Fecha de la medición", widget=forms.DateInput(attrs={"type": "date"}),
                                     help_text="La que usted declara. La de registro la pone el servidor.")
    arboles = forms.IntegerField(label="Árboles medidos", min_value=1)
    dap_promedio_cm = forms.DecimalField(label="DAP promedio (cm)", min_value=Decimal("0.01"), max_digits=6, decimal_places=2)
    altura_promedio_m = forms.DecimalField(label="Altura promedio (m)", min_value=Decimal("0.01"), max_digits=6, decimal_places=2)
    toneladas_co2 = forms.DecimalField(label="Toneladas de CO₂", min_value=Decimal("0"), max_digits=10, decimal_places=3)
    huella_hoja_campo = forms.CharField(label="Huella SHA-256 de la hoja de campo", max_length=64, required=False)
    observaciones = forms.CharField(label="Observaciones", widget=forms.Textarea(attrs={"rows": 3}), required=False)
    motivo_tardio = forms.CharField(label="Motivo del registro tardío", max_length=500, required=False,
                                    help_text=f"Obligatorio si pasaron más de {DIAS_SIN_MOTIVO} días hábiles desde la medición.")

    def clean(self):
        datos = super().clean()
        fecha = datos.get("fecha_medicion")
        if fecha and fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de la medición no puede ser posterior a hoy (C2).")
        if fecha and dias_habiles(fecha) > DIAS_SIN_MOTIVO and not datos.get("motivo_tardio", "").strip():
            self.add_error("motivo_tardio", "Pasaron más de cinco días hábiles: escriba el motivo.")
        return datos


class FormularioDevolucion(forms.Form):
    observaciones = forms.CharField(label="Observaciones para el técnico", widget=forms.Textarea(attrs={"rows": 4}))


def _observaciones(datos):
    texto = datos.get("observaciones", "").strip()
    if datos.get("motivo_tardio", "").strip():
        texto = (texto + "\n" if texto else "") + f"Registro tardío: {datos['motivo_tardio'].strip()}"
    return texto


def _version(medicion, numero, autor, datos, *, enmienda=None):
    """Una versión no se modifica nunca (la base solo deja insertar): la de una enmienda nace
    marcada como propuesta y enlazada a ella."""
    return VersionMedicion.objects.create(
        medicion=medicion, numero=numero, autor=autor, fecha_medicion=datos["fecha_medicion"], arboles=datos["arboles"],
        dap_promedio_cm=datos["dap_promedio_cm"], altura_promedio_m=datos["altura_promedio_m"],
        toneladas_co2=datos["toneladas_co2"], huella_hoja_campo=datos.get("huella_hoja_campo", ""),
        observaciones=_observaciones(datos), es_propuesta=enmienda is not None, enmienda=enmienda,
    )


@require_http_methods(["GET"])
@protegida("leer", "mediciones")
def lista(request):
    mediciones = Medicion.objects.select_related("parcela__finca", "periodo", "version_vigente").order_by("-creada_en")
    filas = [[celda(f"{m.parcela.finca.codigo} · {m.parcela.codigo}", reverse("medicion", args=[m.pk])),
              celda(m.periodo.nombre),
              celda(str(m.version_vigente.toneladas_co2) if m.version_vigente else "—", numero=True),
              celda(estado=m.estado, estado_texto=m.get_estado_display())] for m in mediciones]
    acciones = []
    if "exportar" in verbos(request, "mediciones"):
        acciones.append(accion("Exportar", reverse("exportar_mediciones")))
    return render(request, "flujos/lista.html", {
        "titulo": "Mediciones",
        "descripcion": "Para registrar una, entre a la finca y elija la parcela. Un dueño ve solo las aprobadas.",
        "migas": [("Mediciones", None)],
        "tabla": tabla(["Finca y parcela", "Período", "Toneladas de CO₂", "Estado"], filas,
                       numericas=("Toneladas de CO₂",), vacio_titulo="No hay mediciones que pueda ver"),
        "acciones": acciones,
    })


@require_http_methods(["GET"])
@protegida("leer", "mediciones", objeto=h.medicion)
def ficha(request, medicion):
    m = get_object_or_404(Medicion.objects.select_related("parcela__finca", "periodo", "creada_por", "aprobada_por",
                                                          "version_vigente"), pk=medicion)
    permitidos = verbos(request, "mediciones")
    versiones = m.versiones.select_related("autor").order_by("numero")
    filas_v = [[celda(f"{v.numero}{' · propuesta' if v.es_propuesta else ''}{' · vigente' if m.version_vigente_id == v.pk else ''}"),
                celda(nombre(v.autor)), celda(v.fecha_medicion.strftime("%d/%m/%Y")),
                celda(timezone.localtime(v.fecha_registro).strftime("%d/%m/%Y %H:%M")), celda(str(v.arboles), numero=True),
                celda(str(v.toneladas_co2), numero=True)] for v in versiones]
    enmiendas = m.enmiendas.select_related("solicitada_por").order_by("-solicitada_en")
    filas_e = [[celda(e.solicitada_en.strftime("%d/%m/%Y"), reverse("enmienda", args=[e.pk])),
                celda(nombre(e.solicitada_por)), celda(estado=e.estado, estado_texto=e.get_estado_display())] for e in enmiendas]
    acciones = []
    if m.estado in EDITABLE and permitidos & {"modificar", "enviar"}:
        acciones += [accion("Nueva versión", reverse("modificar_medicion", args=[m.pk])),
                     accion("Enviar a verificación", reverse("enviar_medicion", args=[m.pk]), metodo="post", primaria=True)]
    if m.estado == EstadoMedicion.ENVIADA and permitidos & {"aprobar", "devolver"}:
        acciones += [accion("Aprobar", reverse("aprobar_medicion", args=[m.pk]), metodo="post", primaria=True),
                     accion("Devolver con observaciones", reverse("devolver_medicion", args=[m.pk]))]
    if "solicitar" in verbos(request, "enmiendas"):
        acciones.append(accion("Solicitar enmienda", reverse("solicitar_enmienda", args=[m.pk])))
    vigente = m.version_vigente
    return render(request, "flujos/ficha.html", {
        "titulo": f"Medición de {m.parcela.finca.codigo} · {m.parcela.codigo}",
        "descripcion": f"Período {m.periodo.nombre}.",
        "migas": [("Mediciones", reverse("mediciones")), (f"{m.parcela.finca.codigo} · {m.parcela.codigo}", None)],
        "estado": m.estado, "estado_texto": m.get_estado_display(),
        "datos": [("Finca", m.parcela.finca.codigo), ("Parcela", f"{m.parcela.codigo} (versión {m.parcela.version})"),
                  ("Período", m.periodo.nombre), ("Registró", nombre(m.creada_por)),
                  ("Toneladas de CO₂", vigente.toneladas_co2 if vigente else None),
                  ("Aprobó", nombre(m.aprobada_por)), ("Observaciones", m.observaciones)],
        "acciones": acciones,
        "secciones": [
            tabla(["Versión", "Autor", "Medición", "Registro", "Árboles", "Toneladas"], filas_v, titulo="Versiones",
                  numericas=("Árboles", "Toneladas"),
                  nota="Cada cambio es una versión nueva; quien escribió una no puede aprobar la medición (C3)."),
            tabla(["Solicitada", "Por", "Estado"], filas_e, titulo="Enmiendas", vacio_titulo="Sin enmiendas"),
        ],
    })


@require_http_methods(["GET", "POST"])
@protegida("crear", "mediciones", objeto=h.nueva_medicion, cambio=h.cambio_medicion)
def crear(request, parcela):
    p = get_object_or_404(Parcela.objects.select_related("finca"), pk=parcela, activa=True)
    periodo = h.periodo_abierto()
    form = FormularioVersion(request.POST or None)
    if request.method == "POST" and form.is_valid() and periodo:
        def crear_():
            m = Medicion.objects.create(parcela=p, periodo=periodo, creada_por=request.user)
            v = _version(m, 1, request.user, form.cleaned_data)
            m.version_vigente = v
            m.save(update_fields=["version_vigente"])
            anotar(request, "crear", "mediciones", m.pk, despues={"version": 1, "toneladas": str(v.toneladas_co2)})
            return m

        m, hecho = escribir(request, "crear", "mediciones", "", crear_)
        if hecho:
            return volver(request, reverse("medicion", args=[m.pk]), "Medición registrada como borrador.")
    return render(request, "flujos/formulario.html", {
        "titulo": f"Registrar medición en {p.finca.codigo} · {p.codigo}",
        "descripcion": "Queda en borrador hasta que la envíe a verificación.",
        "migas": [("Fincas", reverse("fincas")), (p.finca.codigo, reverse("finca", args=[p.finca_id])), ("Medición", None)],
        "datos": [("Período", periodo.nombre if periodo else "No hay un período abierto")],
        "form": form, "boton": "Registrar", "cancelar": reverse("finca", args=[p.finca_id]),
    })


@require_http_methods(["GET", "POST"])
@protegida("modificar", "mediciones", objeto=h.medicion, cambio=h.cambio_medicion)
def modificar(request, medicion):
    m = get_object_or_404(Medicion.objects.select_related("parcela__finca", "version_vigente"), pk=medicion)
    v = m.version_vigente
    inicial = {k: getattr(v, k) for k in ("fecha_medicion", "arboles", "dap_promedio_cm", "altura_promedio_m",
                                          "toneladas_co2", "huella_hoja_campo")} if v else {}
    form = FormularioVersion(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        def modificar_():
            numero = (m.versiones.order_by("-numero").values_list("numero", flat=True).first() or 0) + 1
            nueva = _version(m, numero, request.user, form.cleaned_data)
            m.version_vigente = nueva
            m.save(update_fields=["version_vigente"])
            anotar(request, "modificar", "mediciones", m.pk, antes={"version": numero - 1}, despues={"version": numero})

        if escribir(request, "modificar", "mediciones", m.pk, modificar_)[1]:
            return volver(request, reverse("medicion", args=[m.pk]), "Versión nueva registrada.")
    return render(request, "flujos/formulario.html", {
        "titulo": "Nueva versión de la medición",
        "descripcion": "La versión anterior no se borra: queda en el historial de la medición.",
        "migas": [("Mediciones", reverse("mediciones")), ("Medición", reverse("medicion", args=[m.pk])), ("Nueva versión", None)],
        "form": form, "boton": "Guardar versión", "cancelar": reverse("medicion", args=[m.pk]),
    })


@require_POST
@protegida("enviar", "mediciones", objeto=h.medicion)
def enviar(request, medicion):
    m = get_object_or_404(Medicion, pk=medicion)

    def enviar_():
        antes = m.estado
        m.estado = EstadoMedicion.ENVIADA
        m.save(update_fields=["estado"])
        anotar(request, "enviar", "mediciones", m.pk, antes={"estado": antes}, despues={"estado": m.estado})

    if escribir(request, "enviar", "mediciones", m.pk, enviar_)[1]:
        return volver(request, reverse("medicion", args=[m.pk]), "Medición enviada a verificación.")
    return redirect("medicion", m.pk)


@require_POST
@protegida("aprobar", "mediciones", objeto=h.medicion)
def aprobar(request, medicion):
    """Quien aprueba sale de la sesión del servidor; un aprobador_id en la petición se ignora (T-40)."""
    m = get_object_or_404(Medicion, pk=medicion)

    def aprobar_():
        m.estado, m.aprobada_por, m.aprobada_en = EstadoMedicion.APROBADA, request.user, timezone.now()
        m.save(update_fields=["estado", "aprobada_por", "aprobada_en"])
        anotar(request, "aprobar", "mediciones", m.pk, antes={"estado": "enviada"}, despues={"estado": "aprobada"})

    if escribir(request, "aprobar", "mediciones", m.pk, aprobar_)[1]:
        return volver(request, reverse("medicion", args=[m.pk]), "Medición aprobada.")
    return redirect("medicion", m.pk)


@require_http_methods(["GET", "POST"])
@protegida("devolver", "mediciones", objeto=h.medicion)
def devolver(request, medicion):
    m = get_object_or_404(Medicion.objects.select_related("parcela__finca"), pk=medicion)
    form = FormularioDevolucion(request.POST or None)
    if request.method == "POST" and form.is_valid():
        def devolver_():
            m.estado, m.observaciones = EstadoMedicion.DEVUELTA, form.cleaned_data["observaciones"]
            m.save(update_fields=["estado", "observaciones"])
            anotar(request, "devolver", "mediciones", m.pk, antes={"estado": "enviada"}, despues={"estado": "devuelta"})

        if escribir(request, "devolver", "mediciones", m.pk, devolver_)[1]:
            return volver(request, reverse("medicion", args=[m.pk]), "Medición devuelta al técnico.")
    return render(request, "flujos/formulario.html", {
        "titulo": "Devolver la medición",
        "migas": [("Mediciones", reverse("mediciones")), ("Medición", reverse("medicion", args=[m.pk])), ("Devolver", None)],
        "form": form, "boton": "Devolver", "cancelar": reverse("medicion", args=[m.pk]),
    })
