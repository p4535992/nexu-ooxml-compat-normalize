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

echo "Arresto OOXML Compat Normalize..."
docker compose down

echo "Container arrestati. I volumi dei log sono stati conservati."
