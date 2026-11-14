"""Trabajo diario de Verdeazul (fase 7). Cloud Scheduler lo arranca una vez al día como Cloud Run
Job, con la cuenta sa-trabajos y el usuario de base va_trabajos, que solo puede hacer esto:

    7.2  vencer las asignaciones temporales, cerrar las sesiones de quien perdió una asignación o
         una habilitación, dar de baja las cuentas de auditor con la ventana vencida y las que
         llevan 45 días sin uso (POL-CA-06), y borrar las sesiones expiradas;
    7.4  marcar las alertas que SUP no resolvió en dos días hábiles (C15): desde ahí las atiende GER;
    6.3  pedir al servicio de emisión lo que quedó sin emitir si una llamada de la aplicación falló;
    7.3  recalcular la cadena de la bitácora;
    7.5  pedir a una autoridad de sellado de tiempo (RFC 3161) un sello sobre la huella del último
         registro y guardarlo como testigo externo.

Cada paso corre en su propia transacción y deja su registro en la bitácora con el rol SIS. Si la
cadena está rota o un paso falla, el trabajo termina con error: Cloud Run lo marca como fallido y el
aviso queda en Cloud Logging con severidad ERROR (criterio de aceptación 4).
"""

import base64
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import psycopg

import tsa

ORIGEN = "verdeazul-trabajos"
ZONA = "America/Costa_Rica"
HOY = f"(now() AT TIME ZONE '{ZONA}')::date"
METADATOS = ("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
             "?audience={}")


def _registro():
    """Una línea JSON por evento: Cloud Logging toma «severity» y «message»."""

    class Formato(logging.Formatter):
        def format(self, r):
            return json.dumps({"severity": r.levelname, "message": r.getMessage(), "componente": ORIGEN},
                              ensure_ascii=False)

    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(Formato())
    registro = logging.getLogger(ORIGEN)
    registro.handlers = [manejador]
    registro.setLevel(logging.INFO)
    return registro


log = _registro()


def anotar(cur, accion, tipo, objeto_id, regla, resultado="concedido", despues=""):
    cur.execute("SELECT bitacora_anexar(NULL::uuid, 'SIS', %s, %s, %s, '', %s, %s, %s, '', '', %s)",
                (accion, tipo, str(objeto_id), resultado, regla, ORIGEN, despues))


def _cerrar_sesiones(cur, usuarios, regla):
    """Lo mismo que hace la aplicación al cambiar lo que alguien puede hacer (3.6): sin sesión, la
    siguiente petición pide entrar de nuevo con el alcance nuevo."""
    usuarios = sorted({str(u) for u in usuarios})
    if not usuarios:
        return 0
    cur.execute("DELETE FROM cuentas_sesion WHERE usuario_id = ANY(%s::uuid[]) RETURNING usuario_id", (usuarios,))
    cerradas = {str(fila[0]) for fila in cur.fetchall()}
    for usuario in sorted(cerradas):
        anotar(cur, "cerrar_sesiones", "cuenta", usuario, regla)
    return len(cerradas)


# --- 7.2 Vencimientos -----------------------------------------------------------------------------


def vencer_temporales(cur):
    cur.execute(f"""UPDATE negocio_asignacion SET terminada_en = now()
                    WHERE tipo = 'temporal' AND terminada_en IS NULL AND hasta < {HOY}
                    RETURNING id, tecnico_id""")
    filas = cur.fetchall()
    for asignacion, _ in filas:
        anotar(cur, "vencer", "asignaciones", asignacion, "C19")
    return {"temporales": len(filas), "sesiones": _cerrar_sesiones(cur, [t for _, t in filas], "POL-CA-04")}


def habilitaciones_vencidas(cur):
    """La habilitación de técnico vence sola por fecha en cada petición (3.8); aquí se anota y se
    cierran las sesiones de quien la tenía hasta ayer."""
    cur.execute(f"""SELECT id, usuario_id FROM cuentas_propuestarol
                    WHERE es_habilitacion AND estado = 'aprobada' AND fin_habilitacion = {HOY} - 1""")
    filas = cur.fetchall()
    for propuesta, _ in filas:
        anotar(cur, "vencer", "habilitaciones", propuesta, "POL-CA-04")
    return {"habilitaciones": len(filas), "sesiones": _cerrar_sesiones(cur, [u for _, u in filas], "POL-CA-04")}


def bajas(cur):
    cur.execute("""UPDATE cuentas_usuario SET is_active = false
                   WHERE is_active AND rol = 'AUD' AND vigente_hasta IS NOT NULL AND vigente_hasta < now()
                   RETURNING id""")
    auditores = [fila[0] for fila in cur.fetchall()]
    for usuario in auditores:
        anotar(cur, "desactivar", "cuenta", usuario, "C6")
    cur.execute("""UPDATE cuentas_usuario SET is_active = false
                   WHERE is_active AND rol <> '' AND coalesce(last_login, date_joined) < now() - interval '45 days'
                   RETURNING id""")
    sin_uso = [fila[0] for fila in cur.fetchall()]
    for usuario in sin_uso:
        anotar(cur, "desactivar", "cuenta", usuario, "POL-CA-06")
    return {"auditores": len(auditores), "sin_uso": len(sin_uso),
            "sesiones": _cerrar_sesiones(cur, auditores + sin_uso, "POL-CA-05")}


