"""La bitácora (5.12): la leen solo GER y AUD (en su ventana), y cada lectura queda registrada en la
propia bitácora (POL-BT-05). La pantalla también comprueba la cadena de huellas."""

from django.core.paginator import Paginator
from django.db import connection
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from autorizacion.proteccion import protegida
from bitacora.models import Registro
from cuentas.models import Usuario
from flujos.comun import accion, anotar, celda, tabla, verbos

POR_PAGINA = 50


def _cadena():
    """bitacora_verificar() devuelve el número del primer registro roto, o nada si la cadena está bien."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT bitacora_verificar()")
        return cursor.fetchone()[0]


@require_http_methods(["GET"])
@protegida("leer", "bitacora")
def lista(request):
    anotar(request, "leer", "bitacora", "", despues={"pagina": request.GET.get("pagina", "1")})
    pagina = Paginator(Registro.objects.order_by("-id"), POR_PAGINA).get_page(request.GET.get("pagina"))
    usuarios = dict(Usuario.objects.filter(pk__in={r.usuario_id for r in pagina if r.usuario_id})
                    .values_list("pk", "username"))
    filas = [[celda(str(r.id)), celda(timezone.localtime(r.instante).strftime("%d/%m/%Y %H:%M:%S")),
              celda(usuarios.get(r.usuario_id, "sistema")), celda(r.rol), celda(r.accion),
              celda(f"{r.objeto_tipo} {r.objeto_id[:8]}".strip()),
              celda(estado={"concedido": "aprobado", "denegado": "rechazado", "restringido": "restriccion"}.get(r.resultado, r.resultado),
                    estado_texto=r.resultado),
              celda(r.regla)] for r in pagina]
    roto = _cadena()
    acciones = [accion("Exportar", reverse("exportar_bitacora"))] if "exportar" in verbos(request, "bitacora") else []
    pie = f"Página {pagina.number} de {pagina.paginator.num_pages}"
    return render(request, "flujos/lista.html", {
        "titulo": "Bitácora",
        "descripcion": ("La cadena de huellas está íntegra." if roto is None else
                        f"La cadena está rota desde el registro {roto}: alguien alteró la bitácora.")
                       + " Esta consulta también quedó registrada.",
        "migas": [("Bitácora", None)],
        "tabla": tabla(["N.º", "Instante", "Usuario", "Rol", "Acción", "Objeto", "Resultado", "Regla"], filas, pie=pie),
        "acciones": acciones + ([accion("Más antiguos", f"?pagina={pagina.next_page_number()}")] if pagina.has_next() else []),
    })
