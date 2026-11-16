#!/bin/sh
# Presentación, punto 3 (tarea 11.2): el intento prohibido enviado SIN la interfaz. Demuestra que
# decide el servidor: la petición lleva una sesión válida y su marca CSRF, igual que si viniera del
# botón, y aun así se rechaza.
#
# 1. Entre en la aplicación con el personaje que va a intentar algo que no le corresponde, por
#    ejemplo tec.ana (técnica), y abra una medición que esté «Enviada».
# 2. En las herramientas del navegador (F12 → Aplicación → Cookies) copie el valor de las cookies
#    __Host-sesion y csrftoken. No los pegue en ningún archivo: solo en esta terminal.
# 3. Corra, con el identificador de la medición (el que aparece en la dirección):
#
#      SESION='...' CSRF='...' sh infra/demo/intento-prohibido.sh <id-de-la-medicion> [accion]
#
#    La acción por omisión es «aprobar»; otras: devolver, enviar, enmienda.
#
# Resultado esperado: 403 y la regla que lo decidió (para la técnica, «matriz»: su rol no tiene ese
# verbo; para ver.carla sobre F-003, «C3»). El intento queda en la bitácora con resultado «denegado».
set -eu
: "${SESION:?Defina SESION con el valor de la cookie __Host-sesion}"
: "${CSRF:?Defina CSRF con el valor de la cookie csrftoken}"
APP="${APP:-https://verdeazul-app-708901712393.us-east1.run.app}"
MEDICION="${1:?Falta el identificador de la medición}"
ACCION="${2:-aprobar}"
RUTA="$APP/mediciones/$MEDICION/$ACCION/"

cuerpo="$(mktemp)"
trap 'rm -f "$cuerpo"' EXIT
codigo="$(curl -s -o "$cuerpo" -w '%{http_code}' -X POST "$RUTA" \
  -H "Cookie: __Host-sesion=$SESION; csrftoken=$CSRF" \
  -H "X-CSRFToken: $CSRF" -H "Origin: $APP" -H "Referer: $APP/mediciones/$MEDICION/" \
  --data-urlencode "motivo=Intento enviado sin la interfaz")"

echo "POST $RUTA"
echo "Respuesta: HTTP $codigo"
if grep -qi "csrf" "$cuerpo"; then
  echo "Falló la verificación CSRF: copie de nuevo las dos cookies (la sesión pudo haber cambiado)."
  exit 1
fi
regla="$(grep -o 'regla [A-Z0-9a-z-]*' "$cuerpo" | head -1 || true)"
[ -n "$regla" ] && echo "Lo decidió: $regla"
case "$codigo" in
  403|404) echo "Rechazado por el servidor, aunque la petición traía sesión y marca CSRF válidas." ;;
  302) echo "Redirigió: revise si la sesión venció (vuelve a iniciar sesión) o si pidió el segundo factor." ;;
  *) echo "Respuesta inesperada: revise la sesión y la medición." ;;
esac
