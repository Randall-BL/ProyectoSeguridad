#!/bin/sh
# Prepara lo que se crea una sola vez en Google Cloud. Se puede volver a correr: solo crea lo que
# falta y vuelve a aplicar la configuración. Uso: sh infra/preparar-gcp.sh
set -eu
DIR="$(dirname "$0")"
. "$DIR/variables.sh"

# --- 1.12 Registro de imágenes ------------------------------------------------------------------
# Etiquetas inmutables: una versión publicada (v0.1.0) no se puede mover a otra imagen.
# La limpieza conserva las últimas cinco versiones de cada imagen y todas las v1.x.
if ! gcloud artifacts repositories describe "$REPO" --location="$REGION" --project="$PROYECTO" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO" \
    --project="$PROYECTO" --location="$REGION" --repository-format=docker \
    --immutable-tags --description="Imágenes de Verdeazul, una por componente"
fi
gcloud artifacts repositories set-cleanup-policies "$REPO" \
  --project="$PROYECTO" --location="$REGION" \
  --policy="$DIR/registro-limpieza.json" --no-dry-run
