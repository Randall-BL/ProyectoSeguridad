"""Cuentas (5.3): ADM crea cuentas, propone roles y habilitaciones, y desactiva; GER aprueba lo que
propuso otra persona; nadie se administra a sí mismo (C12, T-16). Cada quien mantiene sus
credenciales y su declaración de vínculos (C13); retirar un vínculo lo aprueba GER. Un cambio de
rol o una baja cierran las sesiones abiertas el mismo instante (POL-CA-04, POL-CA-05)."""

import secrets

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from autorizacion.proteccion import protegida
from cuentas.models import Declaracion, EstadoPropuesta, PropuestaRol, Rol, Usuario
from flujos import hechos as h
from flujos.comun import accion, anotar, celda, escribir, nombre, tabla, verbos, volver
from negocio.models import Titular, Vinculo


class FormularioCuenta(forms.Form):
    username = forms.CharField(label="Usuario", max_length=150, help_text="Por ejemplo ver.maria.")
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    identificacion = forms.CharField(label="Identificación", max_length=30)
    email = forms.EmailField(label="Correo", required=False)
    supervisor = forms.ModelChoiceField(label="Supervisor (solo técnicos)", required=False,
                                        queryset=Usuario.objects.filter(rol=Rol.SUP, is_active=True).order_by("username"))

    def clean_username(self):
        usuario = self.cleaned_data["username"].strip().lower()
        if Usuario.objects.filter(username=usuario).exists():
            raise forms.ValidationError("Ese usuario ya existe.")
        return usuario

    def clean_identificacion(self):
        valor = self.cleaned_data["identificacion"].strip()
        if Usuario.objects.filter(identificacion=valor).exists():
            raise forms.ValidationError("Ya hay una cuenta con esa identificación.")
        return valor


