from django.apps import AppConfig


class CuentasConfig(AppConfig):
    name = "cuentas"
    verbose_name = "Cuentas y roles"

    def ready(self):
        from cuentas import revocacion, senales  # noqa: F401  (conectan los receptores)
