"""Clave de firma de Verdeazul (tareas 6.1 y 6.2). Lo llama infra/crear-secretos.sh.

Generar: escribe la clave pública (PEM) en cada archivo indicado y la semilla privada, en base64,
por la salida estándar, que va por una tubería directo a Secret Manager. La privada nunca toca el
disco ni la pantalla: si la salida es una terminal, se niega.

    python infra/clave_firma.py docs/verdeazul-clave-publica.pem | gcloud secrets create ... --data-file=-

Comprobar: lee la semilla por la entrada estándar y dice si corresponde a la clave pública
publicada, sin mostrar nada de la privada.

    gcloud secrets versions access 1 --secret=firma-clave-privada | python infra/clave_firma.py --comprobar docs/verdeazul-clave-publica.pem
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verificador"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

import verdeazul_certificado as vc  # noqa: E402


def generar(destinos):
    if sys.stdout.isatty():
        sys.exit("La semilla privada no se muestra en pantalla: mándela por una tubería a gcloud.")
    clave = Ed25519PrivateKey.generate()
    pem = vc.pem_publico(clave.public_key())
    for destino in destinos:
        Path(destino).write_text(pem, encoding="utf-8", newline="\n")
    sys.stderr.write(f"Huella de la clave pública: {vc.huella(clave.public_key())}\n")
    sys.stdout.write(vc.semilla_b64(clave))


def comprobar(pem):
    publicada = vc.clave_publica_de_pem(Path(pem).read_text(encoding="utf-8"))
    guardada = vc.clave_privada_de(sys.stdin.read().strip()).public_key()
    if vc.huella(guardada) != vc.huella(publicada):
        sys.exit("La clave de Secret Manager NO corresponde a la clave pública publicada.")
    print(f"La clave de Secret Manager corresponde a la publicada: {vc.huella(publicada)}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--comprobar":
        comprobar(sys.argv[2])
    elif len(sys.argv) >= 2 and not sys.argv[1].startswith("-"):
        generar(sys.argv[1:])
    else:
        sys.exit(__doc__)
