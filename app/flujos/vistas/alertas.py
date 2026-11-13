"""Alertas de historial (5.8): SUP atiende las de sus técnicos; GER, las de quien no tiene
supervisor y las que SUP no resolvió en dos días hábiles; nadie resuelve una sobre sí mismo (C15,
T-36). AUD las lee dentro de su ventana."""

from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from autorizacion.proteccion import protegida
from flujos import hechos as h
from flujos.comun import accion, anotar, celda, escribir, nombre, tabla, verbos, volver
from negocio.models import Alerta


class FormularioResolucion(forms.Form):
    resolucion = forms.CharField(label="Resolución", widget=forms.Textarea(attrs={"rows": 3}),
                                 help_text="Qué se revisó y qué se decidió. Queda en la bitácora.")


@require_http_methods(["GET"])
@protegida("leer", "alertas")
def lista(request):
    alertas = h.alertas_visibles(request, Alerta.objects.select_related("sujeto", "resuelta_por")).order_by("resuelta_en", "-creada_en")
    resolver = "resolver" in verbos(request, "alertas")
    filas = []
    for a in alertas:
        fila = [celda(nombre(a.sujeto)), celda(a.get_control_display()),
                celda(estado=a.nivel, estado_texto=a.get_nivel_display()), celda(timezone.localtime(a.creada_en).strftime("%d/%m/%Y %H:%M")),
                celda(nombre(a.resuelta_por) if a.resuelta_por else "Pendiente")]
        if resolver:
            fila.append(celda("Resolver", reverse("resolver_alerta", args=[a.pk])) if not a.resuelta_en else celda("—"))
        filas.append(fila)
    columnas = ["Persona", "Control", "Nivel", "Creada", "Resuelta por"] + (["Acción"] if resolver else [])
    acciones = [accion("Exportar", reverse("exportar_alertas"))] if "exportar" in verbos(request, "alertas") else []
    return render(request, "flujos/lista.html", {
        "titulo": "Alertas de historial",
        "descripcion": "Las que le toca atender a su rol. Nunca aparecen aquí las que son sobre usted.",
        "migas": [("Alertas", None)],
        "tabla": tabla(columnas, filas, vacio_titulo="No hay alertas para usted"),
        "acciones": acciones,
    })


@require_http_methods(["GET", "POST"])
@protegida("resolver", "alertas", objeto=h.alerta)
def resolver(request, alerta):
    a = get_object_or_404(Alerta.objects.select_related("sujeto"), pk=alerta)
    form = FormularioResolucion(request.POST or None)
    if request.method == "POST" and form.is_valid():
        def resolver_():
            a.resuelta_por, a.resuelta_en, a.resolucion = request.user, timezone.now(), form.cleaned_data["resolucion"]
            a.save(update_fields=["resuelta_por", "resuelta_en", "resolucion"])
            anotar(request, "resolver", "alertas", a.pk, despues={"sujeto": a.sujeto.username})

        if escribir(request, "resolver", "alertas", a.pk, resolver_)[1]:
            return volver(request, reverse("alertas"), "Alerta resuelta.")
        return redirect("alertas")
    return render(request, "flujos/formulario.html", {
        "titulo": "Resolver alerta",
        "migas": [("Alertas", reverse("alertas")), ("Resolver", None)],
        "datos": [("Persona", nombre(a.sujeto)), ("Control", a.get_control_display()), ("Nivel", a.get_nivel_display()),
                  ("Detalle", ", ".join(f"{k}: {v}" for k, v in (a.detalle or {}).items()))],
        "form": form, "boton": "Resolver", "cancelar": reverse("alertas"),
    })
