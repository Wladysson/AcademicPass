#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PRINCIPALS_DIR="${PRINCIPALS_DIR:-$(cd "${SCRIPT_DIR}/../principals" && pwd)}"
KEYTAB_DIR="${KEYTAB_DIR:-/etc/academicpass/keytabs}"
KADMIN_LOCAL="${KADMIN_LOCAL:-kadmin.local}"

GENERATED=0
FAILED=0

log() {
    printf '[INFO] %s\n' "$1"
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

if [[ "$KEYTAB_DIR" == "$SCRIPT_DIR"* ]]; then
    error "O diretório de keytabs não pode ficar dentro do diretório dos scripts."
    exit 1
fi

if [[ ! -d "$KEYTAB_DIR" ]]; then
    install -d -m 0700 "$KEYTAB_DIR"
fi

chmod 0700 "$KEYTAB_DIR"

shopt -s nullglob
principal_files=("$PRINCIPALS_DIR"/*.principals)
shopt -u nullglob

if (( ${#principal_files[@]} == 0 )); then
    error "Nenhum arquivo .principals encontrado em $PRINCIPALS_DIR"
    exit 1
fi

for file in "${principal_files[@]}"; do
    service_name="$(basename "$file" .principals)"
    keytab_path="${KEYTAB_DIR}/${service_name}.keytab"

    log "Gerando keytab para ${service_name}"

    temp_keytab="$(mktemp "${KEYTAB_DIR}/.${service_name}.XXXXXX")"
    chmod 0600 "$temp_keytab"

    file_failed=0
    principal_count=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        principal="${line%%#*}"
        principal="${principal//[[:space:]]/}"

        [[ -z "$principal" ]] && continue

        if [[ ! "$principal" =~ ^[a-zA-Z0-9._/-]+@ACADEMICPASS\.LOCAL$ ]]; then
            error "Principal inválido em $(basename "$file"): $principal"
            file_failed=1
            continue
        fi

        ((principal_count += 1))

        if ! "$KADMIN_LOCAL" -q \
            "ktadd -norandkey -k ${temp_keytab} ${principal}" >/dev/null; then
            error "Falha ao exportar principal: $principal"
            file_failed=1
        fi
    done < "$file"

    if (( principal_count == 0 )); then
        error "Nenhum principal encontrado em $(basename "$file")"
        file_failed=1
    fi

    if (( file_failed == 0 )); then
        if command -v klist >/dev/null 2>&1 &&
            ! klist -k "$temp_keytab" >/dev/null 2>&1; then
            error "Keytab inválido: $temp_keytab"
            file_failed=1
        fi
    fi

    if (( file_failed == 0 )); then
        mv -f -- "$temp_keytab" "$keytab_path"
        chmod 0600 "$keytab_path"
        log "Keytab gerado: $keytab_path"
        ((GENERATED += 1))
    else
        rm -f -- "$temp_keytab"
        ((FAILED += 1))
    fi
done

printf '\n'
log "Geração de keytabs concluída."
log "Arquivos gerados: $GENERATED"
log "Falhas: $FAILED"

if (( FAILED > 0 )); then
    exit 1
fi
