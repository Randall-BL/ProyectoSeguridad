from datetime import datetime, timedelta

from allauth.mfa.models import Authenticator
from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from cuentas.models import Rol
from cuentas.roles import QUE_HACE, habilitacion_vigente
from cuentas.sesiones import INICIO


def _estado_de_la_base():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('server_version_num')::int / 10000, postgis_lib_version()")
        return cursor.fetchone()


def _saludo(ahora):
    hora = timezone.localtime(ahora).hour
    if hora < 12:
        return "Buenos días"
    if hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def _sesion(request):
    """Lo que la persona puede ver de su propia sesión: cuándo empezó, cuándo vence y su segundo
    factor."""
    usuario = request.user
    inicio = request.session.get(INICIO)
    inicio = datetime.fromtimestamp(inicio, tz=timezone.get_current_timezone()) if inicio else None
    codigos = Authenticator.objects.filter(user=usuario, type=Authenticator.Type.RECOVERY_CODES).first()
    return {
        "saludo": _saludo(timezone.now()),
        "que_hace": QUE_HACE.get(request.rol_activo, ""),
        "inicio_sesion": inicio,
        "fin_sesion": inicio + timedelta(seconds=settings.SESION_MAXIMA) if inicio else None,
        "inactividad_min": settings.SESSION_COOKIE_AGE // 60,
        "totp_activo": Authenticator.objects.filter(user=usuario, type=Authenticator.Type.TOTP).exists(),
        "codigos_sin_usar": len(codigos.wrap().get_unused_codes()) if codigos else 0,
        "con_habilitacion": usuario.rol == Rol.VER and habilitacion_vigente(usuario),
    }


@require_GET
def inicio(request):
    """Portada sin sesión; con sesión, el inicio de la persona según su rol activo."""
    postgres, postgis = _estado_de_la_base()
    contexto = {"postgres": postgres, "postgis": postgis}
    if not request.user.is_authenticated:
        return render(request, "nucleo/portada.html", contexto)
    contexto.update(_sesion(request))
    return render(request, "nucleo/inicio.html", contexto)


@require_GET
def salud(request):
    """Sonda de arranque de Cloud Run: responde sin tocar la base."""
    return HttpResponse("ok", content_type="text/plain")
