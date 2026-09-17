#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERRORE: Docker non è installato o non è presente nel PATH." >&2
  exit 127
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERRORE: il comando 'docker compose' non è disponibile." >&2
  exit 127
fi

if [ ! -f docker-compose.yml ]; then
  echo "ERRORE: docker-compose.yml non trovato in $SCRIPT_DIR" >&2
  exit 1
fi

echo "Avvio OOXML Compat Normalize..."
docker compose up --build -d

echo
echo "Container avviato."
PORT=${OOXML_PORT:-8080}
CONTEXT=${OOXML_CONTEXT_PATH:-/ooxml-compat-normalize}
BIND=${OOXML_BIND_ADDRESS:-127.0.0.1}
case "$BIND" in
  0.0.0.0|::|"") BROWSER_HOST=127.0.0.1 ;;
  *) BROWSER_HOST=$BIND ;;
esac

echo "Interfaccia web: http://${BROWSER_HOST}:${PORT}${CONTEXT}/"
echo "Stato container:"
docker compose ps
