"""Reautenticación en las decisiones (POL-AU-06, leyenda de la matriz).

Aprobar o devolver una medición, revisar o autorizar una enmienda, abrir o cerrar un período,
aprobar altas o roles, resolver una alerta y exportar evidencia exigen el segundo factor en los
cinco minutos previos. La contraseña sola no cuenta: liga la decisión a la persona presente, no a
una sesión que quedó abierta en un equipo."""

import time
from functools import wraps

from allauth.account.authentication import get_authentication_records
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode


def segundo_factor_reciente(request):
    """La persona usó su segundo factor (al entrar o al reautenticarse) hace menos de cinco
    minutos, en esta misma sesión."""
    ahora = time.time()
    ventana = settings.ACCOUNT_REAUTHENTICATION_TIMEOUT
    return any(
        registro.get("method") == "mfa" and ahora - registro.get("at", 0) < ventana
        for registro in get_authentication_records(request, request.user)
    )


def requiere_segundo_factor(vista):
    """Decorador para toda vista que toma una decisión. Sin segundo factor reciente, manda a
    pedir el código y vuelve a la misma página. Si la decisión venía en un POST, no se ejecuta:
    la persona la confirma otra vez después de reautenticarse."""

    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if segundo_factor_reciente(request):
            return vista(request, *args, **kwargs)
        destino = request.get_full_path() if request.method == "GET" else request.path
        return redirect(f"{reverse('mfa_reauthenticate')}?{urlencode({'next': destino})}")

    return envoltura
