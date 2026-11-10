"""Quién pide, para la seguridad por fila (tarea 2.5, del lado de la aplicación).

Cada petición corre en una transacción que empieza diciéndole a la base quién pide y con qué rol
activo (set_config local de app.usuario y app.rol). Las políticas de la base filtran con eso: un
técnico solo ve las filas de sus fincas (C1), un dueño las de su titular (C5), y sin rol no se ve
nada. Es local a la transacción: aunque el pooler de Neon reutilice la conexión para otra petición,
el valor no pasa de una a otra. El id sale de la sesión del servidor, nunca de la petición (K-2)."""

from django.db import connection, transaction


class ContextoDeBase:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = str(request.user.pk) if request.user.is_authenticated else ""
        rol = getattr(request, "rol_activo", "") or ""
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.usuario', %s, true), set_config('app.rol', %s, true)",
                    [usuario, rol],
                )
            respuesta = self.get_response(request)
            # Django convierte los errores de la vista en una respuesta 500 antes de llegar aquí:
            # lo que alcanzó a escribir esa petición no se guarda. La excepción es el 503 del motor
            # caído (K-3): la vista no corrió, y su denegación en la bitácora tiene que quedar.
            if respuesta.status_code >= 500 and not getattr(respuesta, "conservar_bitacora", False):
                transaction.set_rollback(True)
            return respuesta
