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


class Testigo(models.Model):
    """Testigo externo de la bitácora (tarea 7.5, decisión 0.6). Cada día el trabajo programado pide
    a una autoridad de sellado de tiempo pública (RFC 3161) un sello sobre la huella del último
    registro y lo guarda aquí. La cadena por sí sola no detecta que alguien con acceso a la base
    quite los últimos registros; el sello, firmado por un tercero, prueba que esa huella ya existía
    en esa fecha. Se comprueba sin Verdeazul con openssl ts -verify. Solo se agregan filas."""

    id = models.BigAutoField(primary_key=True)
    instante = models.DateTimeField()
    registro = models.BigIntegerField(help_text="Número del último registro de la bitácora sellado.")
    huella = models.CharField(max_length=64)
    tsa = models.URLField()
    sello = models.TextField(help_text="Respuesta de la TSA (TimeStampResp, DER) en base64.")

    class Meta:
        ordering = ["-id"]
