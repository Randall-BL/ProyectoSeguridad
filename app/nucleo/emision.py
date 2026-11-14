"""Cliente del servicio de emisión (fase 6). La aplicación no firma ni tiene la clave: le pide al
servicio privado verdeazul-emision que emita, reemita o selle. Se identifica con un token de
identidad de sa-app que da el servidor de metadatos de Cloud Run, con el servicio como audiencia;
Cloud Run solo deja pasar ese token si sa-app tiene run.invoker sobre el servicio.

Sin EMISION_URL (en local o en las pruebas) no hay emisión: llamar() lanza SinEmision."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.db import transaction

registro = logging.getLogger("verdeazul.emision")

METADATOS = ("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
             "?audience={}")


class SinEmision(Exception):
    """El servicio de emisión no respondió o no está configurado."""


def _token(audiencia):
    peticion = urllib.request.Request(METADATOS.format(urllib.parse.quote(audiencia, safe="")),
                                      headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(peticion, timeout=3) as respuesta:  # noqa: S310 - dirección fija
        return respuesta.read().decode()


def llamar(ruta, datos, timeout=20):
    """POST al servicio. Devuelve (código HTTP, cuerpo JSON). Un 4xx no es un fallo del servicio:
    es su decisión (por ejemplo, C4) y se devuelve tal cual."""
    base = (settings.EMISION_URL or "").rstrip("/")
    if not base:
        raise SinEmision("No hay servicio de emisión configurado.")
    cabeceras = {"Content-Type": "application/json"}
    if base.startswith("https://"):
        try:
            cabeceras["Authorization"] = f"Bearer {_token(base)}"
        except OSError as error:
            raise SinEmision(f"No se obtuvo el token de identidad: {error}") from error
    peticion = urllib.request.Request(base + ruta, data=json.dumps(datos).encode(), headers=cabeceras, method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:  # noqa: S310 - URL de la configuración
            return respuesta.status, json.loads(respuesta.read() or b"{}")
    except urllib.error.HTTPError as error:
        if error.code >= 500:
            raise SinEmision(f"El servicio respondió {error.code}.") from error
        try:
            return error.code, json.loads(error.read() or b"{}")
        except ValueError:
            return error.code, {}
    except (OSError, ValueError) as error:
        raise SinEmision(str(error)) from error


def despues_de_confirmar(ruta, datos):
    """Pide algo al servicio cuando la transacción de la petición ya se confirmó: el servicio usa
    su propia conexión y tiene que ver la medición aprobada o la enmienda autorizada. Si falla, la
    acción de la persona ya quedó hecha; el trabajo diario (/emitir-pendientes) lo recupera."""

    def pedir():
        try:
            codigo, cuerpo = llamar(ruta, datos)
            registro.info("Emisión %s %s: %s %s", ruta, datos, codigo, cuerpo)
        except SinEmision as error:
            registro.warning("Emisión %s %s pendiente: %s", ruta, datos, error)

    transaction.on_commit(pedir)


def sellar(huella, objeto):
    """6.10: el sello de un paquete del auditor. Sin sello no se entrega (C18)."""
    codigo, cuerpo = llamar("/sellar", {"huella": huella, "objeto": objeto})
    if codigo != 200 or not isinstance(cuerpo.get("sello"), dict):
        raise SinEmision(f"El servicio no selló el paquete ({codigo}).")
    return cuerpo["sello"]
