"""Sesiones de servidor (POL-AU-08, tarea 3.5).

La sesión vive en PostgreSQL y no en la cookie: el navegador solo guarda un identificador al azar,
que cambia al iniciar sesión. Vence a los 30 minutos sin actividad, porque la fecha de vencimiento
se corre en cada petición, y a las 12 horas de iniciada aunque haya actividad. Cada fila guarda de
quién es la sesión, para poder cerrarlas todas a la vez (tarea 3.6)."""

import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import SESSION_KEY, logout
from django.contrib.sessions.backends.db import SessionStore as SesionEnBase
from django.shortcuts import redirect

# Instante en que se inició la sesión, en segundos desde la época.
INICIO = "va_inicio"


class SessionStore(SesionEnBase):
    @classmethod
    def get_model_class(cls):
        from cuentas.models import Sesion

        return Sesion

    def create_model_instance(self, data):
        fila = super().create_model_instance(data)
        fila.usuario_id = data.get(SESSION_KEY)
        return fila


def marcar_inicio(request):
    request.session[INICIO] = int(time.time())


class LimitarSesion:
    """Cierra la sesión que pasó las 12 horas desde que se inició, aunque haya tenido actividad. La
    inactividad de 30 minutos no necesita esto: la base no devuelve una sesión vencida."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            inicio = request.session.get(INICIO)
            if inicio is None or time.time() - inicio > settings.SESION_MAXIMA:
                logout(request)
                messages.info(request, "La sesión llegó a su máximo de 12 horas. Inicie sesión de nuevo.")
                return redirect(settings.LOGIN_URL)
        return self.get_response(request)
