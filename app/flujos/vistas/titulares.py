"""Datos personales de los titulares (5.9): ADM los registra y los mantiene; se suprimen solo si no
hay obligación de conservarlos, es decir, si el titular no tiene un certificado emitido en los
últimos diez años (C16, T-37, POL-BT-04). Los leen TEC (sus fincas, C1), GER y ADM (con H1 a H3),
AUD en su ventana y DUE los suyos (C5)."""

from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from autorizacion.proteccion import protegida
from flujos import hechos as h
from flujos.comun import accion, anotar, celda, escribir, tabla, verbos, volver
from negocio.models import DatosPersonales, Titular


class FormularioDatos(forms.Form):
    nombre = forms.CharField(label="Nombre o razón social", max_length=200)
    identificacion = forms.CharField(label="Identificación", max_length=30)
    telefono = forms.CharField(label="Teléfono", max_length=30, required=False)
    correo = forms.EmailField(label="Correo", required=False)
    direccion = forms.CharField(label="Dirección", max_length=300, required=False)


class FormularioTitularNuevo(FormularioDatos):
    codigo = forms.CharField(label="Código del titular", max_length=20, help_text="Por ejemplo T-009.")
    tipo = forms.ChoiceField(label="Tipo", choices=Titular.Tipo.choices)

    field_order = ["codigo", "tipo", "nombre", "identificacion", "telefono", "correo", "direccion"]

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].strip().upper()
        if Titular.objects.filter(codigo=codigo).exists():
            raise forms.ValidationError("Ya hay un titular con ese código.")
        return codigo


@require_http_methods(["GET"])
@protegida("leer", "datos_personales")
def lista(request):
    titulares = Titular.objects.select_related("datos").order_by("codigo")
    filas = []
    for t in titulares:
        datos = getattr(t, "datos", None)
        suprimido = datos is not None and datos.suprimido_en is not None
        filas.append([celda(t.codigo, reverse("titular", args=[t.pk])), celda(t.get_tipo_display()),
                      celda("Suprimido" if suprimido else (datos.nombre if datos else "Sin datos")),
                      celda(str(t.fincas.count()), numero=True)])
    acciones = [accion("Registrar titular", reverse("crear_titular"), primaria=True)] if "crear" in verbos(request, "datos_personales") else []
    return render(request, "flujos/lista.html", {
        "titulo": "Titulares",
        "descripcion": "Quiénes son dueños de las fincas. Sus datos personales no salen en las exportaciones de auditoría.",
        "migas": [("Titulares", None)],
        "tabla": tabla(["Código", "Tipo", "Nombre", "Fincas"], filas, numericas=("Fincas",),
                       vacio_titulo="No hay titulares que pueda ver"),
        "acciones": acciones,
    })


@require_http_methods(["GET"])
@protegida("leer", "datos_personales", objeto=h.titular)
def ficha(request, titular):
    t = get_object_or_404(Titular, pk=titular)
    datos = DatosPersonales.objects.filter(titular=t).first()
    permitidos = verbos(request, "datos_personales")
    acciones = []
    if datos is None and "crear" in permitidos:
        acciones.append(accion("Registrar datos", reverse("editar_titular", args=[t.pk]), primaria=True))
    if datos and not datos.suprimido_en:
        if "modificar" in permitidos:
            acciones.append(accion("Actualizar datos", reverse("editar_titular", args=[t.pk])))
        if "eliminar" in permitidos:
            acciones.append(accion("Suprimir datos", reverse("suprimir_titular", args=[t.pk]), metodo="post", peligro=True))
    fincas = [[celda(f.codigo, reverse("finca", args=[f.pk])), celda(f.nombre)] for f in t.fincas.order_by("codigo")]
    return render(request, "flujos/ficha.html", {
        "titulo": f"Titular {t.codigo}",
        "migas": [("Titulares", reverse("titulares")), (t.codigo, None)],
        "datos": [("Tipo", t.get_tipo_display())] + ([
            ("Nombre", datos.nombre), ("Identificación", datos.identificacion), ("Teléfono", datos.telefono),
            ("Correo", datos.correo), ("Dirección", datos.direccion),
            ("Suprimidos", datos.suprimido_en.strftime("%d/%m/%Y") if datos.suprimido_en else None)] if datos else
            [("Datos personales", "Sin registrar")]),
        "acciones": acciones,
        "secciones": [tabla(["Finca", "Nombre"], fincas, titulo="Fincas", vacio_titulo="Sin fincas que pueda ver")],
    })


@require_http_methods(["GET", "POST"])
@protegida("crear", "datos_personales", formulario=True)
def crear(request):
    form = FormularioTitularNuevo(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data

        def crear_():
            t = Titular.objects.create(codigo=d["codigo"], tipo=d["tipo"])
            DatosPersonales.objects.create(titular=t, **{k: d[k] for k in ("nombre", "identificacion", "telefono", "correo", "direccion")})
            anotar(request, "crear", "datos_personales", t.pk, despues={"titular": t.codigo})
            return t

        t, hecho = escribir(request, "crear", "datos_personales", "", crear_)
        if hecho:
            return volver(request, reverse("titular", args=[t.pk]), "Titular registrado.")
    return render(request, "flujos/formulario.html", {
        "titulo": "Registrar titular", "migas": [("Titulares", reverse("titulares")), ("Registrar", None)],
        "form": form, "boton": "Registrar", "cancelar": reverse("titulares"),
    })


@require_http_methods(["GET", "POST"])
@protegida("modificar", "datos_personales", objeto=h.titular)
def editar(request, titular):
    t = get_object_or_404(Titular, pk=titular)
    datos = DatosPersonales.objects.filter(titular=t, suprimido_en__isnull=True).first()
    inicial = {k: getattr(datos, k) for k in ("nombre", "identificacion", "telefono", "correo", "direccion")} if datos else {}
    form = FormularioDatos(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        def editar_():
            DatosPersonales.objects.update_or_create(titular=t, defaults=form.cleaned_data)
            anotar(request, "modificar", "datos_personales", t.pk, antes=inicial or None, despues=form.cleaned_data)

        if escribir(request, "modificar", "datos_personales", t.pk, editar_)[1]:
            return volver(request, reverse("titular", args=[t.pk]), "Datos actualizados.")
    return render(request, "flujos/formulario.html", {
        "titulo": f"Datos de {t.codigo}", "migas": [("Titulares", reverse("titulares")), (t.codigo, reverse("titular", args=[t.pk])), ("Datos", None)],
        "form": form, "boton": "Guardar", "cancelar": reverse("titular", args=[t.pk]),
    })


@require_POST
@protegida("eliminar", "datos_personales", objeto=h.titular)
def suprimir(request, titular):
    t = get_object_or_404(Titular, pk=titular)

    def suprimir_():
        DatosPersonales.objects.filter(titular=t).update(
            nombre="Suprimido", identificacion="", telefono="", correo="", direccion="", suprimido_en=timezone.now())
        anotar(request, "eliminar", "datos_personales", t.pk, despues={"suprimidos": True})

    if escribir(request, "eliminar", "datos_personales", t.pk, suprimir_)[1]:
        return volver(request, reverse("titular", args=[t.pk]), "Datos personales suprimidos.")
    return redirect("titular", t.pk)
