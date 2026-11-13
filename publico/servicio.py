"""Comprobación pública de certificados (verdeazul-publico, tareas 6.2, 6.6 y 6.7). Es el rol PUB
de la matriz: cualquiera, sin cuenta.

    GET  /                                   las dos formas de comprobar
    POST /verificar                          «dado el archivo» (6.6): firma, contenido y clave
    GET  /comprobar?codigo=VA-...            «dado el código» (C20, 6.7): sello, estado, toneladas,
                                             período y, si fue revocado, el código del reemplazo
    GET  /.well-known/verdeazul-clave.pem    la clave pública de Verdeazul (6.2)
    GET  /salud

Se conecta con va_publico, que no tiene permiso sobre ninguna tabla: solo puede llamar a
va_comprobar(codigo), que busca por código exacto y no devuelve datos del titular. No hay
listados ni búsquedas. Las consultas por código tienen un límite de ritmo por origen.
"""

import json
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

import psycopg
from flask import Flask, render_template, request

import verdeazul_certificado as vc

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
registro = logging.getLogger("publico")

AQUI = Path(__file__).resolve().parent
app = Flask(__name__, template_folder="plantillas", static_folder="estatico", static_url_path="/estatico")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # un certificado pesa menos de 2 KB

def _pem():
    """En la imagen, la clave viene copiada junto al servicio; en el repositorio, junto al
    verificador. CLAVE_PUBLICA_PEM permite probar con otra."""
    for ruta in (os.environ.get("CLAVE_PUBLICA_PEM"), AQUI / "verdeazul-clave-publica.pem",
                 AQUI.parent / "verificador" / "verdeazul-clave-publica.pem"):
        if ruta and Path(ruta).exists():
            return Path(ruta).read_text(encoding="utf-8")
    raise RuntimeError("No está la clave pública de Verdeazul.")


PEM = _pem()
CLAVE = vc.clave_publica_de_pem(PEM)
CLAVE_ID = vc.huella(CLAVE)
BASE = os.environ.get("DATABASE_URL", "")  # usuario va_publico
CODIGO = re.compile(r"^VA-[A-Z0-9-]{1,12}-[A-HJ-NP-Z2-9]{8}$")
REPOSITORIO = "https://github.com/Randall-BL/ProyectoSeguridad/tree/main/verificador"


class LimiteDeRitmo:
    """Cuántas consultas acepta cada origen por minuto. Vive en la memoria de la instancia: con
    una instancia como máximo (maxScale 1) es un límite real; con más, sería por instancia."""

    def __init__(self, por_minuto):
        self.por_minuto = por_minuto
        self.vistos = defaultdict(deque)
        self.candado = threading.Lock()

    def permite(self, origen, ahora=None):
        ahora = time.monotonic() if ahora is None else ahora
        with self.candado:
            cola = self.vistos[origen]
            while cola and ahora - cola[0] > 60:
                cola.popleft()
            if len(cola) >= self.por_minuto:
                return False
            cola.append(ahora)
            if len(self.vistos) > 10000:  # que la tabla no crezca sin fin
                for viejo in [o for o, c in self.vistos.items() if not c or ahora - c[-1] > 60]:
                    del self.vistos[viejo]
            return True


POR_CODIGO = LimiteDeRitmo(int(os.environ.get("CONSULTAS_POR_MINUTO", "10")))
POR_ARCHIVO = LimiteDeRitmo(30)


def origen():
    """En Cloud Run, el último valor de X-Forwarded-For lo agrega la plataforma con la dirección
    real del cliente; los anteriores los puede inventar quien llama."""
    reenviado = request.headers.get("X-Forwarded-For", "")
    return reenviado.split(",")[-1].strip() if reenviado else (request.remote_addr or "")


def _demasiadas():
    registro.warning("Límite de ritmo alcanzado por %s en %s", origen(), request.path)
    return render_template("mensaje.html", titulo="Demasiadas consultas",
                           texto="Espere un minuto antes de volver a consultar."), 429, {"Retry-After": "60"}


