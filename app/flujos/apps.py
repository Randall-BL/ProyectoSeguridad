from django.apps import AppConfig


class FlujosConfig(AppConfig):
    """Las pantallas de los flujos del negocio (fase 5). Cada vista lleva @protegida."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "flujos"
