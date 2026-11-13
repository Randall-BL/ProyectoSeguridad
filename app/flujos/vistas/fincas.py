"""Catálogo (5.2): fincas, parcelas y sus propuestas. ADM propone el alta de una finca, el cambio
de titular o una parcela nueva; GER aprueba lo que propuso otra persona (C11). Una parcela con
mediciones no se edita: la propuesta crea una versión nueva que la reemplaza."""

from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from autorizacion.proteccion import protegida
from flujos import hechos as h
from flujos.comun import accion, anotar, celda, escribir, nombre, tabla, verbos, volver
from negocio.models import EstadoCatalogo, Finca, Medicion, Parcela, PropuestaCatalogo, Titular

WKT_AYUDA = "Polígono en WKT con longitud y latitud (WGS 84), cerrado: POLYGON((lon lat, lon lat, …, lon lat))."


def _poligono(valor):
    texto = (valor or "").strip()
    if not texto.upper().startswith("POLYGON((") or not texto.endswith("))"):
        raise forms.ValidationError("Escriba un polígono en WKT: POLYGON((lon lat, …)).")
    return texto


class FormularioAltaFinca(forms.Form):
    codigo = forms.CharField(label="Código", max_length=20)
    nombre = forms.CharField(label="Nombre", max_length=200)
    titular = forms.ModelChoiceField(label="Titular", queryset=Titular.objects.order_by("codigo"))
    ubicacion = forms.CharField(label="Ubicación (distrito)", max_length=300, required=False)
    parcela = forms.CharField(label="Código de la primera parcela", max_length=30, initial="P-01")
    geometria = forms.CharField(label="Geometría de la parcela", widget=forms.Textarea(attrs={"rows": 3}), help_text=WKT_AYUDA)

    def clean_geometria(self):
        return _poligono(self.cleaned_data["geometria"])

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].strip().upper()
        if Finca.objects.filter(codigo=codigo).exists():
            raise forms.ValidationError("Ya hay una finca con ese código.")
        return codigo


class FormularioTitular(forms.Form):
    titular_nuevo = forms.ModelChoiceField(label="Titular nuevo", queryset=Titular.objects.order_by("codigo"))


