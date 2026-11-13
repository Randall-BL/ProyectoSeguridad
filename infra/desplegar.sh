#!/bin/sh
# Despliega en Cloud Run un componente con la imagen de una versión ya publicada.
# Uso: sh infra/desplegar.sh app v0.1.0
set -eu
DIR="$(dirname "$0")"
. "$DIR/variables.sh"
COMPONENTE="$1"
VERSION="$2"
SERVICIO="verdeazul-$COMPONENTE"

if ! gcloud artifacts docker images describe "$REGISTRO/$COMPONENTE:$VERSION" >/dev/null 2>&1; then
  echo "No existe $COMPONENTE:$VERSION en el registro: publíquela primero con infra/publicar.sh." >&2
  exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
sed "s/__VERSION__/$VERSION/g" "$DIR/$COMPONENTE.service.yaml" > "$tmp"
gcloud run services replace "$tmp" --project="$PROYECTO" --region="$REGION"

# Solo la aplicación y la comprobación pública se abren a internet. La emisión queda privada: la
# invocan solo la aplicación y los trabajos programados, con su token de identidad.
case "$COMPONENTE" in
  app|publico)
    gcloud run services add-iam-policy-binding "$SERVICIO" --project="$PROYECTO" --region="$REGION" \
      --member=allUsers --role=roles/run.invoker >/dev/null ;;
  emision)
    for cuenta in sa-app sa-trabajos; do
      gcloud run services add-iam-policy-binding "$SERVICIO" --project="$PROYECTO" --region="$REGION" \
        --member="serviceAccount:$cuenta@$PROYECTO.iam.gserviceaccount.com" --role=roles/run.invoker >/dev/null
    done ;;
esac
gcloud run services describe "$SERVICIO" --project="$PROYECTO" --region="$REGION" \
  --format="value(status.url,status.latestReadyRevisionName)"
