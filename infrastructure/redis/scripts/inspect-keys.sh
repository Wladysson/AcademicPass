#!/usr/bin/env bash

set -Eeuo pipefail

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_DATABASE="${REDIS_DATABASE:-0}"
REDIS_USERNAME="${REDIS_USERNAME:-}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

SCAN_COUNT="${SCAN_COUNT:-200}"
MAX_KEYS="${MAX_KEYS:-100}"
KEY_PATTERN="${KEY_PATTERN:-*}"

REDIS_CLI="${REDIS_CLI:-redis-cli}"

TOTAL_KEYS=0

REDIS_ARGS=(
    -h "$REDIS_HOST"
    -p "$REDIS_PORT"
    -n "$REDIS_DATABASE"
    --no-auth-warning
)

if [[ -n "$REDIS_USERNAME" ]]; then
    REDIS_ARGS+=(--user "$REDIS_USERNAME")
fi

if [[ -n "$REDIS_PASSWORD" ]]; then
    REDIS_ARGS=(
        --no-auth-warning
        -h "$REDIS_HOST"
        -p "$REDIS_PORT"
        -n "$REDIS_DATABASE"
        --user "${REDIS_USERNAME:-default}"
        -a "$REDIS_PASSWORD"
    )
fi

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

redis_command() {
    "$REDIS_CLI" "${REDIS_ARGS[@]}" --raw "$@"
}

validate_environment() {
    if ! [[ "$REDIS_PORT" =~ ^[0-9]+$ ]] ||
       (( REDIS_PORT < 1 || REDIS_PORT > 65535 )); then
        error "REDIS_PORT inválida."
        exit 1
    fi

    if ! [[ "$REDIS_DATABASE" =~ ^[0-9]+$ ]]; then
        error "REDIS_DATABASE deve ser um número inteiro."
        exit 1
    fi

    if ! [[ "$SCAN_COUNT" =~ ^[0-9]+$ ]] || (( SCAN_COUNT < 1 )); then
        error "SCAN_COUNT deve ser maior que zero."
        exit 1
    fi

    if ! [[ "$MAX_KEYS" =~ ^[0-9]+$ ]] || (( MAX_KEYS < 1 )); then
        error "MAX_KEYS deve ser maior que zero."
        exit 1
    fi
}

check_connection() {
    local response

    if ! response="$(redis_command PING 2>/dev/null)"; then
        error "Não foi possível conectar ao Redis."
        exit 1
    fi

    if [[ "$response" != "PONG" ]]; then
        error "Resposta inesperada do Redis: $response"
        exit 1
    fi

    log "Conexão estabelecida com Redis."
}

print_server_info() {
    local info

    log "Informações gerais do Redis"

    info="$(redis_command INFO server)"

    printf '%s\n' "$info" |
        awk -F: '
            /^redis_version:/ { print "Versão: " $2 }
            /^uptime_in_days:/ { print "Tempo ativo (dias): " $2 }
        '

    info="$(redis_command INFO memory)"

    printf '%s\n' "$info" |
        awk -F: '
            /^used_memory_human:/ { print "Memória utilizada: " $2 }
            /^maxmemory_human:/ { print "Limite de memória: " $2 }
            /^maxmemory_policy:/ { print "Política de eviction: " $2 }
        '

    info="$(redis_command INFO keyspace)"

    printf '\nBanco de dados:\n'

    printf '%s\n' "$info" |
        awk '/^db[0-9]+:/ { print $0 }'
}

inspect_pattern() {
    local category="$1"
    local pattern="$2"

    local cursor="0"
    local scanned=0
    local found=0

    printf '\n--- %s ---\n' "$category"
    printf 'Padrão: %s\n' "$pattern"

    while :; do
        local response
        local next_cursor
        local keys

        if ! response="$(redis_command SCAN "$cursor" MATCH "$pattern" COUNT "$SCAN_COUNT")"; then
            error "Falha ao executar SCAN para ${category}."
            return 1
        fi

        next_cursor="$(printf '%s\n' "$response" | sed -n '1p')"
        keys="$(printf '%s\n' "$response" | sed '1d')"

        while IFS= read -r key; do
            [[ -z "$key" ]] && continue

            found=$((found + 1))

            if (( found <= MAX_KEYS )); then
                local key_type
                local ttl

                key_type="$(redis_command TYPE "$key")"
                ttl="$(redis_command TTL "$key")"

                case "$ttl" in
                    -1) ttl_description="Sem expiração" ;;
                    -2) ttl_description="Chave inexistente" ;;
                    *) ttl_description="${ttl}s" ;;
                esac

                printf 'Chave: %s | Tipo: %s | TTL: %s\n' \
                    "$key" "$key_type" "$ttl_description"
            fi

            scanned=$((scanned + 1))
        done <<< "$keys"

        cursor="$next_cursor"

        if [[ "$cursor" == "0" ]] || (( found >= MAX_KEYS )); then
            break
        fi
    done

    TOTAL_KEYS=$((TOTAL_KEYS + found))

    if (( found == 0 )); then
        printf 'Nenhuma chave encontrada.\n'
    elif (( found > MAX_KEYS )); then
        printf 'Exibindo as primeiras %d chaves encontradas.\n' "$MAX_KEYS"
    fi

    printf 'Chaves encontradas: %d\n' "$found"
}

main() {
    require_command "$REDIS_CLI"
    require_command awk
    require_command sed

    validate_environment
    check_connection
    print_server_info

    if [[ "$KEY_PATTERN" != "*" ]]; then
        inspect_pattern "Busca personalizada" "$KEY_PATTERN"
    else
        inspect_pattern "Cache" "academicpass:cache:*"
        inspect_pattern "Sessões" "academicpass:session:*"
        inspect_pattern "Seleções" "academicpass:selection:*"
    fi

    printf '\n========== RESUMO ==========\n'
    printf 'Total de chaves encontradas: %d\n' "$TOTAL_KEYS"
    printf 'Banco Redis: %s\n' "$REDIS_DATABASE"
    printf '============================\n'
}

main "$@"
