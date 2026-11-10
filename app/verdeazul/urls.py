from allauth.account import urls as rutas_de_cuenta
from django.urls import include, path

from cuentas import views as cuentas
from nucleo import views

# De allauth solo se publican estas rutas de cuenta. Quedan fuera el registro abierto (C12), la
# recuperación por correo y por código (POL-AU-10: la hacen ADM y GER, nunca la persona sola) y la
# gestión de correos, que no se usa para entrar.
RUTAS_DE_CUENTA = {
    "account_login",
    "account_logout",
    "account_inactive",
    "account_reauthenticate",
    "account_change_password",
}

urlpatterns = [
    path("", views.hola, name="hola"),
    path("salud", views.salud, name="salud"),
    path(
        "cuentas/",
        include([ruta for ruta in rutas_de_cuenta.urlpatterns if getattr(ruta, "name", None) in RUTAS_DE_CUENTA]),
    ),
    path("cuentas/2fa/", include("allauth.mfa.urls")),
    path("cuentas/rol/", cuentas.elegir_rol, name="elegir_rol"),
]
