#!/bin/sh
# Crea los secretos en Secret Manager sin que pasen por un archivo ni por la pantalla: se generan
# aquí y viajan por la entrada estándar. Cada secreto lo puede leer solo la cuenta que lo usa.
# Lee la cadena del dueño de la base de .env.local, que escribe neon init y git ignora.
# Uso: sh infra/crear-secretos.sh    (solo crea los que faltan)
set -eu
DIR="$(dirname "$0")"
. "$DIR/variables.sh"
RAIZ="$DIR/.."
SA_APP="sa-app@$PROYECTO.iam.gserviceaccount.com"
CA_IMAGEN="/etc/ssl/certs/ca-certificates.crt"

existe() { gcloud secrets describe "$1" --project="$PROYECTO" >/dev/null 2>&1; }
crear() {
  gcloud secrets create "$1" --project="$PROYECTO" \
    --replication-policy=user-managed --locations="$REGION" --data-file=- >/dev/null
}
permitir() {
  gcloud secrets add-iam-policy-binding "$1" --project="$PROYECTO" \
    --member="serviceAccount:$2" --role=roles/secretmanager.secretAccessor >/dev/null
}
aleatorio() { python -c "import secrets; print(secrets.token_urlsafe($1), end='')"; }
de_env_local() { grep "^$1=" "$RAIZ/.env.local" | cut -d= -f2- | tr -d "\"'"; }

# Llave secreta de Django.
if ! existe django-secret-key; then
  aleatorio 50 | crear django-secret-key
fi
permitir django-secret-key "$SA_APP"

# Usuario va_app y su cadena de conexión: por el pooler de Neon, con verify-full contra el paquete
# de CA de la imagen y channel binding.
if ! existe db-url-app; then
  dueno="$(de_env_local DATABASE_URL_UNPOOLED)"
  host_pool="$(de_env_local DATABASE_URL | sed -E 's#.*@([^/:?]+).*#\1#')"
  clave="$(aleatorio 32)"
  psql "$dueno" -X -q -v ON_ERROR_STOP=1 -v clave="$clave" -f "$RAIZ/db/roles/va_app.sql"
  printf '%s://va_app:%s@%s/verdeazul?sslmode=verify-full&sslrootcert=%s&channel_binding=require' \
    postgresql "$clave" "$host_pool" "$CA_IMAGEN" | crear db-url-app
fi
permitir db-url-app "$SA_APP"

# Clave Fernet que cifra en la base los secretos TOTP y las semillas de los códigos de recuperación
# (POL-AU-05): 32 bytes al azar en base64 URL. Perderla obliga a enrolar de nuevo a todo el mundo.
if ! existe mfa-clave; then
  python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(), end='')" \
    | crear mfa-clave
fi
permitir mfa-clave "$SA_APP"
