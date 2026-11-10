"""Cliente del motor de decisión (OPA), con fallo cerrado (K-3, tarea 4.6).

Si el motor no contesta dentro del límite, contesta con un error o con algo que no se entiende, la
pregunta termina en MotorSinRespuesta y la petición se frena: no hay decisión por omisión que
conceda, no se guardan decisiones anteriores y no hay camino alterno «mientras vuelve»."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings

RESULTADOS = {
    "conceder",
    "pedir_segundo_factor",
    "pedir_segundo_factor_y_motivo",
    "restringir",
    "denegar",
}

# Sin proxies: el motor está en la misma instancia, y una variable de entorno no debe poder desviar
# las preguntas a otro lado.
_abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_TAMANO_MAXIMO = 1_000_000


class MotorSinRespuesta(Exception):
    """El motor no respondió a tiempo, falló o respondió algo inválido. Se deniega (K-3)."""


@dataclass(frozen=True)
class Decision:
    resultado: str
    regla: str
    avisar: bool = False

    @property
    def concedida(self):
        return self.resultado == "conceder"


def _pedir(ruta, cuerpo=None):
    url = settings.OPA_URL.rstrip("/") + ruta
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(
        url,
        data=datos,
        method="POST" if datos is not None else "GET",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with _abridor.open(peticion, timeout=settings.OPA_LIMITE) as respuesta:
            if respuesta.status != 200:
                raise MotorSinRespuesta(f"HTTP {respuesta.status}")
            return json.loads(respuesta.read(_TAMANO_MAXIMO))
    except MotorSinRespuesta:
        raise
    except (OSError, ValueError, urllib.error.URLError) as error:
        # OSError cubre la conexión rechazada y el tiempo agotado; ValueError, el JSON inválido.
        raise MotorSinRespuesta(type(error).__name__) from error


def preguntar(entrada):
    """Pregunta una decisión. Devuelve Decision o lanza MotorSinRespuesta."""
    respuesta = _pedir("/v1/data/verdeazul/decision", {"input": entrada})
    resultado = respuesta.get("result") if isinstance(respuesta, dict) else None
    if (
        not isinstance(resultado, dict)
        or resultado.get("resultado") not in RESULTADOS
        or not isinstance(resultado.get("regla"), str)
        or not isinstance(resultado.get("avisar"), bool)
    ):
        raise MotorSinRespuesta("respuesta inválida")
    return Decision(resultado["resultado"], resultado["regla"], resultado["avisar"])


def permisos_del_rol(rol):
    """Las celdas de la matriz de un rol, para que la interfaz muestre lo que puede hacer (4.10).
    Es solo comodidad: lo que protege es la decisión de cada petición."""
    respuesta = _pedir(f"/v1/data/matriz/celdas/{rol}")
    celdas = respuesta.get("result") if isinstance(respuesta, dict) else None
    if not isinstance(celdas, dict):
        raise MotorSinRespuesta("respuesta inválida")
    return celdas


def objetos():
    respuesta = _pedir("/v1/data/matriz/objetos")
    nombres = respuesta.get("result") if isinstance(respuesta, dict) else None
    if not isinstance(nombres, dict):
        raise MotorSinRespuesta("respuesta inválida")
    return nombres
