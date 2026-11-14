"""Emisión, revocación y sello (tareas 6.3, 6.4, 6.5 y 6.10). Es el componente SIS de la matriz:
ninguna persona emite ni revoca; lo hace este servicio con su propio usuario de base (va_emision),
que solo puede leer lo necesario y escribir certificados. La base vuelve a comprobar C4 con un
disparador (negocio/sql/0006).

Cada función recibe una conexión de psycopg y trabaja en una sola transacción: si algo falla,
no queda nada a medias, ni el certificado ni su registro en la bitácora.
"""

import re
import secrets
import uuid
from datetime import UTC, datetime

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import verdeazul_certificado as vc

ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I: se dicta por teléfono sin errores
ORIGEN = "verdeazul-emision"

MEDICION = """
SELECT m.id, m.estado, m.parcela_id, m.periodo_id, v.toneladas_co2,
       pa.codigo AS parcela, f.codigo AS finca, pe.nombre AS periodo,
       trim(coalesce(u.first_name, '') || ' ' || coalesce(u.last_name, '')) AS aprobado_por
FROM negocio_medicion m
JOIN negocio_versionmedicion v ON v.id = m.version_vigente_id
JOIN negocio_parcela pa ON pa.id = m.parcela_id
JOIN negocio_finca f ON f.id = pa.finca_id
JOIN negocio_periodo pe ON pe.id = m.periodo_id
LEFT JOIN cuentas_usuario u ON u.id = m.aprobada_por_id
WHERE m.id = %s
"""

VIGENTE = """
SELECT id, codigo, medicion_id, toneladas_co2 FROM negocio_certificado
WHERE parcela_id = %s AND periodo_id = %s AND estado = 'vigente'
"""


class NoSeEmite(Exception):
    """La petición no cumple C4: no se firma nada. El mensaje dice por qué."""


def identificador(valor):
    try:
        return uuid.UUID(str(valor))
    except ValueError:
        raise NoSeEmite("El identificador no es válido.") from None


def anotar(cur, accion, objeto_tipo, objeto_id, *, resultado="concedido", regla="C4", origen=ORIGEN, despues=""):
    cur.execute(
        "SELECT bitacora_anexar(NULL::uuid, 'SIS', %s, %s, %s, '', %s, %s, %s, '', '', %s)",
        (accion, objeto_tipo, str(objeto_id), resultado, regla, origen, despues),
    )


def anotar_denegacion(conexion, accion, objeto_tipo, objeto_id, motivo, origen=ORIGEN):
    """La denegación queda en la bitácora en su propia transacción, porque la de la acción se
    deshizo. La regla es lo que va antes de los dos puntos del motivo (C4, por ejemplo)."""
    regla = motivo.split(":", 1)[0] if ":" in motivo[:6] else "C4"
    with conexion.transaction(), conexion.cursor() as cur:
        anotar(cur, accion, objeto_tipo, objeto_id, resultado="denegado", regla=regla, origen=origen)


def _codigo(periodo):
    periodo = re.sub(r"[^A-Z0-9-]", "", periodo.upper())[:12]
    return f"VA-{periodo}-" + "".join(secrets.choice(ALFABETO) for _ in range(8))


def _medicion(cur, medicion_id):
    cur.execute(MEDICION, (medicion_id,))
    m = cur.fetchone()
    if m is None:
        raise NoSeEmite("C4: la medición no existe o no tiene versión vigente.")
    # Una emisión a la vez por parcela y período: dos pedidos simultáneos no pueden emitir dos
    # certificados vigentes (además lo impide el índice único de la base).
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"certificado:{m['parcela_id']}:{m['periodo_id']}",))
    return m


