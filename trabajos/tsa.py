"""Sello de tiempo RFC 3161 (tarea 7.5, decisión 0.6) sin bibliotecas extra: la solicitud es una
estructura ASN.1 pequeña que se arma a mano en DER, y de la respuesta solo hace falta leer el
estado. La comprobación completa del sello (firma y certificado de la TSA) la hace cualquiera, sin
Verdeazul, con:

    openssl ts -reply -in sello.tsr -text
    openssl ts -verify -digest <huella> -in sello.tsr -CAfile cacert.pem -untrusted tsa.crt
"""

import secrets
import urllib.request

# AlgorithmIdentifier de SHA-256: OID 2.16.840.1.101.3.4.2.1 y parámetros NULL.
SHA256 = bytes.fromhex("300d06096086480165030402010500")


def _largo(n):
    if n < 0x80:
        return bytes([n])
    cifras = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(cifras)]) + cifras


def _tlv(etiqueta, contenido):
    return bytes([etiqueta]) + _largo(len(contenido)) + contenido


def _entero(n):
    cifras = n.to_bytes(max(1, (n.bit_length() + 7) // 8), "big")
    return _tlv(0x02, (b"\x00" + cifras) if cifras[0] & 0x80 else cifras)


def solicitud(huella, nonce):
    """TimeStampReq: versión 1, la huella SHA-256 (32 bytes), un nonce y certReq verdadero (que la
    TSA incluya su certificado, para verificar sin pedirlo aparte)."""
    if len(huella) != 32:
        raise ValueError("La huella debe ser un SHA-256 de 32 bytes.")
    imprint = _tlv(0x30, SHA256 + _tlv(0x04, huella))
    return _tlv(0x30, _entero(1) + imprint + _entero(nonce) + _tlv(0x01, b"\xff"))


def _leer(datos, pos):
    """Una etiqueta DER: devuelve (etiqueta, inicio del contenido, fin)."""
    etiqueta, largo = datos[pos], datos[pos + 1]
    pos += 2
    if largo & 0x80:
        n = largo & 0x7F
        largo = int.from_bytes(datos[pos:pos + n], "big")
        pos += n
    return etiqueta, pos, pos + largo


def estado(respuesta):
    """El PKIStatus de un TimeStampResp: 0 concedido, 1 concedido con cambios, 2 o más rechazado."""
    etiqueta, inicio, _ = _leer(respuesta, 0)
    if etiqueta != 0x30:
        raise ValueError("La respuesta no es un TimeStampResp.")
    etiqueta, inicio, _ = _leer(respuesta, inicio)  # PKIStatusInfo
    if etiqueta != 0x30:
        raise ValueError("La respuesta no trae PKIStatusInfo.")
    etiqueta, inicio, fin = _leer(respuesta, inicio)
    if etiqueta != 0x02:
        raise ValueError("El estado no es un entero.")
    return int.from_bytes(respuesta[inicio:fin], "big")


def sellar(huella_hex, url, tiempo=20):
    """Pide el sello a una TSA. Devuelve los bytes del TimeStampResp, ya revisado: estado concedido
    y la huella y el nonce pedidos dentro del sello."""
    huella = bytes.fromhex(huella_hex)
    nonce = secrets.randbits(63)
    peticion = urllib.request.Request(url, data=solicitud(huella, nonce), method="POST",
                                      headers={"Content-Type": "application/timestamp-query"})
    with urllib.request.urlopen(peticion, timeout=tiempo) as respuesta:  # noqa: S310 - TSA de la configuración
        cuerpo = respuesta.read()
    if estado(cuerpo) not in (0, 1):
        raise ValueError(f"La TSA rechazó la solicitud (estado {estado(cuerpo)}).")
    if huella not in cuerpo or _entero(nonce)[2:] not in cuerpo:
        raise ValueError("El sello no corresponde a la huella o al nonce pedidos.")
    return cuerpo