class FormularioRol(forms.Form):
    rol = forms.ChoiceField(label="Rol", choices=Rol.choices)
    es_habilitacion = forms.BooleanField(label="Habilitación temporal (además de su rol)", required=False)
    fin_habilitacion = forms.DateField(label="Fin de la habilitación", required=False,
                                       widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        datos = super().clean()
        if datos.get("es_habilitacion") and not datos.get("fin_habilitacion"):
            self.add_error("fin_habilitacion", "Una habilitación temporal lleva fecha de fin.")
        return datos


class FormularioVinculo(forms.Form):
    titular = forms.ModelChoiceField(label="Titular", queryset=Titular.objects.order_by("codigo"))
    tipo = forms.ChoiceField(label="Tipo de vínculo", choices=Vinculo.Tipo.choices)


@require_http_methods(["GET"])
@protegida("leer", "cuentas")
def lista(request):
    cuentas = Usuario.objects.order_by("username")
    filas = [[celda(u.username, reverse("cuenta", args=[u.pk])), celda(nombre(u)),
              celda(Rol(u.rol).label if u.rol in Rol.values else "Sin rol"),
              celda(estado="vigente" if u.is_active else "cerrado", estado_texto="Activa" if u.is_active else "Desactivada")]
             for u in cuentas]
    permitidos = verbos(request, "cuentas")
    acciones = [accion("Crear cuenta", reverse("crear_cuenta"), primaria=True)] if "crear" in permitidos else []
    pendientes = PropuestaRol.objects.filter(estado=EstadoPropuesta.PROPUESTA).select_related("usuario", "propuesta_por")
    retiros = Vinculo.objects.filter(retiro_solicitado_en__isnull=False, retirado_en__isnull=True).select_related("usuario", "titular")
    secciones = [
        tabla(["Cuenta", "Rol propuesto", "Habilitación", "Propuesta por"],
              [[celda(p.usuario.username, reverse("cuenta", args=[p.usuario_id])), celda(Rol(p.rol).label),
                celda(f"hasta {p.fin_habilitacion:%d/%m/%Y}" if p.es_habilitacion else "No"), celda(nombre(p.propuesta_por))]
               for p in pendientes],
              titulo="Roles propuestos", nota="Los aprueba Gerencia desde la ficha de la cuenta (C12).",
              vacio_titulo="No hay roles pendientes"),
        tabla(["Cuenta", "Titular", "Tipo", "Pedido"],
              [[celda(v.usuario.username, reverse("cuenta", args=[v.usuario_id])), celda(v.titular.codigo),
                celda(v.get_tipo_display()), celda(v.retiro_solicitado_en.strftime("%d/%m/%Y"))] for v in retiros],
              titulo="Retiros de vínculo pedidos", vacio_titulo="No hay retiros pendientes"),
    ]
    return render(request, "flujos/lista.html", {
        "titulo": "Personal",
        "descripcion": "Las cuentas se crean y se desactivan; nunca se borran (POL-CA-05).",
        "migas": [("Personal", None)],
        "tabla": tabla(["Usuario", "Nombre", "Rol", "Estado"], filas),
        "acciones": acciones,
        "secciones": secciones,
    })


@require_http_methods(["GET"])
@protegida("leer", "cuentas", objeto=h.cuenta)
def ficha(request, cuenta):
    u = get_object_or_404(Usuario.objects.select_related("supervisor"), pk=cuenta)
    permitidos = verbos(request, "cuentas")
    propuestas = u.propuestas_rol.select_related("propuesta_por", "aprobada_por").order_by("-propuesta_en")
    vinculos = Vinculo.objects.filter(usuario=u).select_related("titular").order_by("-declarado_en")
    acciones = []
    if u.pk != request.user.pk:
        if "proponer" in permitidos:
            acciones.append(accion("Proponer rol o habilitación", reverse("proponer_rol", args=[u.pk])))
        if "desactivar" in permitidos and u.is_active:
            acciones.append(accion("Desactivar la cuenta", reverse("desactivar_cuenta", args=[u.pk]), metodo="post", peligro=True))
        if "aprobar" in permitidos:
            acciones += [accion(f"Aprobar rol {Rol(p.rol).label.lower()}", reverse("aprobar_rol", args=[p.pk]), metodo="post", primaria=True)
                         for p in propuestas if p.estado == EstadoPropuesta.PROPUESTA]
            acciones += [accion(f"Aprobar retiro del vínculo con {v.titular.codigo}", reverse("aprobar_retiro", args=[v.pk]), metodo="post")
                         for v in vinculos if v.retiro_solicitado_en and not v.retirado_en]
    return render(request, "flujos/ficha.html", {
        "titulo": nombre(u),
        "descripcion": u.username,
        "migas": [("Personal", reverse("cuentas")), (u.username, None)],
        "estado": "vigente" if u.is_active else "cerrado", "estado_texto": "Activa" if u.is_active else "Desactivada",
        "datos": [("Rol", Rol(u.rol).label if u.rol in Rol.values else "Sin rol"), ("Supervisor", nombre(u.supervisor)),
                  ("Vigente desde", u.vigente_desde.strftime("%d/%m/%Y") if u.vigente_desde else None),
                  ("Vigente hasta", u.vigente_hasta.strftime("%d/%m/%Y") if u.vigente_hasta else None),
                  ("Último ingreso", timezone.localtime(u.last_login).strftime("%d/%m/%Y %H:%M") if u.last_login else None)],
        "acciones": acciones,
        "secciones": [
            tabla(["Rol", "Habilitación", "Propuesta por", "Aprobada por", "Estado"],
                  [[celda(Rol(p.rol).label), celda(f"hasta {p.fin_habilitacion:%d/%m/%Y}" if p.es_habilitacion else "No"),
                    celda(nombre(p.propuesta_por)), celda(nombre(p.aprobada_por)),
                    celda(estado=p.estado, estado_texto=p.get_estado_display())] for p in propuestas],
                  titulo="Roles", vacio_titulo="Sin propuestas de rol"),
            tabla(["Titular", "Tipo", "Declarado", "Estado"],
                  [[celda(v.titular.codigo), celda(v.get_tipo_display()), celda(v.declarado_en.strftime("%d/%m/%Y")),
                    celda("Retirado" if v.retirado_en else ("Retiro pedido" if v.retiro_solicitado_en else "Vigente"))]
                   for v in vinculos],
                  titulo="Vínculos declarados", nota="Con un vínculo vigente, la persona se abstiene de actuar sobre las fincas de ese titular (C17).",
                  vacio_titulo="Sin vínculos declarados"),
        ],
    })


@require_http_methods(["GET", "POST"])
@protegida("crear", "cuentas", objeto=h.cuenta_nueva, formulario=True)
def crear(request):
    form = FormularioCuenta(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        u = Usuario(**datos)
        while True:  # 20 caracteres al azar que pasen los validadores de POL-AU-01
            clave = secrets.token_urlsafe(15)
            try:
                validate_password(clave, u)
                break
            except forms.ValidationError:
                continue

        def crear_():
            u.set_password(clave)
            u.save()
            anotar(request, "crear", "cuentas", u.pk, despues={"usuario": u.username})
            return u

        u, hecho = escribir(request, "crear", "cuentas", "", crear_)
        if hecho:
            # La contraseña inicial se muestra una sola vez, en esta respuesta: no va a un mensaje
            # (se guardaría en la cookie o en la sesión) ni a la bitácora.
            return render(request, "flujos/ficha.html", {
                "titulo": f"Cuenta {u.username} creada",
                "descripcion": "Entréguele esta contraseña inicial por un canal aparte; no se vuelve a mostrar. Al entrar "
                               "tendrá que activar su segundo factor. Su rol lo propone Administración y lo aprueba Gerencia.",
                "migas": [("Personal", reverse("cuentas")), (u.username, None)],
                "datos": [("Usuario", u.username), ("Contraseña inicial", clave)],
                "acciones": [accion("Proponer su rol", reverse("proponer_rol", args=[u.pk]), primaria=True)],
            })
    return render(request, "flujos/formulario.html", {
        "titulo": "Crear cuenta",
        "descripcion": "La cuenta nace sin rol: se le propone uno y lo aprueba Gerencia (C12).",
        "migas": [("Personal", reverse("cuentas")), ("Crear", None)],
        "form": form, "boton": "Crear", "cancelar": reverse("cuentas"),
    })


@require_POST
@protegida("desactivar", "cuentas", objeto=h.cuenta)
def desactivar(request, cuenta):
    u = get_object_or_404(Usuario, pk=cuenta)

    def desactivar_():
        u.is_active = False
        u.save(update_fields=["is_active"])
        anotar(request, "desactivar", "cuentas", u.pk, antes={"activa": True}, despues={"activa": False})

    if escribir(request, "desactivar", "cuentas", u.pk, desactivar_)[1]:
        return volver(request, reverse("cuenta", args=[u.pk]), "Cuenta desactivada; sus sesiones se cerraron.")
    return redirect("cuenta", u.pk)


@require_http_methods(["GET", "POST"])
@protegida("proponer", "cuentas", objeto=h.cuenta)
def proponer_rol(request, cuenta):
    u = get_object_or_404(Usuario, pk=cuenta)
    form = FormularioRol(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data

        def proponer_():
            p = PropuestaRol.objects.create(usuario=u, rol=datos["rol"], es_habilitacion=datos["es_habilitacion"],
                                            fin_habilitacion=datos["fin_habilitacion"] if datos["es_habilitacion"] else None,
                                            propuesta_por=request.user)
            anotar(request, "proponer", "cuentas", u.pk, despues={"rol": p.rol, "habilitacion": p.es_habilitacion})

        if escribir(request, "proponer", "cuentas", u.pk, proponer_)[1]:
            return volver(request, reverse("cuenta", args=[u.pk]), "Rol propuesto: espera la aprobación de Gerencia.")
    return render(request, "flujos/formulario.html", {
        "titulo": f"Proponer rol para {u.username}",
        "migas": [("Personal", reverse("cuentas")), (u.username, reverse("cuenta", args=[u.pk])), ("Rol", None)],
        "datos": [("Rol actual", Rol(u.rol).label if u.rol in Rol.values else "Sin rol")],
        "form": form, "boton": "Proponer", "cancelar": reverse("cuenta", args=[u.pk]),
    })


@require_POST
@protegida("aprobar", "cuentas", objeto=h.propuesta_rol)
def aprobar_rol(request, propuesta):
    p = get_object_or_404(PropuestaRol.objects.select_related("usuario"), pk=propuesta)

    def aprobar_():
        PropuestaRol.objects.filter(pk=p.pk).update(estado=EstadoPropuesta.APROBADA, aprobada_por=request.user,
                                                    aprobada_en=timezone.now())
        if not p.es_habilitacion:
            usuario = p.usuario
            antes = usuario.rol
            usuario.rol = p.rol
            usuario.save(update_fields=["rol"])
            anotar(request, "aprobar", "cuentas", usuario.pk, antes={"rol": antes}, despues={"rol": p.rol})
        else:
            anotar(request, "aprobar", "cuentas", p.usuario_id, despues={"habilitacion": p.rol, "hasta": str(p.fin_habilitacion)})

    if escribir(request, "aprobar", "cuentas", p.usuario_id, aprobar_)[1]:
        return volver(request, reverse("cuenta", args=[p.usuario_id]), "Rol aprobado; las sesiones de la persona se cerraron.")
    return redirect("cuenta", p.usuario_id)


@require_POST
@protegida("aprobar", "cuentas", objeto=h.retiro_vinculo)
def aprobar_retiro(request, vinculo):
    v = get_object_or_404(Vinculo, pk=vinculo)

    def aprobar_():
        Vinculo.objects.filter(pk=v.pk).update(retirado_en=timezone.now(), retiro_aprobado_por=request.user)
        anotar(request, "aprobar", "cuentas", v.usuario_id, despues={"vinculo_retirado": str(v.titular_id)})

    if escribir(request, "aprobar", "cuentas", v.usuario_id, aprobar_)[1]:
        return volver(request, reverse("cuenta", args=[v.usuario_id]), "Retiro del vínculo aprobado.")
    return redirect("cuenta", v.usuario_id)


@require_http_methods(["GET", "POST"])
@protegida("modificar", "cuentas", objeto=h.cuenta_propia)
def mis_vinculos(request):
    """C13: cada quien declara sus vínculos con titulares (POL-CA-14). Declarar es inmediato;
    retirar uno se pide aquí y lo aprueba Gerencia."""
    u = request.user
    form = FormularioVinculo(request.POST if request.POST.get("operacion") == "declarar" else None)
    if request.method == "POST":
        operacion = request.POST.get("operacion")
        if operacion == "declarar" and form.is_valid():
            def declarar():
                Vinculo.objects.create(usuario=u, titular=form.cleaned_data["titular"], tipo=form.cleaned_data["tipo"])
                Declaracion.objects.create(usuario=u, sin_vinculos=False)
                anotar(request, "modificar", "cuentas", u.pk, despues={"vinculo": form.cleaned_data["titular"].codigo})

            if escribir(request, "modificar", "cuentas", u.pk, declarar)[1]:
                return volver(request, reverse("mis_vinculos"), "Vínculo declarado: se abstendrá de actuar sobre las fincas de ese titular.")
        elif operacion == "sin_vinculos":
            def sin():
                Declaracion.objects.create(usuario=u, sin_vinculos=True)
                anotar(request, "modificar", "cuentas", u.pk, despues={"declaracion": "sin vínculos"})

            if escribir(request, "modificar", "cuentas", u.pk, sin)[1]:
                return volver(request, reverse("mis_vinculos"), "Declaración registrada.")
        elif operacion == "retiro":
            vinculo = Vinculo.objects.filter(pk=request.POST.get("vinculo"), usuario=u, retirado_en__isnull=True).first()
            if vinculo:
                def retiro():
                    Vinculo.objects.filter(pk=vinculo.pk).update(retiro_solicitado_en=timezone.now())
                    anotar(request, "modificar", "cuentas", u.pk, despues={"retiro_pedido": vinculo.titular.codigo})

                if escribir(request, "modificar", "cuentas", u.pk, retiro)[1]:
                    return volver(request, reverse("mis_vinculos"), "Retiro pedido: lo aprueba Gerencia.")
    vinculos = Vinculo.objects.filter(usuario=u).select_related("titular").order_by("-declarado_en")
    ultima = Declaracion.objects.filter(usuario=u).order_by("-fecha").first()
    return render(request, "flujos/vinculos.html", {
        "titulo": "Mis vínculos con titulares",
        "migas": [("Mis vínculos", None)],
        "form": form,
        "vinculos": vinculos,
        "ultima": ultima,
    })
