#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.services.yml"

SOURCE_DIR="${1:-}"

if [[ -z "$SOURCE_DIR" ]]; then
    echo "Uso: $0 <diretorio-dos-pdfs>"
    exit 1
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Erro: diretório não encontrado: $SOURCE_DIR"
    exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Erro: arquivo Compose não encontrado: $COMPOSE_FILE"
    exit 1
fi

PDF_COUNT=$(find "$SOURCE_DIR" -type f -iname '*.pdf' | wc -l)

if [[ "$PDF_COUNT" -eq 0 ]]; then
    echo "Nenhum arquivo PDF encontrado no diretório."
    exit 1
fi

echo "Iniciando ingestão completa..."
echo "Diretório: $SOURCE_DIR"
echo "PDFs encontrados: $PDF_COUNT"

docker compose -f "$COMPOSE_FILE" exec \
    -T ingestion-service \
    python -m ingestion "$SOURCE_DIR"

echo "Ingestão completa finalizada."
