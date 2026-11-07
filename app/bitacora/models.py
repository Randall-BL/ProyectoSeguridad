from django.db import models


class Registro(models.Model):
    """Lectura de la bitácora. La tabla la crea y la protege la migración 0001: solo se escribe
    con la función bitacora_anexar(), que encadena cada registro con la huella del anterior, y un
    disparador rechaza UPDATE, DELETE y TRUNCATE, también al dueño (POL-BT-03)."""

    id = models.BigIntegerField(primary_key=True)
    instante = models.DateTimeField()
    usuario_id = models.UUIDField(null=True)
    rol = models.TextField()
    accion = models.TextField()
    objeto_tipo = models.TextField()
    objeto_id = models.TextField()
    objeto_version = models.TextField()
    resultado = models.TextField()
    regla = models.TextField()
    origen = models.TextField()
    sesion = models.TextField()
    huella_antes = models.TextField()
    huella_despues = models.TextField()
    huella_previa = models.TextField()
    huella = models.TextField()

    class Meta:
        managed = False
        db_table = "bitacora_registro"
        ordering = ["id"]
