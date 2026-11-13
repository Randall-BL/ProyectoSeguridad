#!/bin/sh
# Crea los secretos en Secret Manager sin que pasen por un archivo ni por la pantalla: se generan
# aquí y viajan por la entrada estándar. Cada secreto lo puede leer solo la cuenta que lo usa.
# Lee la cadena del dueño de la base de .env.local, que escribe neon init y git ignora.
# Uso: sh infra/crear-secretos.sh    (solo crea los que faltan)
#      PYTHON=ruta/a/python sh infra/crear-secretos.sh    (un Python con cryptography, para la firma)
set -eu
DIR="$(dirname "$0")"
. "$DIR/variables.sh"
RAIZ="$DIR/.."
PYTHON="${PYTHON:-python}"
cuenta() { echo "sa-$1@$PROYECTO.iam.gserviceaccount.com"; }
SA_APP="$(cuenta app)"
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
aleatorio() { "$PYTHON" -c "import secrets; print(secrets.token_urlsafe($1), end='')"; }
de_env_local() { grep "^$1=" "$RAIZ/.env.local" | cut -d= -f2- | tr -d "\"'"; }

# Llave secreta de Django.
if ! existe django-secret-key; then
  aleatorio 50 | crear django-secret-key
fi
permitir django-secret-key "$SA_APP"

# Un usuario de base por componente, cada uno con su cadena de conexión: por el pooler de Neon,
# con verify-full contra el paquete de CA de la imagen y channel binding.
usuario_de_base() {  # rol, secreto
  if ! existe "$2"; then
    dueno="$(de_env_local DATABASE_URL_UNPOOLED)"
    host_pool="$(de_env_local DATABASE_URL | sed -E 's#.*@([^/:?]+).*#\1#')"
    clave="$(aleatorio 32)"
    psql "$dueno" -X -q -v ON_ERROR_STOP=1 -v rol="$1" -v clave="$clave" -f "$RAIZ/db/roles/servicio.sql" >/dev/null
    printf '%s://%s:%s@%s/verdeazul?sslmode=verify-full&sslrootcert=%s&channel_binding=require' \
      postgresql "$1" "$clave" "$host_pool" "$CA_IMAGEN" | crear "$2"
  fi
}
usuario_de_base va_app db-url-app
permitir db-url-app "$SA_APP"
usuario_de_base va_emision db-url-emision
permitir db-url-emision "$(cuenta emision)"
usuario_de_base va_publico db-url-publico
permitir db-url-publico "$(cuenta publico)"
usuario_de_base va_trabajos db-url-trabajos
permitir db-url-trabajos "$(cuenta trabajos)"

# Clave Fernet que cifra en la base los secretos TOTP y las semillas de los códigos de recuperación
# (POL-AU-05): 32 bytes al azar en base64 URL. Perderla obliga a enrolar de nuevo a todo el mundo.
if ! existe mfa-clave; then
  "$PYTHON" -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(), end='')" \
    | crear mfa-clave
fi
permitir mfa-clave "$SA_APP"

# Clave Ed25519 de los certificados (6.1). La privada va de Python a Secret Manager por una
# tubería; la pública queda en docs/ y junto al verificador (6.2). Solo sa-emision la lee.
if ! existe firma-clave-privada; then
  "$PYTHON" "$DIR/clave_firma.py" "$RAIZ/docs/verdeazul-clave-publica.pem" "$RAIZ/verificador/verdeazul-clave-publica.pem" \
    | crear firma-clave-privada
fi
permitir firma-clave-privada "$(cuenta emision)"
# Comprobación: la guardada corresponde a la publicada (se compara dentro de Python, sin mostrarla).
gcloud secrets versions access latest --secret=firma-clave-privada --project="$PROYECTO" \
  | "$PYTHON" "$DIR/clave_firma.py" --comprobar "$RAIZ/docs/verdeazul-clave-publica.pem"
