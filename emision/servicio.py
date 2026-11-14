"""Servicio de emisión (verdeazul-emision, tarea 6.3). No es público: Cloud Run solo deja entrar
peticiones con un token de identidad de sa-app (la aplicación, después de aprobar una medición,
autorizar una enmienda o exportar) o de sa-trabajos (el trabajo diario). Además, el servicio lee
de qué cuenta viene el token, la anota en la bitácora y rechaza cualquier otra (INVOCADORES).

    POST /emitir             {"medicion": "<uuid>"}
    POST /reemitir           {"enmienda": "<uuid>"}
    POST /emitir-pendientes
    POST /sellar             {"huella": "<sha256>", "objeto": "fincas"}
    GET  /salud

La clave privada llega de Secret Manager en FIRMA_CLAVE y la cadena de conexión (usuario
va_emision) en DATABASE_URL.
"""

import base64
import json
import logging
import os

import psycopg
from flask import Flask, jsonify, request

import emitir as e
import verdeazul_certificado as vc

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
registro = logging.getLogger("emision")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024

CLAVE = vc.clave_privada_de(os.environ["FIRMA_CLAVE"])
CLAVE_ID = vc.huella(CLAVE.public_key())
INVOCADORES = {c.strip() for c in os.environ.get("INVOCADORES", "").split(",") if c.strip()}


def _conexion():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, connect_timeout=10,
                           application_name="verdeazul-emision")


def _quien():
    """La cuenta del token que ya validó Cloud Run. Aquí solo se lee: la firma la comprobó la
    plataforma antes de dejar pasar la petición."""
    for cabecera in ("X-Serverless-Authorization", "Authorization"):
        valor = request.headers.get(cabecera, "")
        if valor.startswith("Bearer ") and valor.count(".") == 2:
            carga = valor.split(".")[1]
            try:
                datos = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
                return str(datos.get("email", ""))
            except (ValueError, UnicodeDecodeError):
                return ""
    return ""


@app.before_request
def _solo_invocadores():
    if request.path == "/salud":
        return None
    quien = _quien()
    request.origen = f"verdeazul-emision:{quien or 'local'}"
    if INVOCADORES and quien not in INVOCADORES:
        registro.warning("Petición de una cuenta no autorizada: %s", quien or "sin token")
        return jsonify(motivo="Esta cuenta no puede pedir emisiones."), 403
    return None


def _cuerpo():
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else {}


def _rechazo(accion, tipo, objeto, error):
    with _conexion() as conexion:
        e.anotar_denegacion(conexion, accion, tipo, objeto, str(error), request.origen)
    registro.info("%s %s rechazado: %s", accion, objeto, error)
    return jsonify(motivo=str(error)), 409


@app.post("/emitir")
def emitir():
    medicion = _cuerpo().get("medicion")
    try:
        with _conexion() as conexion:
            resultado = e.emitir(conexion, medicion, CLAVE, request.origen)
    except e.NoSeEmite as error:
        return _rechazo("emitir", "mediciones", medicion, error)
    return jsonify(resultado), 201 if resultado["resultado"] == "emitido" else 200


@app.post("/reemitir")
def reemitir():
    enmienda = _cuerpo().get("enmienda")
    try:
        with _conexion() as conexion:
            resultado = e.reemitir(conexion, enmienda, CLAVE, request.origen)
    except e.NoSeEmite as error:
        return _rechazo("reemitir", "enmiendas", enmienda, error)
    return jsonify(resultado), 200


@app.post("/emitir-pendientes")
def emitir_pendientes():
    with _conexion() as conexion:
        return jsonify(e.emitir_pendientes(conexion, CLAVE, request.origen)), 200


@app.post("/sellar")
def sellar():
    datos = _cuerpo()
    try:
        with _conexion() as conexion:
            sello = e.sellar(conexion, datos.get("huella"), datos.get("objeto", ""), CLAVE, request.origen)
    except e.NoSeEmite as error:
        return jsonify(motivo=str(error)), 400
    return jsonify(sello=sello), 200


@app.get("/salud")
def salud():
    return jsonify(estado="ok", clave_id=CLAVE_ID, version=os.environ.get("APP_VERSION", "local"))


@app.after_request
def _cabeceras(respuesta):
    respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    return respuesta
