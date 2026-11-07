#!/bin/sh
# Construye en Cloud Build la imagen de un componente, la publica en Artifact Registry y pone la
# misma etiqueta en git. Uso: sh infra/publicar.sh app v0.1.0
# Exige el árbol limpio y el commit ya subido a GitHub (a main o a una rama development-*): así cada
# imagen corresponde a un estado del código que cualquiera puede ver. Al fusionar a main se usa
# merge commit, no squash, para que el commit etiquetado siga en la historia de main.
set -eu
DIR="$(dirname "$0")"
. "$DIR/variables.sh"
COMPONENTE="$1"
VERSION="$2"

case "$VERSION" in
  v[0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "La versión debe tener la forma vX.Y.Z" >&2; exit 1 ;;
esac
if [ -n "$(git status --porcelain)" ]; then
  echo "Hay cambios sin commit: la imagen no correspondería a ningún commit." >&2; exit 1
fi
git fetch -q origin
COMMIT="$(git rev-parse --short=7 HEAD)"
if [ -z "$(git branch -r --contains HEAD)" ]; then
  echo "El commit $COMMIT no está en GitHub: súbalo primero." >&2; exit 1
fi

gcloud builds submit "$DIR/.." --project="$PROYECTO" --region="$REGION" \
  --config="$DIR/cloudbuild.yaml" \
  --substitutions="_COMPONENTE=$COMPONENTE,_VERSION=$VERSION,_COMMIT=$COMMIT,_REGISTRO=$REGISTRO" \
  --service-account="projects/$PROYECTO/serviceAccounts/sa-build@$PROYECTO.iam.gserviceaccount.com" \
  --gcs-source-staging-dir="gs://${PROYECTO}_cloudbuild/source"

# La etiqueta de git apunta al mismo commit que la imagen. Si ya existe (otro componente con la
# misma versión), se deja como está: las etiquetas v* no se mueven.
if ! git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
  git tag -a "$VERSION" -m "Versión $VERSION (imagen $COMPONENTE:$VERSION, commit $COMMIT)"
  git push -q origin "refs/tags/$VERSION"
fi
echo "Publicado $REGISTRO/$COMPONENTE:$VERSION (commit $COMMIT)"
