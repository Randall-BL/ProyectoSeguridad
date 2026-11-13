"""Pruebas de la comprobación pública (6.6, 6.7, C20): verificación por archivo, consulta por
código con límite de ritmo, cabeceras y clave publicada. La función va_comprobar y los permisos de
va_publico se prueban contra la base en app/flujos/tests_certificados.py.

    cd publico && python -m unittest -v
"""

import copy
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verificador"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

import verdeazul_certificado as vc  # noqa: E402

CLAVE = Ed25519PrivateKey.generate()
_pem = Path(tempfile.mkdtemp()) / "clave.pem"
_pem.write_text(vc.pem_publico(CLAVE.public_key()), encoding="utf-8")
with mock.patch.dict(os.environ, {"CLAVE_PUBLICA_PEM": str(_pem), "DATABASE_URL": "postgresql://sin-base"}):
    import servicio  # noqa: E402

CONTENIDO = {"codigo": "VA-2026-II-7K3M9QXT", "finca": "F-001", "parcela": "P-1", "periodo": "2026-II",
             "toneladas_co2": "12.500", "emitido_en": "2026-11-13T18:00:00Z", "aprobado_por": "Carla",
             "reemplaza": None}
CERTIFICADO = vc.firmar(CONTENIDO, CLAVE)


def _fila(estado="vigente", reemplazado_por=None, certificado=CERTIFICADO):
    return (certificado["contenido"]["codigo"], estado, Decimal(certificado["contenido"]["toneladas_co2"]), "2026-II",
            datetime(2026, 11, 13, tzinfo=UTC), datetime(2026, 11, 14, tzinfo=UTC) if estado == "revocado" else None,
            reemplazado_por, certificado["contenido"], certificado["firma"])


class BaseFalsa:
    def __init__(self, fila):
        self.fila, self.consultas = fila, []

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, parametros):
        self.consultas.append(parametros)
        return self

    def fetchone(self):
        return self.fila


