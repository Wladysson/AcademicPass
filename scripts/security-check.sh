#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "Verificando arquivos sensíveis versionados..."

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Erro: diretório não pertence a um repositório Git."
    exit 1
fi

PATTERNS=(
    '\.keytab$'
    '(^|/)\.env($|\.)'
    '\.pem$'
    '\.p12$'
    '\.pfx$'
    'id_rsa$'
    'id_ed25519$'
)

FOUND=0

for pattern in "${PATTERNS[@]}"; do
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue

        echo "[ALERTA] Arquivo sensível versionado: $file"
        FOUND=1
    done < <(git ls-files | grep -Ei "$pattern" || true)
done

if [[ "$FOUND" -eq 1 ]]; then
    echo
    echo "Verificação concluída: arquivos potencialmente sensíveis encontrados."
    exit 1
fi

echo "Verificação concluída: nenhum arquivo sensível identificado."
