from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def hola(request):
    """Página de la versión v0.1.0: prueba que la cadena de conexión llega desde Secret Manager
    y que la base responde. Se reemplaza por el inicio de sesión en el sprint 2."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('server_version_num')::int / 10000, postgis_lib_version()")
        postgres, postgis = cursor.fetchone()
    return render(
        request,
        "nucleo/hola.html",
        {
            "version": settings.VERSION_APP,
            "commit": settings.COMMIT_APP,
            "postgres": postgres,
            "postgis": postgis,
        },
    )


@require_GET
def salud(request):
    """Sonda de arranque de Cloud Run: responde sin tocar la base."""
    return HttpResponse("ok", content_type="text/plain")
