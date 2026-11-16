#!/bin/sh
# Antes de presentar (tarea 11.4): Cloud Run y Neon se apagan sin uso, y la primera petición tarda
# unos segundos en despertarlos. Esto despierta la aplicación (con su motor), el servicio público,
# la base (la comprobación por código la consulta) y, si hay gcloud con sesión, la emisión.
# Uso, 10 minutos antes:  sh infra/demo/calentar.sh
# No es una prueba de carga: hace tres rondas de unas pocas peticiones (8.9).
set -u
APP="https://verdeazul-app-708901712393.us-east1.run.app"
PUB="https://verdeazul-publico-708901712393.us-east1.run.app"
EMI="https://verdeazul-emision-708901712393.us-east1.run.app"
CODIGO="${CODIGO:-VA-2026-I-QXWJWM9G}"

pedir() {  # nombre, url, [token]
  if [ -n "${3:-}" ]; then
    r="$(curl -s -o /dev/null -w '%{http_code} en %{time_total}s' -H "Authorization: Bearer $3" "$2")"
  else
    r="$(curl -s -o /dev/null -w '%{http_code} en %{time_total}s' "$2")"
  fi
  printf '  %-26s %s\n' "$1" "$r"
}

token=""
if command -v gcloud >/dev/null 2>&1; then
  token="$(gcloud auth print-identity-token 2>/dev/null || true)"
fi
for ronda in 1 2 3; do
  echo "Ronda $ronda"
  pedir "aplicación (portada)" "$APP/"
  pedir "aplicación (entrada)" "$APP/cuentas/login/"
  pedir "público + Neon" "$PUB/comprobar?codigo=$CODIGO"
  [ -n "$token" ] && pedir "emisión (privada)" "$EMI/salud" "$token"
done
echo "Listo si la última ronda responde 200 en menos de un segundo."
