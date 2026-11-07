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

# --- 1.13 Cuentas de servicio -------------------------------------------------------------------
# Una por componente, sin ningún rol al crearla: cada una recibe después solo lo que usa (sus
# secretos, invocar a emisión). Nunca se usa la cuenta por omisión de Compute, que es editora.
crear_cuenta() {
  if ! gcloud iam service-accounts describe "$1@$PROYECTO.iam.gserviceaccount.com" --project="$PROYECTO" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$1" --project="$PROYECTO" --display-name="$2"
  fi
}
crear_cuenta sa-app      "Aplicación Django (punto de cumplimiento)"
crear_cuenta sa-emision  "Servicio de emisión de certificados (SIS)"
crear_cuenta sa-publico  "Comprobación pública de certificados (PUB)"
crear_cuenta sa-trabajos "Trabajos programados"
crear_cuenta sa-build    "Construcción de imágenes en Cloud Build"

# sa-build: escribe imágenes solo en este repositorio, escribe sus registros y lee el código que
# sube gcloud builds submit a un bucket propio, que borra el código a los 7 días.
SA_BUILD="sa-build@$PROYECTO.iam.gserviceaccount.com"
BUCKET="gs://${PROYECTO}_cloudbuild"
if ! gcloud storage buckets describe "$BUCKET" >/dev/null 2>&1; then
  gcloud storage buckets create "$BUCKET" --project="$PROYECTO" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
fi
gcloud storage buckets update "$BUCKET" --lifecycle-file="$DIR/bucket-ciclo.json"
gcloud storage buckets add-iam-policy-binding "$BUCKET" \
  --member="serviceAccount:$SA_BUILD" --role=roles/storage.objectViewer >/dev/null
gcloud artifacts repositories add-iam-policy-binding "$REPO" --project="$PROYECTO" --location="$REGION" \
  --member="serviceAccount:$SA_BUILD" --role=roles/artifactregistry.writer >/dev/null
gcloud projects add-iam-policy-binding "$PROYECTO" --condition=None \
  --member="serviceAccount:$SA_BUILD" --role=roles/logging.logWriter >/dev/null

# La cuenta por omisión de Compute nace como editora del proyecto. Nada de Verdeazul la usa: se le
# quita el rol para que un despliegue que olvide indicar su cuenta falle en vez de correr con ella.
NUMERO="$(gcloud projects describe "$PROYECTO" --format='value(projectNumber)')"
gcloud projects remove-iam-policy-binding "$PROYECTO" --condition=None \
  --member="serviceAccount:${NUMERO}-compute@developer.gserviceaccount.com" \
  --role=roles/editor >/dev/null 2>&1 || true
