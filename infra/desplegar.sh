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

# El trabajo diario no es un servicio: es un Cloud Run Job que arranca Cloud Scheduler a las 2:30
# de Costa Rica, con la identidad de sa-trabajos, que solo puede iniciar ese trabajo.
if [ "$COMPONENTE" = trabajos ]; then
  SA_TRABAJOS="sa-trabajos@$PROYECTO.iam.gserviceaccount.com"
  sed "s/__VERSION__/$VERSION/g" "$DIR/trabajos.job.yaml" > "$tmp"
  gcloud run jobs replace "$tmp" --project="$PROYECTO" --region="$REGION"
  gcloud run jobs add-iam-policy-binding "$SERVICIO" --project="$PROYECTO" --region="$REGION" \
    --member="serviceAccount:$SA_TRABAJOS" --role=roles/run.invoker >/dev/null
  if gcloud scheduler jobs describe verdeazul-diario --project="$PROYECTO" --location="$REGION" >/dev/null 2>&1; then
    accion=update
  else
    accion=create
  fi
  gcloud scheduler jobs "$accion" http verdeazul-diario --project="$PROYECTO" --location="$REGION" \
    --schedule="30 2 * * *" --time-zone="America/Costa_Rica" --http-method=POST \
    --uri="https://run.googleapis.com/v2/projects/$PROYECTO/locations/$REGION/jobs/$SERVICIO:run" \
    --oauth-service-account-email="$SA_TRABAJOS" >/dev/null
  echo "Trabajo $SERVICIO con trabajos:$VERSION; Cloud Scheduler verdeazul-diario a las 2:30 (Costa Rica)."
  exit 0
fi

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