@app.get("/")
def inicio():
    return render_template("inicio.html", clave_id=CLAVE_ID, repositorio=REPOSITORIO)


@app.post("/verificar")
def verificar():
    if not POR_ARCHIVO.permite(origen()):
        return _demasiadas()
    archivo = request.files.get("certificado")
    if archivo is None or not archivo.filename:
        return render_template("inicio.html", clave_id=CLAVE_ID, repositorio=REPOSITORIO,
                               error_archivo="Elija el archivo del certificado."), 400
    texto = archivo.read().decode("utf-8", errors="replace")
    resultado = vc.verificar_archivo(texto, CLAVE)
    contenido = None
    if resultado["formato"]:
        leido = json.loads(texto)
        contenido = leido.get("contenido") if isinstance(leido.get("contenido"), dict) else None
    return render_template("verificacion.html", resultado=resultado, clave_id=CLAVE_ID, contenido=contenido)


@app.get("/comprobar")
def comprobar():
    codigo = request.args.get("codigo", "").strip().upper()
    if not codigo:
        return render_template("inicio.html", clave_id=CLAVE_ID, repositorio=REPOSITORIO,
                               error_codigo="Escriba el código del certificado."), 400
    if not POR_CODIGO.permite(origen()):
        return _demasiadas()
    if not CODIGO.match(codigo):
        return render_template("comprobacion.html", codigo=codigo, certificado=None, formato=False), 404
    try:
        with psycopg.connect(BASE, connect_timeout=8, application_name="verdeazul-publico") as conexion:
            fila = conexion.execute(
                "SELECT codigo, estado, toneladas_co2, periodo, emitido_en, revocado_en, reemplazado_por, contenido, firma"
                " FROM va_comprobar(%s)", (codigo,)).fetchone()
    except psycopg.Error:
        registro.exception("No se pudo consultar la base")
        return render_template("mensaje.html", titulo="No se pudo comprobar ahora",
                               texto="El servicio no tiene conexión con la base. Inténtelo en unos minutos."), 503
    if fila is None:
        return render_template("comprobacion.html", codigo=codigo, certificado=None, formato=True), 404
    nombres = ("codigo", "estado", "toneladas_co2", "periodo", "emitido_en", "revocado_en", "reemplazado_por", "contenido", "firma")
    certificado = dict(zip(nombres, fila, strict=True))
    sello = vc.verificar({"contenido": certificado["contenido"], "firma": certificado["firma"]}, CLAVE)
    return render_template("comprobacion.html", codigo=codigo, certificado=certificado, sello=sello)


@app.get("/.well-known/verdeazul-clave.pem")
def clave_publica():
    return PEM, 200, {"Content-Type": "application/x-pem-file; charset=utf-8",
                      "Content-Disposition": 'inline; filename="verdeazul-clave-publica.pem"',
                      "Cache-Control": "public, max-age=3600"}


@app.get("/salud")
def salud():
    return {"estado": "ok", "clave_id": CLAVE_ID, "version": os.environ.get("APP_VERSION", "local")}


@app.errorhandler(404)
@app.errorhandler(405)
def no_existe(_error):
    return render_template("mensaje.html", titulo="Página no encontrada",
                           texto="Aquí solo se comprueban certificados."), 404


@app.errorhandler(413)
def muy_grande(_error):
    return render_template("mensaje.html", titulo="Archivo demasiado grande",
                           texto="Un certificado de Verdeazul pesa menos de 2 KB."), 413


@app.after_request
def cabeceras(respuesta):
    h = respuesta.headers
    h["Content-Security-Policy"] = ("default-src 'none'; style-src 'self'; img-src 'self'; form-action 'self'; "
                                    "base-uri 'none'; frame-ancestors 'none'")
    h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    h["X-Content-Type-Options"] = "nosniff"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    if request.path != "/.well-known/verdeazul-clave.pem" and not request.path.startswith("/estatico/"):
        h["Cache-Control"] = "no-store"
    return respuesta
