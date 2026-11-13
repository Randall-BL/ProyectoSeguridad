"""Escritura de la bitácora desde la aplicación. Se llama dentro de la misma transacción que la
acción: si el registro no se puede escribir, la transacción entera se deshace y la acción no
ocurre (POL-BT-06)."""

import hashlib
import json

from django.db import connection


def huella(valor):
    """SHA-256 de un valor en JSON canónico. La bitácora guarda la huella del valor anterior y del
    nuevo, no el valor: así no copia datos personales."""
    if valor is None:
        return ""
    texto = json.dumps(valor, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def anexar(
    *,
    accion,
    resultado,
    usuario=None,
    rol="",
    objeto_tipo="",
    objeto_id="",
    objeto_version="",
    regla="",
    origen="",
    sesion="",
    antes=None,
    despues=None,
):
    """Agrega un registro y devuelve su número."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT bitacora_anexar(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                str(usuario.pk) if usuario is not None else None,
                rol,
                accion,
                objeto_tipo,
                str(objeto_id),
                str(objeto_version),
                resultado,
                regla,
                origen,
                hashlib.sha256(sesion.encode()).hexdigest() if sesion else "",
                huella(antes),
                huella(despues),
            ],
        )
        return cursor.fetchone()[0]


def verificar_cadena():
    """Recalcula la cadena completa. Devuelve None si está íntegra o el número del primer
    registro que no coincide."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT bitacora_verificar()")
        return cursor.fetchone()[0]


def origen_de(request):
    """Dirección desde la que llegó la petición. En Cloud Run el frente de Google agrega al final de
    X-Forwarded-For la dirección que vio; lo que venga antes lo pudo escribir el cliente."""
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if reenviada:
        return reenviada.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")
