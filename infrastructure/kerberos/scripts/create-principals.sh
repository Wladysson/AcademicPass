#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PRINCIPALS_DIR="${PRINCIPALS_DIR:-$(cd "${SCRIPT_DIR}/../principals" && pwd)}"
KADMIN_LOCAL="${KADMIN_LOCAL:-kadmin.local}"

CREATED=0
EXISTING=0
FAILED=0

log() {
    printf '[INFO] %s\n' "$1"
}

warn() {
    printf '[WARN] %s\n' "$1" >&2
}

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

if ! command -v "$KADMIN_LOCAL" >/dev/null 2>&1; then
    error "Comando kadmin.local não encontrado."
    exit 1
fi

if [[ ! -d "$PRINCIPALS_DIR" ]]; then
    error "Diretório de principals não encontrado: $PRINCIPALS_DIR"
    exit 1
fi

shopt -s nullglob
principal_files=("$PRINCIPALS_DIR"/*.principals)
shopt -u nullglob

if (( ${#principal_files[@]} == 0 )); then
    error "Nenhum arquivo .principals encontrado em $PRINCIPALS_DIR"
    exit 1
fi

principal_exists() {
    local principal="$1"

    "$KADMIN_LOCAL" -q "getprinc ${principal}" >/dev/null 2>&1
}

create_principal() {
    local principal="$1"

    if principal_exists "$principal"; then
        log "Principal já existente: $principal"
        ((EXISTING += 1))
        return 0
    fi

    if "$KADMIN_LOCAL" -q "addprinc -randkey ${principal}" >/dev/null; then
        log "Principal criado: $principal"
        ((CREATED += 1))
    else
        error "Falha ao criar principal: $principal"
        ((FAILED += 1))
        return 1
    fi
}

for file in "${principal_files[@]}"; do
    log "Processando $(basename "$file")"

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%%#*}"
        line="${line//[[:space:]]/}"

        [[ -z "$line" ]] && continue

        if [[ ! "$line" =~ ^[a-zA-Z0-9._/-]+@ACADEMICPASS\.LOCAL$ ]]; then
            warn "Principal com formato inválido em $(basename "$file"): $line"
            ((FAILED += 1))
            continue
        fi

        create_principal "$line" || true
    done < "$file"
done

printf '\n'
log "Provisionamento concluído."
log "Criados: $CREATED"
log "Já existentes: $EXISTING"
log "Falhas: $FAILED"

if (( FAILED > 0 )); then
    exit 1
fi