class ComprobacionPublica(unittest.TestCase):
    def setUp(self):
        self.cliente = servicio.app.test_client()
        servicio.POR_CODIGO.vistos.clear()
        servicio.POR_ARCHIVO.vistos.clear()

    def _subir(self, certificado):
        datos = {"certificado": (io.BytesIO(json.dumps(certificado).encode()), "certificado.json")}
        return self.cliente.post("/verificar", data=datos, content_type="multipart/form-data")

    def _consultar(self, codigo, fila):
        base = BaseFalsa(fila)
        with mock.patch.object(servicio.psycopg, "connect", base):
            return self.cliente.get("/comprobar", query_string={"codigo": codigo}), base

    # 6.6 ------------------------------------------------------------------------------------------

    def test_un_archivo_valido(self):
        respuesta = self._subir(CERTIFICADO)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Certificado válido", respuesta.text)
        self.assertIn("12.500", respuesta.text)

    def test_t32_el_mismo_con_una_tonelada_cambiada(self):
        alterado = copy.deepcopy(CERTIFICADO)
        alterado["contenido"]["toneladas_co2"] = "13.500"
        respuesta = self._subir(alterado)
        self.assertIn("Certificado no válido", respuesta.text)
        self.assertIn("modificado", respuesta.text)
        self.assertNotIn("13.500", respuesta.text)  # no se muestra un contenido que no pasó la firma

    def test_firmado_con_otra_clave_no_es_de_verdeazul(self):
        respuesta = self._subir(vc.firmar(CONTENIDO, Ed25519PrivateKey.generate()))
        self.assertIn("Certificado no válido", respuesta.text)
        self.assertIn("no es la de Verdeazul", respuesta.text)

    def test_sin_archivo_o_demasiado_grande(self):
        self.assertEqual(self.cliente.post("/verificar", data={}).status_code, 400)
        grande = {"certificado": (io.BytesIO(b"x" * 70000), "grande.json")}
        self.assertEqual(self.cliente.post("/verificar", data=grande, content_type="multipart/form-data").status_code, 413)

    def test_el_contenido_del_archivo_se_escapa(self):
        malicioso = vc.firmar({**CONTENIDO, "finca": "<script>alert(1)</script>"}, CLAVE)
        respuesta = self._subir(malicioso)
        self.assertNotIn("<script>alert(1)</script>", respuesta.text)
        self.assertIn("&lt;script&gt;", respuesta.text)

    # 6.7, C20 -------------------------------------------------------------------------------------

    def test_un_codigo_vigente(self):
        respuesta, base = self._consultar("va-2026-ii-7k3m9qxt", _fila())
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Certificado vigente", respuesta.text)
        self.assertIn("Válido, firmado por Verdeazul", respuesta.text)
        self.assertEqual(base.consultas, [("VA-2026-II-7K3M9QXT",)])  # se consulta el código exacto

    def test_t32_un_revocado_dice_cual_lo_reemplaza(self):
        respuesta, _ = self._consultar(CONTENIDO["codigo"], _fila("revocado", "VA-2026-II-ABCDEFGH"))
        self.assertIn("Certificado revocado", respuesta.text)
        self.assertIn("VA-2026-II-ABCDEFGH", respuesta.text)

    def test_un_sello_alterado_en_la_base_se_nota(self):
        alterado = copy.deepcopy(CERTIFICADO)
        alterado["contenido"]["toneladas_co2"] = "99.000"
        respuesta, _ = self._consultar(CONTENIDO["codigo"], _fila(certificado=alterado))
        self.assertIn("El sello no es válido", respuesta.text)

    def test_sin_busquedas_ni_comodines(self):
        for intento in ("VA-%", "VA-2026-II-%", "' OR 1=1 --", "VA-2026-II-7K3M9QX"):
            respuesta, base = self._consultar(intento, None)
            self.assertEqual(respuesta.status_code, 404)
            self.assertEqual(base.consultas, [])  # ni siquiera llega a la base

    def test_un_codigo_que_no_existe(self):
        respuesta, _ = self._consultar("VA-2026-II-ZZZZZZZZ", None)
        self.assertEqual(respuesta.status_code, 404)
        self.assertIn("No hay un certificado con ese código", respuesta.text)

    def test_limite_de_ritmo_por_origen(self):
        for _ in range(10):
            self._consultar("VA-2026-II-ZZZZZZZZ", None)
        respuesta, _ = self._consultar("VA-2026-II-ZZZZZZZZ", None)
        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(respuesta.headers["Retry-After"], "60")
        # Otro origen sigue pudiendo consultar; inventar un X-Forwarded-For no sirve para evadirlo.
        with mock.patch.object(servicio.psycopg, "connect", BaseFalsa(None)):
            otro = self.cliente.get("/comprobar?codigo=VA-2026-II-ZZZZZZZZ", headers={"X-Forwarded-For": "1.2.3.4, 9.9.9.9"})
            mismo = self.cliente.get("/comprobar?codigo=VA-2026-II-ZZZZZZZZ", headers={"X-Forwarded-For": "5.5.5.5, 127.0.0.1"})
        self.assertEqual(otro.status_code, 404)
        self.assertEqual(mismo.status_code, 429)

    def test_el_limite_se_libera_al_minuto(self):
        limite = servicio.LimiteDeRitmo(2)
        self.assertTrue(limite.permite("a", 0) and limite.permite("a", 1))
        self.assertFalse(limite.permite("a", 2))
        self.assertTrue(limite.permite("a", 62))

    # 6.2 y cabeceras --------------------------------------------------------------------------------

    def test_la_clave_publicada_es_la_que_verifica(self):
        respuesta = self.cliente.get("/.well-known/verdeazul-clave.pem")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(vc.huella(vc.clave_publica_de_pem(respuesta.text)), vc.huella(CLAVE.public_key()))

    def test_cabeceras_de_seguridad(self):
        respuesta = self.cliente.get("/")
        self.assertIn("default-src 'none'", respuesta.headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", respuesta.headers["Content-Security-Policy"])
        self.assertEqual(respuesta.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(respuesta.headers["Cache-Control"], "no-store")
        self.assertNotIn("<script", respuesta.text)

    def test_no_hay_otras_rutas(self):
        for ruta in ("/certificados", "/admin", "/comprobar/todos"):
            self.assertEqual(self.cliente.get(ruta).status_code, 404)


if __name__ == "__main__":
    unittest.main()
