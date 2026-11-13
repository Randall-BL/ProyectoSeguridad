"""Lo que todas las plantillas necesitan: versión, rol activo y menú principal."""

from django.conf import settings
from django.urls import reverse

from cuentas.models import Rol

# Opciones del menú principal: texto, nombre de la ruta y roles que la ven (vacío: todos). Las
# pantallas de la fase 5 se agregan aquí. Esconder una opción es solo comodidad: lo que protege
# es la decisión en el servidor (tarea 4.10).
MENU = [
    ("Inicio", "inicio", ()),
    ("Fincas", "fincas", ("TEC", "VER", "SUP", "GER", "ADM", "AUD", "DUE")),
    ("Titulares", "titulares", ("TEC", "GER", "ADM", "AUD", "DUE")),
    ("Períodos", "periodos", ()),
    ("Asignaciones", "asignaciones", ("TEC", "SUP", "GER", "AUD", "DUE")),
    ("Mediciones", "mediciones", ("TEC", "VER", "SUP", "GER", "AUD", "DUE")),
    ("Enmiendas", "enmiendas", ("TEC", "VER", "SUP", "GER", "AUD", "DUE")),
    ("Certificados", "certificados", ("VER", "GER", "AUD", "DUE")),
]


def verdeazul(request):
    rol = getattr(request, "rol_activo", "")
    ruta = request.resolver_match.url_name if request.resolver_match else ""
    menu = [
        {"texto": texto, "url": reverse(nombre), "actual": nombre == ruta}
        for texto, nombre, roles in MENU
        if rol and (not roles or rol in roles)
    ]
    return {
        "version_app": settings.VERSION_APP,
        "commit_app": settings.COMMIT_APP[:7],
        "rol_activo": rol,
        "rol_activo_nombre": Rol(rol).label if rol in Rol.values else "",
        "menu_principal": menu,
    }
