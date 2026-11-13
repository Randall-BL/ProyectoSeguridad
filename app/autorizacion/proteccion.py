"""El punto de cumplimiento en cada ruta (tarea 4.7).

Toda vista del negocio lleva @protegida(accion, tipo, objeto=…): antes de ejecutarla se arman los
hechos desde la base, se pregunta al motor y se hace lo que responde. La vista solo corre si la
respuesta es «conceder»; cualquier otra cosa, o el motor sin responder, la frena. Una prueba
recorre todas las rutas y falla si alguna no lo declara (criterio de aceptación 2)."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

from autorizacion import hechos, historial, motor, respuestas

# Lecturas denegadas por alcance: se responde «no encontrado», igual que si no existiera, para no
# revelar qué existe fuera del alcance de la persona (T-08).
ALCANCE = {"C1", "C5"}


def _a_reautenticar(request):
    destino = request.get_full_path() if request.method == "GET" else request.path
    return redirect(f"{reverse('mfa_reauthenticate')}?{urlencode({'next': destino})}")


def _formulario_vacio(request, accion, tipo, vista, args, kwargs):
    """Mostrar el formulario de una acción que todavía no tiene objeto (crear una asignación,
    proponer una finca): basta con que el rol tenga ese verbo en su celda de la matriz. No cambia
    nada; la decisión con los hechos se toma al enviarlo."""
    try:
        celdas = motor.permisos_del_rol(request.rol_activo)
    except motor.MotorSinRespuesta as error:
        return respuestas.sin_motor(request, accion, {"tipo": tipo}, str(error))
    if any(permiso["verbo"] == accion for permiso in celdas.get(tipo, [])):
        return vista(request, *args, **kwargs)
    decision = motor.Decision("denegar", "matriz", False)
    return respuestas.denegada(request, accion, {"tipo": tipo}, decision)


def protegida(accion, tipo, *, objeto=None, cambio=None, formulario=False):
    """accion: verbo de la matriz. tipo: objeto de la matriz. objeto(request, **kwargs): los hechos
    del objeto desde la base, o None si no existe; sin objeto, la ruta es una lista. cambio(request,
    hechos): lo que se quiere escribir, para las reglas que lo revisan (C2, C14, C19).
    formulario=True: el GET muestra un formulario vacío y solo exige el verbo en la celda del rol;
    el POST se decide con los hechos completos."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if formulario and request.method == "GET":
                return _formulario_vacio(request, accion, tipo, vista, args, kwargs)
            hechos_objeto = objeto(request, **kwargs) if objeto else {"coleccion": True}
            if hechos_objeto is None:
                raise Http404
            hechos_objeto = {**hechos_objeto, "tipo": tipo}
            datos_cambio = cambio(request, hechos_objeto) if cambio and request.method == "POST" else None
            motivo = (request.POST.get("motivo") or request.GET.get("motivo") or "").strip()
            try:
                decision = motor.preguntar(
                    hechos.entrada(request, accion, hechos_objeto, datos_cambio, motivo)
                )
            except motor.MotorSinRespuesta as error:
                return respuestas.sin_motor(request, accion, hechos_objeto, str(error))
            if accion == "leer":
                historial.anotar_lectura(request, hechos_objeto, decision)
            # Respuesta graduada (4.9): conceder y avisar, o restringir, dejan una alerta.
            if decision.avisar or decision.resultado == "restringir":
                historial.alertar(request, accion, hechos_objeto, decision, motivo)

            if decision.concedida:
                request.decision = decision
                return vista(request, *args, **kwargs)
            if decision.resultado == "pedir_segundo_factor":
                return _a_reautenticar(request)
            if decision.resultado == "pedir_segundo_factor_y_motivo":
                return respuestas.pedir_motivo(request, accion, hechos_objeto, decision)
            if accion == "leer" and decision.regla in ALCANCE and objeto:
                respuestas.anotar_denegacion(request, accion, hechos_objeto, decision)
                raise Http404
            return respuestas.denegada(request, accion, hechos_objeto, decision)

        envoltura.protegida = (accion, tipo)
        return envoltura

    return decorador