def _firmar_e_insertar(cur, m, clave, *, reemplaza=None, aprobado_por=None, origen=ORIGEN):
    ahora = datetime.now(UTC).replace(microsecond=0)
    contenido = {
        "codigo": _codigo(m["periodo"]),
        "finca": m["finca"],
        "parcela": m["parcela"],
        "periodo": m["periodo"],
        "toneladas_co2": f"{m['toneladas_co2']:.3f}",
        "emitido_en": ahora.isoformat().replace("+00:00", "Z"),
        "aprobado_por": aprobado_por or m["aprobado_por"],
        "reemplaza": reemplaza["codigo"] if reemplaza else None,
    }
    certificado = vc.firmar(contenido, clave)
    nuevo = uuid.uuid4()
    cur.execute(
        """INSERT INTO negocio_certificado (id, codigo, medicion_id, parcela_id, periodo_id, toneladas_co2,
               estado, emitido_en, revocado_en, reemplaza_id, contenido, firma, clave_id)
           VALUES (%s, %s, %s, %s, %s, %s, 'vigente', %s, NULL, %s, %s, %s, %s)""",
        (nuevo, contenido["codigo"], m["id"], m["parcela_id"], m["periodo_id"], m["toneladas_co2"], ahora,
         reemplaza["id"] if reemplaza else None, Jsonb(certificado["contenido"]), certificado["firma"],
         certificado["contenido"]["clave_id"]),
    )
    anotar(cur, "emitir", "certificados", nuevo, origen=origen, despues=vc.huella_de(certificado))
    return {"id": str(nuevo), "codigo": contenido["codigo"]}


def emitir(conexion, medicion_id, clave, origen=ORIGEN):
    """6.3: certifica una medición aprobada. Si ya tiene certificado vigente, lo devuelve sin
    emitir otro (se puede llamar dos veces sin duplicar)."""
    medicion_id = identificador(medicion_id)
    with conexion.transaction(), conexion.cursor(row_factory=dict_row) as cur:
        m = _medicion(cur, medicion_id)
        if m["estado"] != "aprobada":
            raise NoSeEmite("C4: solo se certifica una medición aprobada.")
        cur.execute(VIGENTE, (m["parcela_id"], m["periodo_id"]))
        vigente = cur.fetchone()
        if vigente:
            if vigente["medicion_id"] == m["id"]:
                return {"resultado": "ya_emitido", "codigo": vigente["codigo"]}
            raise NoSeEmite("C4: ya hay un certificado vigente para esa parcela y ese período.")
        return {"resultado": "emitido", **_firmar_e_insertar(cur, m, clave, origen=origen)}


