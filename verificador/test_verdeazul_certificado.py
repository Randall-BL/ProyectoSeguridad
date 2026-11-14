"""Pruebas del formato del certificado (6.4) y del verificador de consola (6.8).

    cd verificador && python -m unittest -v
"""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import verdeazul_certificado as vc
import verificar

CONTENIDO = {
    "codigo": "VA-2026-II-7K3M9QXT", "finca": "F-0001", "parcela": "P-01", "periodo": "2026-II",
    "toneladas_co2": "12.500", "emitido_en": "2026-11-13T18:00:00Z", "aprobado_por": "Carla Verificadora",
    "reemplaza": None,
}


class FormatoDelCertificado(unittest.TestCase):
    def setUp(self):
        self.clave = Ed25519PrivateKey.generate()
        self.publica = self.clave.public_key()
        self.certificado = vc.firmar(CONTENIDO, self.clave)

    def test_un_certificado_recien_firmado_es_valido(self):
        resultado = vc.verificar(self.certificado, self.publica)
        self.assertTrue(resultado["valido"], resultado["motivo"])
        self.assertEqual(self.certificado["contenido"]["clave_id"], vc.huella(self.publica))

    def test_el_json_canonico_no_depende_del_orden_ni_de_los_espacios(self):
        desordenado = json.loads(json.dumps(dict(reversed(list(self.certificado["contenido"].items()))), indent=2))
        self.assertEqual(vc.canonico(desordenado), vc.canonico(self.certificado["contenido"]))
        reescrito = json.dumps({"firma": self.certificado["firma"], "contenido": desordenado}, indent=4)
        self.assertTrue(vc.verificar_archivo(reescrito, self.publica)["valido"])

    def test_cambiar_una_tonelada_rompe_la_firma(self):
        alterado = copy.deepcopy(self.certificado)
        alterado["contenido"]["toneladas_co2"] = "13.500"
        resultado = vc.verificar(alterado, self.publica)
        self.assertFalse(resultado["valido"])
        self.assertFalse(resultado["firma_valida"])
        self.assertIn("modificado", resultado["motivo"])

    def test_una_firma_correcta_con_otra_clave_no_es_de_verdeazul(self):
        falso = vc.firmar(CONTENIDO, Ed25519PrivateKey.generate())
        resultado = vc.verificar(falso, self.publica)
        self.assertTrue(resultado["firma_valida"])
        self.assertFalse(resultado["clave_de_verdeazul"])
        self.assertFalse(resultado["valido"])

    def test_cambiar_la_clave_incrustada_tambien_rompe_la_firma(self):
        otra = Ed25519PrivateKey.generate().public_key()
        alterado = copy.deepcopy(self.certificado)
        alterado["contenido"]["clave_publica"] = vc._b64(vc.bytes_publicos(otra))
        self.assertFalse(vc.verificar(alterado, self.publica)["firma_valida"])

    def test_archivos_que_no_son_certificados(self):
        for texto in ("no es json", "[]", '{"contenido": {}}', json.dumps({"contenido": CONTENIDO})):
            resultado = vc.verificar_archivo(texto, self.publica)
            self.assertFalse(resultado["valido"])
            self.assertFalse(resultado["formato"])

    def test_firma_que_no_es_base64(self):
        alterado = copy.deepcopy(self.certificado)
        alterado["firma"] = "esto no es base64 !!"
        self.assertFalse(vc.verificar(alterado, self.publica)["valido"])

    def test_el_sello_de_un_paquete_cubre_su_contenido(self):
        paquete = {"objeto": "fincas", "filas": [{"codigo": "F-0001"}]}
        sello = vc.sellar(vc.huella_de(paquete), self.clave)
        self.assertTrue(vc.verificar_sello(paquete, sello, self.publica)["valido"])
        archivo = json.dumps({**paquete, "sello": sello})
        self.assertTrue(vc.verificar_archivo(archivo, self.publica)["valido"])
        paquete["filas"].append({"codigo": "F-9999"})
        self.assertFalse(vc.verificar_sello(paquete, sello, self.publica)["valido"])
        ajeno = vc.sellar(vc.huella_de(paquete), Ed25519PrivateKey.generate())
        self.assertFalse(vc.verificar_sello(paquete, ajeno, self.publica)["clave_de_verdeazul"])

    def test_la_clave_privada_viaja_como_semilla_en_base64(self):
        semilla = vc.semilla_b64(self.clave)
        self.assertEqual(vc.huella(vc.clave_privada_de(semilla).public_key()), vc.huella(self.publica))

    def test_el_pem_publico_se_vuelve_a_leer(self):
        leida = vc.clave_publica_de_pem(vc.pem_publico(self.publica))
        self.assertEqual(vc.huella(leida), vc.huella(self.publica))


class VerificadorDeConsola(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp())
        clave = Ed25519PrivateKey.generate()
        (self.carpeta / "clave.pem").write_text(vc.pem_publico(clave.public_key()), encoding="utf-8")
        self.certificado = vc.firmar(CONTENIDO, clave)

    def correr(self, certificado):
        archivo = self.carpeta / "certificado.json"
        archivo.write_text(json.dumps(certificado, ensure_ascii=False), encoding="utf-8")
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = verificar.main([str(archivo), "--clave", str(self.carpeta / "clave.pem")])
        return codigo, salida.getvalue()

    def test_valido_sale_con_cero(self):
        codigo, salida = self.correr(self.certificado)
        self.assertEqual(codigo, 0)
        self.assertIn("VÁLIDO", salida)

    def test_alterado_sale_con_uno(self):
        alterado = copy.deepcopy(self.certificado)
        alterado["contenido"]["toneladas_co2"] = "99.000"
        codigo, salida = self.correr(alterado)
        self.assertEqual(codigo, 1)
        self.assertIn("NO VÁLIDO", salida)

    def test_la_clave_que_viene_con_el_programa_es_la_publicada(self):
        junto = Path(verificar.__file__).resolve().parent / "verdeazul-clave-publica.pem"
        publicada = Path(verificar.__file__).resolve().parent.parent / "docs" / "verdeazul-clave-publica.pem"
        if not publicada.exists():
            self.skipTest("Todavía no hay clave publicada en docs/.")
        self.assertEqual(junto.read_text(encoding="utf-8"), publicada.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