class FormularioParcela(forms.Form):
    reemplaza = forms.ModelChoiceField(
        label="Parcela que reemplaza", queryset=Parcela.objects.none(), required=False,
        help_text="Déjelo vacío para una parcela nueva.",
    )
    codigo = forms.CharField(label="Código (solo si es nueva)", max_length=30, required=False)
    geometria = forms.CharField(label="Geometría", widget=forms.Textarea(attrs={"rows": 3}), help_text=WKT_AYUDA)

    def __init__(self, *args, finca, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reemplaza"].queryset = Parcela.objects.filter(finca=finca, activa=True).order_by("codigo")
        self.fields["reemplaza"].label_from_instance = lambda p: f"{p.codigo} (versión {p.version})"

    def clean_geometria(self):
        return _poligono(self.cleaned_data["geometria"])

    def clean(self):
        datos = super().clean()
        if not datos.get("reemplaza") and not datos.get("codigo"):
            raise forms.ValidationError("Elija la parcela que reemplaza o escriba el código de una nueva.")
        return datos


def _fila_propuesta(p):
    if p.tipo == PropuestaCatalogo.Tipo.CAMBIO_TITULAR:
        detalle = f"Pasa a {p.titular_nuevo.codigo}" if p.titular_nuevo_id else ""
    elif p.parcela_id:
        detalle = f"Parcela {p.parcela.codigo}, versión {p.parcela.version}"
    else:
        detalle = ""
    return detalle


@require_http_methods(["GET"])
@protegida("leer", "fincas")
def lista(request):
    fincas = Finca.objects.select_related("titular").order_by("codigo")
    filas = [
        [
            celda(f.codigo, reverse("finca", args=[f.pk])),
            celda(f.nombre),
            celda(f.titular.codigo),
            celda(f.ubicacion),
            celda(estado=f.estado, estado_texto=f.get_estado_display()),
        ]
        for f in fincas
    ]
    permitidos = verbos(request, "fincas")
    acciones = []
    if "proponer" in permitidos:
        acciones.append(accion("Proponer una finca", reverse("proponer_finca"), primaria=True))
    if "exportar" in permitidos:
        acciones.append(accion("Exportar", reverse("exportar_fincas")))
    secciones = []
    if permitidos & {"proponer", "aprobar"}:
        pendientes = PropuestaCatalogo.objects.filter(estado=EstadoCatalogo.PROPUESTO).select_related(
            "finca", "propuesta_por", "titular_nuevo", "parcela"
        ).order_by("propuesta_en")
        secciones.append(tabla(
            ["Finca", "Propuesta", "Detalle", "Propuesta por"],
            [[celda(p.finca.codigo, reverse("finca", args=[p.finca_id])), celda(p.get_tipo_display()),
              celda(_fila_propuesta(p)), celda(nombre(p.propuesta_por))] for p in pendientes],
            titulo="Propuestas pendientes",
            nota="GER aprueba desde la ficha de la finca lo que propuso otra persona (C11).",
            vacio_titulo="No hay propuestas pendientes",
        ))
    return render(request, "flujos/lista.html", {
        "titulo": "Fincas",
        "descripcion": "Las fincas que su rol puede ver. La base filtra las filas: un técnico ve las asignadas y un dueño las suyas.",
        "migas": [("Fincas", None)],
        "tabla": tabla(["Código", "Nombre", "Titular", "Ubicación", "Estado"], filas,
                       vacio_titulo="No hay fincas que pueda ver"),
        "acciones": acciones,
        "secciones": secciones,
    })


@require_http_methods(["GET"])
@protegida("leer", "fincas", objeto=h.finca)
def ficha(request, finca):
    f = get_object_or_404(Finca.objects.select_related("titular"), pk=finca)
    permitidos = verbos(request, "fincas")
    medir = "crear" in verbos(request, "mediciones")
    parcelas = f.parcelas.order_by("codigo", "-version")
    columnas = ["Parcela", "Versión", "Área (ha)", "Estado", "Activa"] + (["Medición"] if medir else [])
    filas = []
    for p in parcelas:
        fila = [celda(p.codigo), celda(str(p.version), numero=True), celda(str(p.area_ha or "—"), numero=True),
                celda(estado=p.estado, estado_texto=p.get_estado_display()), celda("Sí" if p.activa else "No")]
        if medir:
            fila.append(celda("Registrar medición", reverse("nueva_medicion", args=[p.pk])) if p.activa else celda("—"))
        filas.append(fila)
    mediciones = Medicion.objects.filter(parcela__finca=f).select_related("parcela", "periodo").order_by("-creada_en")
    filas_m = [[celda(m.parcela.codigo, reverse("medicion", args=[m.pk])), celda(m.periodo.nombre),
                celda(estado=m.estado, estado_texto=m.get_estado_display())] for m in mediciones]
    propuestas = f.propuestas.select_related("propuesta_por", "titular_nuevo", "parcela").order_by("-propuesta_en")
    filas_p = [[celda(p.get_tipo_display()), celda(_fila_propuesta(p)), celda(nombre(p.propuesta_por)),
                celda(estado=p.estado, estado_texto=p.get_estado_display())] for p in propuestas]
    acciones = []
    if "proponer" in permitidos:
        acciones += [accion("Proponer cambio de titular", reverse("proponer_titular", args=[f.pk])),
                     accion("Proponer parcela o geometría", reverse("proponer_parcela", args=[f.pk]))]
    if "aprobar" in permitidos:
        acciones += [accion(f"Aprobar: {p.get_tipo_display().lower()}", reverse("aprobar_catalogo", args=[p.pk]),
                            metodo="post", primaria=True)
                     for p in propuestas if p.estado == EstadoCatalogo.PROPUESTO]
    return render(request, "flujos/ficha.html", {
        "titulo": f"{f.codigo} · {f.nombre}",
        "migas": [("Fincas", reverse("fincas")), (f.codigo, None)],
        "estado": f.estado, "estado_texto": f.get_estado_display(),
        "datos": [("Código", f.codigo), ("Titular", f.titular.codigo), ("Ubicación", f.ubicacion)],
        "acciones": acciones,
        "secciones": [
            tabla(columnas, filas, titulo="Parcelas", numericas=("Versión", "Área (ha)"), vacio_titulo="Sin parcelas"),
            tabla(["Parcela", "Período", "Estado"], filas_m, titulo="Mediciones", vacio_titulo="Sin mediciones que pueda ver"),
            tabla(["Propuesta", "Detalle", "Propuesta por", "Estado"], filas_p, titulo="Propuestas de catálogo",
                  vacio_titulo="Sin propuestas"),
        ],
    })


@require_http_methods(["GET", "POST"])
@protegida("proponer", "fincas", objeto=h.propuesta_finca, formulario=True)
def proponer_finca(request):
    form = FormularioAltaFinca(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data

        def proponer():
            finca = Finca.objects.create(codigo=datos["codigo"], nombre=datos["nombre"], titular=datos["titular"],
                                         ubicacion=datos["ubicacion"])
            parcela = Parcela.objects.create(finca=finca, codigo=datos["parcela"], geometria=datos["geometria"])
            propuesta = PropuestaCatalogo.objects.create(tipo=PropuestaCatalogo.Tipo.ALTA_FINCA, finca=finca,
                                                         parcela=parcela, propuesta_por=request.user)
            anotar(request, "proponer", "fincas", propuesta.pk, despues={"finca": finca.codigo, "tipo": "alta_finca"})
            return finca

        finca, hecho = escribir(request, "proponer", "fincas", "", proponer)
        if hecho:
            return volver(request, reverse("finca", args=[finca.pk]), "Alta propuesta: espera la aprobación de Gerencia.")
    return render(request, "flujos/formulario.html", {
        "titulo": "Proponer una finca",
        "descripcion": "Queda en estado propuesto hasta que una persona de Gerencia, distinta de usted, la apruebe (C11).",
        "migas": [("Fincas", reverse("fincas")), ("Proponer", None)],
        "form": form, "boton": "Proponer", "cancelar": reverse("fincas"),
    })


@require_http_methods(["GET", "POST"])
@protegida("proponer", "fincas", objeto=h.finca, formulario=True)
def proponer_titular(request, finca):
    f = get_object_or_404(Finca, pk=finca)
    form = FormularioTitular(request.POST or None)
    if request.method == "POST" and form.is_valid():
        def proponer():
            propuesta = PropuestaCatalogo.objects.create(tipo=PropuestaCatalogo.Tipo.CAMBIO_TITULAR, finca=f,
                                                         titular_nuevo=form.cleaned_data["titular_nuevo"],
                                                         propuesta_por=request.user)
            anotar(request, "proponer", "fincas", propuesta.pk,
                   antes={"titular": f.titular.codigo}, despues={"titular": form.cleaned_data["titular_nuevo"].codigo})

        if escribir(request, "proponer", "fincas", f.pk, proponer)[1]:
            return volver(request, reverse("finca", args=[f.pk]), "Cambio de titular propuesto.")
    return render(request, "flujos/formulario.html", {
        "titulo": f"Cambio de titular de {f.codigo}",
        "migas": [("Fincas", reverse("fincas")), (f.codigo, reverse("finca", args=[f.pk])), ("Titular", None)],
        "datos": [("Titular actual", f.titular.codigo)],
        "form": form, "boton": "Proponer", "cancelar": reverse("finca", args=[f.pk]),
    })


@require_http_methods(["GET", "POST"])
@protegida("proponer", "fincas", objeto=h.finca, formulario=True)
def proponer_parcela(request, finca):
    f = get_object_or_404(Finca, pk=finca)
    form = FormularioParcela(request.POST or None, finca=f)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        anterior = datos["reemplaza"]

        def proponer():
            parcela = Parcela.objects.create(
                finca=f, codigo=anterior.codigo if anterior else datos["codigo"],
                version=(anterior.version + 1) if anterior else 1, reemplaza=anterior, geometria=datos["geometria"],
            )
            propuesta = PropuestaCatalogo.objects.create(tipo=PropuestaCatalogo.Tipo.GEOMETRIA, finca=f,
                                                         parcela=parcela, propuesta_por=request.user)
            anotar(request, "proponer", "fincas", propuesta.pk,
                   despues={"parcela": parcela.codigo, "version": parcela.version})

        if escribir(request, "proponer", "fincas", f.pk, proponer)[1]:
            return volver(request, reverse("finca", args=[f.pk]), "Parcela propuesta.")
    return render(request, "flujos/formulario.html", {
        "titulo": f"Parcela de {f.codigo}",
        "descripcion": "Una parcela con mediciones no se edita: se propone una versión nueva que la reemplaza.",
        "migas": [("Fincas", reverse("fincas")), (f.codigo, reverse("finca", args=[f.pk])), ("Parcela", None)],
        "form": form, "boton": "Proponer", "cancelar": reverse("finca", args=[f.pk]),
    })


@require_POST
@protegida("aprobar", "fincas", objeto=h.aprobacion_catalogo)
def aprobar(request, propuesta):
    p = get_object_or_404(PropuestaCatalogo.objects.select_related("finca", "parcela"), pk=propuesta)

    def aplicar():
        if p.tipo == PropuestaCatalogo.Tipo.ALTA_FINCA:
            Finca.objects.filter(pk=p.finca_id).update(estado=EstadoCatalogo.APROBADO)
        elif p.tipo == PropuestaCatalogo.Tipo.CAMBIO_TITULAR:
            Finca.objects.filter(pk=p.finca_id).update(titular=p.titular_nuevo_id)
        if p.parcela_id:
            if p.parcela.reemplaza_id:
                Parcela.objects.filter(pk=p.parcela.reemplaza_id).update(activa=False)
            parcela = Parcela.objects.get(pk=p.parcela_id)
            parcela.estado, parcela.activa = EstadoCatalogo.APROBADO, True
            parcela.save(update_fields=["estado", "activa"])
        PropuestaCatalogo.objects.filter(pk=p.pk).update(
            estado=EstadoCatalogo.APROBADO, aprobada_por=request.user, aprobada_en=timezone.now()
        )
        anotar(request, "aprobar", "fincas", p.pk, despues={"tipo": p.tipo, "finca": p.finca.codigo})

    if escribir(request, "aprobar", "fincas", p.pk, aplicar)[1]:
        return volver(request, reverse("finca", args=[p.finca_id]), "Propuesta aprobada.")
    return redirect("finca", p.finca_id)
