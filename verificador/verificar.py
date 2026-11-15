"""Verifica un certificado de Verdeazul Carbono sin conectarse al sistema (tarea 6.8).

Es lo que haría un comprador en otro país: con el archivo del certificado y la clave pública que
Verdeazul publica (verdeazul-clave-publica.pem, junto a este programa y en el README), confirma que la firma
es de Verdeazul y que nadie cambió el contenido.

    pip install cryptography
    python verificar.py certificado.json
    python verificar.py certificado.json --clave otra-copia-de-la-clave.pem

Sale con 0 si el certificado es válido y con 1 si no lo es.
"""

import argparse
import sys
from pathlib import Path

from verdeazul_certificado import clave_publica_de_pem, huella, verificar_archivo

AQUI = Path(__file__).resolve().parent


def main(argumentos=None):
    lector = argparse.ArgumentParser(description="Verifica un certificado de Verdeazul Carbono sin conexión.")
    lector.add_argument("certificado", type=Path, help="El archivo JSON del certificado.")
    lector.add_argument("--clave", type=Path, default=AQUI / "verdeazul-clave-publica.pem",
                        help="La clave pública de Verdeazul (por omisión, la que viene con este programa).")
    opciones = lector.parse_args(argumentos)

    clave = clave_publica_de_pem(opciones.clave.read_text(encoding="utf-8"))
    resultado = verificar_archivo(opciones.certificado.read_bytes().decode("utf-8", errors="replace"), clave)
    print(f"Clave de Verdeazul: {huella(clave)}")
    for etiqueta, campo in (("Forma de certificado", "formato"), ("Firma correcta", "firma_valida"),
                            ("Clave de Verdeazul", "clave_de_verdeazul")):
        print(f"  {etiqueta}: {'sí' if resultado[campo] else 'no'}")
    print(("VÁLIDO: " if resultado["valido"] else "NO VÁLIDO: ") + resultado["motivo"])
    return 0 if resultado["valido"] else 1


if __name__ == "__main__":
    sys.exit(main())
