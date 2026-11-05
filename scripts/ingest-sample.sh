#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.services.yml"

PDF_FILE="${1:-}"

if [[ -z "$PDF_FILE" ]]; then
    echo "Uso: $0 <caminho-do-pdf>"
    exit 1
fi

if [[ ! -f "$PDF_FILE" ]]; then
    echo "Erro: arquivo não encontrado: $PDF_FILE"
    exit 1
fi

if [[ "${PDF_FILE,,}" != *.pdf ]]; then
    echo "Erro: o arquivo informado não é um PDF."
    exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Erro: arquivo Compose não encontrado: $COMPOSE_FILE"
    exit 1
fi

echo "Iniciando ingestão da amostra..."
echo "Arquivo: $PDF_FILE"

docker compose -f "$COMPOSE_FILE" exec \
    -T ingestion-service \
    python -m ingestion "$PDF_FILE"

echo "Processo de ingestão finalizado."