def sesiones_expiradas(cur):
    cur.execute("DELETE FROM cuentas_sesion WHERE expire_date < now()")
    return {"sesiones_expiradas": cur.rowcount}


# --- 7.4 Escalamiento -----------------------------------------------------------------------------


def escalar_alertas(cur):
    cur.execute(f"""UPDATE negocio_alerta a SET escalada_en = now()
                    FROM cuentas_usuario u
                    WHERE u.id = a.sujeto_id AND u.supervisor_id IS NOT NULL
                      AND a.resuelta_en IS NULL AND a.escalada_en IS NULL
                      AND va_dias_habiles((a.creada_en AT TIME ZONE '{ZONA}')::date, {HOY}) > 2
                    RETURNING a.id""")
    filas = cur.fetchall()
    for (alerta,) in filas:
        anotar(cur, "escalar", "alertas", alerta, "C15")
    return {"escaladas": len(filas)}


# --- 6.3 Emisiones pendientes ---------------------------------------------------------------------


def emisiones_pendientes(_cur=None):
    base = os.environ.get("EMISION_URL", "").rstrip("/")
    if not base:
        return {"omitido": "sin EMISION_URL"}
    cabeceras = {"Content-Type": "application/json"}
    if base.startswith("https://"):
        pedido = urllib.request.Request(METADATOS.format(urllib.parse.quote(base, safe="")),
                                        headers={"Metadata-Flavor": "Google"})
        with urllib.request.urlopen(pedido, timeout=5) as respuesta:  # noqa: S310 - dirección fija
            cabeceras["Authorization"] = "Bearer " + respuesta.read().decode()
    pedido = urllib.request.Request(base + "/emitir-pendientes", data=b"{}", headers=cabeceras, method="POST")
    with urllib.request.urlopen(pedido, timeout=120) as respuesta:  # noqa: S310 - URL de la configuración
        return json.loads(respuesta.read())


# --- 7.3 y 7.5 Bitácora ---------------------------------------------------------------------------


def verificar_cadena(cur):
    cur.execute("SELECT bitacora_verificar(), (SELECT max(id) FROM bitacora_registro)")
    rota, ultimo = cur.fetchone()
    if rota is not None:
        anotar(cur, "verificar_cadena", "bitacora", rota, "POL-BT-03", resultado="denegado")
        return {"integra": False, "primer_registro_alterado": rota}
    anotar(cur, "verificar_cadena", "bitacora", ultimo or 0, "POL-BT-03")
    return {"integra": True, "registros": ultimo or 0}


def testigo(cur):
    cur.execute("SELECT id, huella FROM bitacora_registro ORDER BY id DESC LIMIT 1")
    fila = cur.fetchone()
    if fila is None:
        return {"omitido": "bitácora vacía"}
    registro, huella = fila
    errores = []
    for url in [u.strip() for u in os.environ.get("TSA_URLS", "http://timestamp.digicert.com").split(",") if u.strip()]:
        try:
            sello = tsa.sellar(huella, url)
        except (OSError, ValueError) as error:
            errores.append(f"{url}: {error}")
            continue
        cur.execute("""INSERT INTO bitacora_testigo (instante, registro, huella, tsa, sello)
                       VALUES (now(), %s, %s, %s, %s) RETURNING id""",
                    (registro, huella, url, base64.b64encode(sello).decode()))
        testigo_id = cur.fetchone()[0]
        anotar(cur, "testigo", "bitacora", registro, "POL-BT-03", despues=huella)
        return {"testigo": testigo_id, "registro": registro, "tsa": url}
    raise RuntimeError("Ninguna TSA respondió: " + "; ".join(errores))


PASOS = [
    ("vencer_temporales", vencer_temporales),
    ("habilitaciones_vencidas", habilitaciones_vencidas),
    ("bajas", bajas),
    ("sesiones_expiradas", sesiones_expiradas),
    ("escalar_alertas", escalar_alertas),
    ("emisiones_pendientes", None),
    ("verificar_cadena", verificar_cadena),
    ("testigo", testigo),
]


def correr(conexion, pasos=PASOS):
    """Corre cada paso en su transacción. Devuelve (resumen, todo_bien)."""
    resumen, bien = {}, True
    for nombre, paso in pasos:
        try:
            if paso is None:  # habla con el servicio de emisión, no con la base
                resumen[nombre] = emisiones_pendientes()
            else:
                with conexion.transaction(), conexion.cursor() as cur:
                    resumen[nombre] = paso(cur)
        except Exception as error:  # noqa: BLE001 - un paso que falla no detiene a los demás
            bien = False
            resumen[nombre] = {"error": str(error)[:300]}
            log.error("Falló %s: %s", nombre, error)
            continue
        log.info("%s: %s", nombre, json.dumps(resumen[nombre], ensure_ascii=False, default=str))
    if resumen.get("verificar_cadena", {}).get("integra") is False:
        bien = False
        log.error("LA CADENA DE LA BITÁCORA ESTÁ ROTA desde el registro %s",
                  resumen["verificar_cadena"]["primer_registro_alterado"])
    return resumen, bien


def main():
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, connect_timeout=15,
                         application_name=ORIGEN) as conexion:
        _, bien = correr(conexion)
    return 0 if bien else 1


if __name__ == "__main__":
    sys.exit(main())
