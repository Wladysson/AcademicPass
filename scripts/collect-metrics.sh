#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTORS_DIR="$ROOT_DIR/scripts/metrics"

if [[ ! -d "$COLLECTORS_DIR" ]]; then
    echo "Erro: diretório de coletores não encontrado: $COLLECTORS_DIR"
    exit 1
fi

echo "Iniciando coleta de métricas..."

FOUND=0

for collector in "$COLLECTORS_DIR"/*.sh; do
    [[ -f "$collector" ]] || continue
    [[ "$collector" == "$0" ]] && continue

    FOUND=1
    echo "Executando: $(basename "$collector")"
    bash "$collector"
done

if [[ "$FOUND" -eq 0 ]]; then
    echo "Nenhum coletor encontrado em $COLLECTORS_DIR"
    exit 1
fi

echo "Coleta de métricas finalizada."
