#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INDICES_DIR="$(cd -- "${SCRIPT_DIR}/../indices" && pwd)"

SETTINGS_FILE="${INDICES_DIR}/questions-settings.json"
MAPPING_FILE="${INDICES_DIR}/questions-mapping.json"

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
ELASTICSEARCH_INDEX="${ELASTICSEARCH_INDEX:-enade-questions}"
ELASTICSEARCH_USERNAME="${ELASTICSEARCH_USERNAME:-elastic}"
ELASTICSEARCH_PASSWORD="${ELASTICSEARCH_PASSWORD:-}"

RECREATE="${RECREATE:-false}"
CURL_TIMEOUT="${CURL_TIMEOUT:-30}"

log() {
    printf '[INFO] %s\n' "$1"
}

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "Comando obrigatório não encontrado: $1"
        exit 1
    fi
}

validate_files() {
    local file

    for file in "$SETTINGS_FILE" "$MAPPING_FILE"; do
        if [[ ! -f "$file" ]]; then
            error "Arquivo não encontrado: $file"
            exit 1
        fi
    done

    python3 -m json.tool "$SETTINGS_FILE" >/dev/null
    python3 -m json.tool "$MAPPING_FILE" >/dev/null

    log "Arquivos JSON validados."
}

build_auth_args() {
    if [[ -n "$ELASTICSEARCH_USERNAME" ]]; then
        if [[ -z "$ELASTICSEARCH_PASSWORD" ]]; then
            error "ELASTICSEARCH_PASSWORD não foi definida."
            exit 1
        fi

        AUTH_ARGS=(-u "${ELASTICSEARCH_USERNAME}:${ELASTICSEARCH_PASSWORD}")
    else
        AUTH_ARGS=()
    fi
}

check_connection() {
    local status

    log "Verificando conexão com o Elasticsearch..."

    status="$(
        curl --silent --show-error \
            --connect-timeout "$CURL_TIMEOUT" \
            --max-time "$CURL_TIMEOUT" \
            "${AUTH_ARGS[@]}" \
            -o /dev/null \
            -w '%{http_code}' \
            "${ELASTICSEARCH_URL}/"
    )" || {
        error "Não foi possível conectar ao Elasticsearch."
        exit 1
    }

    if [[ "$status" != "200" ]]; then
        error "Elasticsearch retornou HTTP ${status}."
        exit 1
    fi

    log "Conexão estabelecida."
}

index_exists() {
    local status

    status="$(
        curl --silent --show-error \
            --connect-timeout "$CURL_TIMEOUT" \
            --max-time "$CURL_TIMEOUT" \
            "${AUTH_ARGS[@]}" \
            -o /dev/null \
            -w '%{http_code}' \
            "${ELASTICSEARCH_URL}/${ELASTICSEARCH_INDEX}"
    )"

    case "$status" in
        200)
            return 0
            ;;
        404)
            return 1
            ;;
        *)
            error "Falha ao verificar índice. HTTP ${status}."
            exit 1
            ;;
    esac
}

delete_index() {
    log "Removendo índice existente: ${ELASTICSEARCH_INDEX}"

    curl --fail-with-body --silent --show-error \
        --connect-timeout "$CURL_TIMEOUT" \
        --max-time "$CURL_TIMEOUT" \
        "${AUTH_ARGS[@]}" \
        -X DELETE \
        "${ELASTICSEARCH_URL}/${ELASTICSEARCH_INDEX}" \
        >/dev/null

    log "Índice removido."
}

create_index() {
    log "Criando índice: ${ELASTICSEARCH_INDEX}"

    jq -s '.[0] * .[1]' \
        "$SETTINGS_FILE" \
        "$MAPPING_FILE" |
        curl --fail-with-body --silent --show-error \
            --connect-timeout "$CURL_TIMEOUT" \
            --max-time "$CURL_TIMEOUT" \
            "${AUTH_ARGS[@]}" \
            -X PUT \
            -H "Content-Type: application/json" \
            --data-binary @- \
            "${ELASTICSEARCH_URL}/${ELASTICSEARCH_INDEX}"

    printf '\n'
    log "Índice criado com sucesso."
}

main() {
    require_command curl
    require_command jq
    require_command python3

    validate_files
    build_auth_args
    check_connection

    if index_exists; then
        if [[ "$RECREATE" != "true" ]]; then
            error "O índice '${ELASTICSEARCH_INDEX}' já existe."
            error "Para recriá-lo, execute com RECREATE=true."
            exit 1
        fi

        delete_index
    fi

    create_index
}

main "$@"
