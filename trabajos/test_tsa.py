"""Pruebas del cliente RFC 3161 sin red (las TSA reales se probaron a mano y se prueban en el
despliegue). Las del trabajo diario con la base están en app/flujos/tests_trabajos.py.

    cd trabajos && python -m unittest -v
"""

import hashlib
import io
import unittest
from unittest import mock

import tsa

HUELLA = hashlib.sha256(b"registro").hexdigest()


def respuesta(estado, *extra):
    cuerpo = tsa._tlv(0x30, tsa._entero(estado)) + b"".join(extra)
    return tsa._tlv(0x30, cuerpo)


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SelloDeTiempo(unittest.TestCase):
    def test_la_solicitud_lleva_la_huella_el_algoritmo_y_el_nonce(self):
        pedido = tsa.solicitud(bytes.fromhex(HUELLA), 0x1234)
        self.assertEqual(pedido[0], 0x30)
        self.assertIn(bytes.fromhex(HUELLA), pedido)
        self.assertIn(tsa.SHA256, pedido)
        self.assertTrue(pedido.endswith(b"\x01\x01\xff"))  # certReq verdadero

    def test_enteros_y_largos_en_der(self):
        self.assertEqual(tsa._entero(1), b"\x02\x01\x01")
        self.assertEqual(tsa._entero(0x80), b"\x02\x02\x00\x80")  # sin signo negativo
        self.assertEqual(tsa._largo(200), b"\x81\xc8")
        self.assertEqual(tsa._largo(300), b"\x82\x01\x2c")

    def test_solo_acepta_huellas_sha256(self):
        with self.assertRaises(ValueError):
            tsa.solicitud(b"corta", 1)

    def test_lee_el_estado_de_la_respuesta(self):
        self.assertEqual(tsa.estado(respuesta(0)), 0)
        self.assertEqual(tsa.estado(respuesta(2)), 2)
        with self.assertRaises(ValueError):
            tsa.estado(b"\x04\x00")

    def _sellar(self, cuerpo):
        with mock.patch.object(tsa.urllib.request, "urlopen", return_value=Respuesta(cuerpo)), \
                mock.patch.object(tsa.secrets, "randbits", return_value=0x5A):
            return tsa.sellar(HUELLA, "http://tsa.ejemplo")

    def test_un_sello_concedido_con_la_huella_y_el_nonce(self):
        cuerpo = respuesta(0, tsa._tlv(0x04, bytes.fromhex(HUELLA)), tsa._entero(0x5A))
        self.assertEqual(self._sellar(cuerpo), cuerpo)

    def test_un_rechazo_de_la_tsa(self):
        with self.assertRaisesRegex(ValueError, "rechazó"):
            self._sellar(respuesta(2))

    def test_un_sello_de_otra_huella_no_sirve(self):
        otra = hashlib.sha256(b"otro").digest()
        with self.assertRaisesRegex(ValueError, "no corresponde"):
            self._sellar(respuesta(0, tsa._tlv(0x04, otra), tsa._entero(0x5A)))


if __name__ == "__main__":
    unittest.main()
