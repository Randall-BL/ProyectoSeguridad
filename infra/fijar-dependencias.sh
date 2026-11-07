#!/bin/sh
# Fija las dependencias de un componente con versión y huella, para la plataforma de la imagen
# (Linux, Python 3.14). Requiere uv (pip install uv). Uso: sh infra/fijar-dependencias.sh app
set -eu
cd "$(dirname "$0")/../$1"
uv pip compile requirements.in --generate-hashes \
  --python-version 3.14 --python-platform x86_64-manylinux_2_28 --no-strip-markers \
  --custom-compile-command "sh infra/fijar-dependencias.sh $1" -o requirements.txt
