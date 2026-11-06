#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.services.yml"

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Erro: arquivo Compose não encontrado: $COMPOSE_FILE"
    exit 1
fi

echo "Iniciando reprocessamento dos documentos..."

docker compose -f "$COMPOSE_FILE" exec \
    -T indexing-service \
    python -m indexing --reindex

echo "Solicitação de reindexação finalizada."
