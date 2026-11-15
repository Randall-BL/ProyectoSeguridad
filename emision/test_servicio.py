"""Pruebas del servicio HTTP de emisión, sin base: la lógica con la base se prueba en
app/flujos/tests_certificados.py con el usuario va_emision real.

    cd emision && python -m unittest -v      (necesita verificador/ en PYTHONPATH)
"""

import base64
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verificador"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

import verdeazul_certificado as vc  # noqa: E402

CLAVE = Ed25519PrivateKey.generate()
APP = "sa-app@verdeazul-ce1115-g6.iam.gserviceaccount.com"
with mock.patch.dict(os.environ, {"FIRMA_CLAVE": vc.semilla_b64(CLAVE), "DATABASE_URL": "postgresql://sin-base",
                                  "INVOCADORES": f"{APP},sa-trabajos@verdeazul-ce1115-g6.iam.gserviceaccount.com"}):
    import servicio  # noqa: E402


def token(email):
    carga = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).decode().rstrip("=")
    return {"Authorization": f"Bearer cabecera.{carga}.firma"}


class ConexionFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ServicioDeEmision(unittest.TestCase):
    def setUp(self):
        self.cliente = servicio.app.test_client()
        parche = mock.patch.object(servicio, "_conexion", return_value=ConexionFalsa())
        parche.start()
        self.addCleanup(parche.stop)

    def test_la_salud_no_pide_token_ni_dice_mas_que_la_clave(self):
        respuesta = self.cliente.get("/salud")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json["clave_id"], vc.huella(CLAVE.public_key()))

    def test_sin_token_o_con_otra_cuenta_se_rechaza(self):
        self.assertEqual(self.cliente.post("/emitir", json={"medicion": "x"}).status_code, 403)
        respuesta = self.cliente.post("/emitir", json={"medicion": "x"}, headers=token("alguien@gmail.com"))
        self.assertEqual(respuesta.status_code, 403)

    def test_la_aplicacion_pide_una_emision(self):
        with mock.patch.object(servicio.e, "emitir", return_value={"resultado": "emitido", "codigo": "VA-1"}) as emitir:
            respuesta = self.cliente.post("/emitir", json={"medicion": "123"}, headers=token(APP))
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(emitir.call_args.args[1], "123")
        self.assertEqual(emitir.call_args.args[3], f"verdeazul-emision:{APP}")

    def test_un_rechazo_de_c4_queda_en_la_bitacora_y_responde_409(self):
        with mock.patch.object(servicio.e, "emitir", side_effect=servicio.e.NoSeEmite("C4: no aprobada")), \
                mock.patch.object(servicio.e, "anotar_denegacion") as anotar:
            respuesta = self.cliente.post("/emitir", json={"medicion": "123"}, headers=token(APP))
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(anotar.call_args.args[1:5], ("emitir", "mediciones", "123", "C4: no aprobada"))

    def test_el_sello_devuelve_la_firma(self):
        huella = "a" * 64
        with mock.patch.object(servicio.e, "sellar", return_value=vc.sellar(huella, CLAVE)):
            respuesta = self.cliente.post("/sellar", json={"huella": huella, "objeto": "fincas"}, headers=token(APP))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json["sello"]["huella_sha256"], huella)

    def test_cuerpos_grandes_se_rechazan(self):
        respuesta = self.cliente.post("/emitir", data="x" * 10000, headers={**token(APP), "Content-Type": "application/json"})
        self.assertEqual(respuesta.status_code, 413)


if __name__ == "__main__":
    unittest.main()