def reemitir(conexion, enmienda_id, clave, origen=ORIGEN):
    """6.5: después de una enmienda autorizada. Si las toneladas cambiaron, revoca el certificado
    vigente y emite el reemplazo en la misma transacción, enlazados y sin borrar ninguno (C4,
    T-25). Si no cambiaron, solo anota la enmienda en el certificado."""
    enmienda_id = identificador(enmienda_id)
    with conexion.transaction(), conexion.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT e.id, e.estado, e.medicion_id,
                      trim(coalesce(u.first_name, '') || ' ' || coalesce(u.last_name, '')) AS autorizada_por
               FROM negocio_enmienda e LEFT JOIN cuentas_usuario u ON u.id = e.autorizada_por_id
               WHERE e.id = %s""",
            (enmienda_id,),
        )
        e = cur.fetchone()
        if e is None or e["estado"] != "autorizada":
            raise NoSeEmite("C4: la enmienda no existe o no está autorizada.")
        m = _medicion(cur, e["medicion_id"])
        cur.execute(VIGENTE, (m["parcela_id"], m["periodo_id"]))
        vigente = cur.fetchone()
        if vigente is None:
            if m["estado"] != "aprobada":
                return {"resultado": "sin_certificado"}
            nuevo = _firmar_e_insertar(cur, m, clave, aprobado_por=e["autorizada_por"], origen=origen)
            _anotar_enmienda(cur, nuevo["id"], e["id"])
            return {"resultado": "emitido", **nuevo}
        if vigente["toneladas_co2"] == m["toneladas_co2"]:
            _anotar_enmienda(cur, vigente["id"], e["id"])
            anotar(cur, "anotar_enmienda", "certificados", vigente["id"], origen=origen)
            return {"resultado": "anotada", "codigo": vigente["codigo"]}
        cur.execute(
            "UPDATE negocio_certificado SET estado = 'revocado', revocado_en = now() WHERE id = %s",
            (vigente["id"],),
        )
        anotar(cur, "revocar", "certificados", vigente["id"], origen=origen)
        nuevo = _firmar_e_insertar(cur, m, clave, reemplaza=vigente, aprobado_por=e["autorizada_por"], origen=origen)
        _anotar_enmienda(cur, nuevo["id"], e["id"])
        return {"resultado": "reemitido", "revocado": vigente["codigo"], **nuevo}


def _anotar_enmienda(cur, certificado_id, enmienda_id):
    cur.execute(
        """INSERT INTO negocio_certificado_enmiendas_anotadas (certificado_id, enmienda_id)
           VALUES (%s, %s) ON CONFLICT DO NOTHING""",
        (certificado_id, enmienda_id),
    )


def pendientes(conexion):
    """Lo que quedó sin hacer si una llamada de la aplicación falló: mediciones aprobadas sin
    certificado vigente y enmiendas autorizadas cuyo certificado no tiene las toneladas nuevas.
    Lo pide el trabajo diario (7.1)."""
    with conexion.cursor() as cur:
        cur.execute(
            """SELECT m.id FROM negocio_medicion m
               WHERE m.estado = 'aprobada' AND m.version_vigente_id IS NOT NULL AND NOT EXISTS (
                   SELECT 1 FROM negocio_certificado c
                   WHERE c.parcela_id = m.parcela_id AND c.periodo_id = m.periodo_id AND c.estado = 'vigente')
               ORDER BY m.aprobada_en"""
        )
        mediciones = [fila[0] for fila in cur.fetchall()]
        cur.execute(
            """SELECT DISTINCT ON (m.id) e.id FROM negocio_enmienda e
               JOIN negocio_medicion m ON m.id = e.medicion_id
               JOIN negocio_versionmedicion v ON v.id = m.version_vigente_id
               JOIN negocio_certificado c ON c.medicion_id = m.id AND c.estado = 'vigente'
               WHERE e.estado = 'autorizada' AND c.toneladas_co2 <> v.toneladas_co2
               ORDER BY m.id, e.autorizada_en DESC"""
        )
        enmiendas = [fila[0] for fila in cur.fetchall()]
    return mediciones, enmiendas


def emitir_pendientes(conexion, clave, origen=ORIGEN):
    mediciones, enmiendas = pendientes(conexion)
    hechos = {"emitidos": [], "reemitidos": [], "rechazados": 0}
    for medicion in mediciones:
        try:
            hechos["emitidos"].append(emitir(conexion, medicion, clave, origen)["codigo"])
        except NoSeEmite as error:
            anotar_denegacion(conexion, "emitir", "mediciones", medicion, str(error), origen)
            hechos["rechazados"] += 1
    for enmienda in enmiendas:
        try:
            hechos["reemitidos"].append(reemitir(conexion, enmienda, clave, origen).get("codigo"))
        except NoSeEmite as error:
            anotar_denegacion(conexion, "reemitir", "enmiendas", enmienda, str(error), origen)
            hechos["rechazados"] += 1
    return hechos


HUELLA = re.compile(r"^[0-9a-f]{64}$")


def sellar(conexion, huella_hex, objeto, clave, origen=ORIGEN):
    """6.10: sello de un paquete del auditor (C18). Llega solo la huella SHA-256 del paquete."""
    if not isinstance(huella_hex, str) or not HUELLA.match(huella_hex):
        raise NoSeEmite("C18: la huella del paquete no es un SHA-256 en hexadecimal.")
    sello = vc.sellar(huella_hex, clave)
    with conexion.transaction(), conexion.cursor() as cur:
        anotar(cur, "sellar", str(objeto)[:30], huella_hex, regla="C18", origen=origen, despues=huella_hex)
    return sello
