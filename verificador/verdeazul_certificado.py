"""Formato y verificación de un certificado de Verdeazul Carbono (decisión 0.3, tarea 6.4).

Un certificado es un archivo JSON con dos partes:

    {"contenido": {...}, "firma": "<Ed25519 en base64>"}

La firma es sobre el contenido en JSON canónico: claves ordenadas, sin espacios, UTF-8. El
contenido lleva la clave pública con la que se firmó (clave_publica) y su huella (clave_id), pero
eso solo no basta: cualquiera puede firmar un certificado falso con su propia clave e incrustarla.
Por eso la verificación compara la clave incrustada con la clave publicada de Verdeazul (6.6).

Este mismo archivo lo usan el servicio de emisión (firmar), el servicio público (verificar) y el
programa de consola que verifica sin conexión (6.8). Solo depende de la biblioteca cryptography.
"""

import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ALGORITMO = "Ed25519"
CAMPOS = (
    "codigo", "finca", "parcela", "periodo", "toneladas_co2", "emitido_en", "aprobado_por", "reemplaza",
    "algoritmo", "clave_id", "clave_publica",
)


def canonico(datos):
    """El JSON exacto que se firma: claves ordenadas, sin espacios y en UTF-8."""
    return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _b64(datos):
    return base64.b64encode(datos).decode("ascii")


def clave_privada_de(texto_b64):
    """La clave privada viene de Secret Manager como los 32 bytes de la semilla en base64."""
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(texto_b64))


def bytes_publicos(clave_publica):
    return clave_publica.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def huella(clave_publica):
    """Identificador de la clave: SHA-256 de sus 32 bytes, en hexadecimal."""
    return hashlib.sha256(bytes_publicos(clave_publica)).hexdigest()


def pem_publico(clave_publica):
    return clave_publica.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def clave_publica_de_pem(texto):
    clave = serialization.load_pem_public_key(texto.encode() if isinstance(texto, str) else texto)
    if not isinstance(clave, Ed25519PublicKey):
        raise ValueError("La clave publicada no es Ed25519.")
    return clave


def firmar(contenido, clave_privada):
    """Completa el contenido con el algoritmo y la clave pública, y devuelve el certificado."""
    publica = clave_privada.public_key()
    contenido = {**contenido, "algoritmo": ALGORITMO, "clave_id": huella(publica),
                 "clave_publica": _b64(bytes_publicos(publica))}
    return {"contenido": contenido, "firma": _b64(clave_privada.sign(canonico(contenido)))}


def semilla_b64(clave_privada):
    """Los 32 bytes de la semilla en base64: la forma en que la clave viaja a Secret Manager."""
    return _b64(clave_privada.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))


def huella_de(datos):
    """SHA-256 del JSON canónico de cualquier objeto, en hexadecimal."""
    return hashlib.sha256(canonico(datos)).hexdigest()


def sellar(huella_hex, clave_privada):
    """Sello de un paquete del auditor (6.10, C18): se firma solo la huella del paquete, así el
    servicio de emisión no necesita recibir el paquete entero."""
    publica = clave_privada.public_key()
    return {"algoritmo": ALGORITMO, "clave_id": huella(publica), "clave_publica": _b64(bytes_publicos(publica)),
            "huella_sha256": huella_hex, "firma": _b64(clave_privada.sign(canonico({"huella_sha256": huella_hex})))}


def verificar_sello(datos, sello, clave_verdeazul):
    """Revisa que el sello corresponda a estos datos (sin el sello) y que sea de Verdeazul."""
    resultado = {"formato": False, "firma_valida": False, "clave_de_verdeazul": False, "valido": False, "motivo": ""}
    if not isinstance(sello, dict) or not all(isinstance(sello.get(c), str) for c in ("huella_sha256", "firma", "clave_publica")):
        resultado["motivo"] = "El paquete no trae sello de Verdeazul."
        return resultado
    resultado["formato"] = True
    if sello["huella_sha256"] != huella_de(datos):
        resultado["motivo"] = "El contenido del paquete no corresponde a la huella sellada: fue modificado."
        return resultado
    try:
        incrustada = Ed25519PublicKey.from_public_bytes(base64.b64decode(sello["clave_publica"]))
        incrustada.verify(base64.b64decode(sello["firma"]), canonico({"huella_sha256": sello["huella_sha256"]}))
        resultado["firma_valida"] = True
    except (InvalidSignature, ValueError, TypeError):
        resultado["motivo"] = "La firma del sello no es válida."
        return resultado
    resultado["clave_de_verdeazul"] = bytes_publicos(incrustada) == bytes_publicos(clave_verdeazul)
    if not resultado["clave_de_verdeazul"]:
        resultado["motivo"] = "El sello está firmado con una clave que no es la de Verdeazul."
        return resultado
    resultado["valido"] = True
    resultado["motivo"] = "El paquete lleva el sello de Verdeazul y no fue modificado."
    return resultado


def verificar(certificado, clave_verdeazul):
    """Revisa un certificado ya leído. Devuelve un diccionario con cada comprobación y un veredicto:
    - formato: tiene contenido, firma y los campos del contenido;
    - firma_valida: la firma corresponde al contenido con la clave incrustada (si alguien cambió
      una cifra, deja de corresponder);
    - clave_de_verdeazul: la clave incrustada es la publicada por Verdeazul;
    - valido: las tres cosas a la vez."""
    resultado = {"formato": False, "firma_valida": False, "clave_de_verdeazul": False, "valido": False, "motivo": ""}
    if not isinstance(certificado, dict) or not isinstance(certificado.get("contenido"), dict):
        resultado["motivo"] = "El archivo no tiene la forma de un certificado de Verdeazul."
        return resultado
    contenido = certificado["contenido"]
    faltan = [campo for campo in CAMPOS if campo not in contenido]
    if faltan or not isinstance(certificado.get("firma"), str):
        resultado["motivo"] = "Faltan datos del certificado: " + ", ".join(faltan or ["firma"])
        return resultado
    resultado["formato"] = True
    try:
        incrustada = Ed25519PublicKey.from_public_bytes(base64.b64decode(contenido["clave_publica"]))
        incrustada.verify(base64.b64decode(certificado["firma"]), canonico(contenido))
        resultado["firma_valida"] = True
    except (InvalidSignature, ValueError, TypeError):
        resultado["motivo"] = "La firma no corresponde al contenido: el certificado fue modificado o la firma es falsa."
        return resultado
    resultado["clave_de_verdeazul"] = (
        bytes_publicos(incrustada) == bytes_publicos(clave_verdeazul) and contenido["clave_id"] == huella(clave_verdeazul)
    )
    if not resultado["clave_de_verdeazul"]:
        resultado["motivo"] = "La firma es correcta, pero con una clave que no es la de Verdeazul: no es un certificado de Verdeazul."
        return resultado
    resultado["valido"] = True
    resultado["motivo"] = "La firma es de Verdeazul y el contenido no fue modificado."
    return resultado


def verificar_archivo(texto, clave_verdeazul):
    """Un archivo puede ser un certificado o un paquete de exportación del auditor (lleva «sello»)."""
    try:
        datos = json.loads(texto)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"formato": False, "firma_valida": False, "clave_de_verdeazul": False, "valido": False,
                "motivo": "El archivo no es JSON."}
    if isinstance(datos, dict) and "sello" in datos and "contenido" not in datos:
        sello = datos.pop("sello")
        return verificar_sello(datos, sello, clave_verdeazul)
    return verificar(datos, clave_verdeazul)
