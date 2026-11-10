from django.apps import AppConfig


class CuentasConfig(AppConfig):
    name = "cuentas"
    verbose_name = "Cuentas y roles"

    def ready(self):
        from cuentas import senales  # noqa: F401  (conecta los receptores)
