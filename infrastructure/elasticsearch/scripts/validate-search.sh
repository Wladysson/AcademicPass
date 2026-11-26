#!/usr/bin/env bash

set -Eeuo pipefail

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
ELASTICSEARCH_INDEX="${ELASTICSEARCH_INDEX:-enade-questions}"
ELASTICSEARCH_USERNAME="${ELASTICSEARCH_USERNAME:-elastic}"
ELASTICSEARCH_PASSWORD="${ELASTICSEARCH_PASSWORD:-}"
CURL_TIMEOUT="${CURL_TIMEOUT:-30}"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

AUTH_ARGS=()

log() {
    printf '[INFO] %s\n' "$1"
}

success() {
    printf '[PASS] %s\n' "$1"
    PASSED_TESTS=$((PASSED_TESTS + 1))
}

failure() {
    printf '[FAIL] %s\n' "$1"
    FAILED_TESTS=$((FAILED_TESTS + 1))
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf '[ERROR] Comando obrigatório não encontrado: %s\n' "$1" >&2
        exit 1
    fi
}

build_auth_args() {
    if [[ -n "$ELASTICSEARCH_USERNAME" ]]; then
        if [[ -z "$ELASTICSEARCH_PASSWORD" ]]; then
            printf '[ERROR] ELASTICSEARCH_PASSWORD não foi definida.\n' >&2
            exit 1
        fi

        AUTH_ARGS=(-u "${ELASTICSEARCH_USERNAME}:${ELASTICSEARCH_PASSWORD}")
    fi
}

request() {
    local method="$1"
    local endpoint="$2"
    local body="${3:-}"

    if [[ -n "$body" ]]; then
        curl --fail-with-body --silent --show-error \
            --connect-timeout "$CURL_TIMEOUT" \
            --max-time "$CURL_TIMEOUT" \
            "${AUTH_ARGS[@]}" \
            -X "$method" \
            -H "Content-Type: application/json" \
            --data-binary "$body" \
            "${ELASTICSEARCH_URL}${endpoint}"
    else
        curl --fail-with-body --silent --show-error \
            --connect-timeout "$CURL_TIMEOUT" \
            --max-time "$CURL_TIMEOUT" \
            "${AUTH_ARGS[@]}" \
            -X "$method" \
            "${ELASTICSEARCH_URL}${endpoint}"
    fi
}

run_test() {
    local description="$1"
    local endpoint="$2"
    local body="$3"
    local expected="$4"

    local response
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if ! response="$(request POST "$endpoint" "$body" 2>/dev/null)"; then
        failure "$description - falha na requisição Elasticsearch."
        return
    fi

    if jq -e "$expected" >/dev/null 2>&1 <<< "$response"; then
        success "$description"
    else
        failure "$description - resultado inesperado."
    fi
}

validate_index() {
    local response

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if ! response="$(request GET "/${ELASTICSEARCH_INDEX}" 2>/dev/null)"; then
        failure "Índice disponível."
        return 1
    fi

    if jq -e --arg index "$ELASTICSEARCH_INDEX" \
        'has($index)' >/dev/null <<< "$response"; then
        success "Índice disponível."
        return 0
    fi

    failure "Índice disponível."
    return 1
}

validate_analyzer() {
    local body

    body='{
      "analyzer": "brazilian",
      "text": "A educação brasileira transforma a sociedade."
    }'

    run_test \
        "Analyzer brazilian" \
        "/${ELASTICSEARCH_INDEX}/_analyze" \
        "$body" \
        '.tokens | length > 0'
}

validate_stemming() {
    local body

    body='{
      "analyzer": "brazilian",
      "text": "estudantes estudando estudos"
    }'

    run_test \
        "Stemming em português" \
        "/${ELASTICSEARCH_INDEX}/_analyze" \
        "$body" \
        '([.tokens[].token] | index("estud")) != null'
}

validate_synonyms() {
    local body

    body='{
      "analyzer": "brazilian_search",
      "text": "ensino superior"
    }'

    run_test \
        "Expansão de sinônimos" \
        "/${ELASTICSEARCH_INDEX}/_analyze" \
        "$body" \
        '([.tokens[].token] | index("educação")) != null'
}

validate_highlight() {
    local document_id="validation-$(date +%s)-$$"
    local document

    document='{
      "question_id": "'"$document_id"'",
      "document_id": "validation-document",
      "question_number": 1,
      "statement": "A educação superior contribui para a formação acadêmica.",
      "alternatives": [],
      "topics": ["educação"]
    }'

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if ! request PUT \
        "/${ELASTICSEARCH_INDEX}/_doc/${document_id}?refresh=wait_for" \
        "$document" >/dev/null 2>&1; then
        failure "Inserção de documento para highlight."
        return
    fi

    local query

    query='{
      "query": {
        "match": {
          "statement": "educação"
        }
      },
      "highlight": {
        "fields": {
          "statement": {}
        }
      }
    }'

    local response

    if ! response="$(request POST \
        "/${ELASTICSEARCH_INDEX}/_search" "$query" 2>/dev/null)"; then
        failure "Highlight de resultados."
        request DELETE \
            "/${ELASTICSEARCH_INDEX}/_doc/${document_id}?refresh=wait_for" \
            >/dev/null 2>&1 || true
        return
    fi

    if jq -e \
        '.hits.hits[0].highlight.statement | length > 0' \
        >/dev/null 2>&1 <<< "$response"; then
        success "Highlight de resultados."
    else
        failure "Highlight de resultados."
    fi

    request DELETE \
        "/${ELASTICSEARCH_INDEX}/_doc/${document_id}?refresh=wait_for" \
        >/dev/null 2>&1 || true
}

print_summary() {
    printf '\n'
    printf '%s\n' "========== RESULTADO DA VALIDAÇÃO =========="
    printf 'Total: %d\n' "$TOTAL_TESTS"
    printf 'Aprovados: %d\n' "$PASSED_TESTS"
    printf 'Falhas: %d\n' "$FAILED_TESTS"
    printf '%s\n' "============================================"

    if (( FAILED_TESTS > 0 )); then
        exit 1
    fi

    log "Todas as validações foram concluídas."
}

main() {
    require_command curl
    require_command jq

    build_auth_args

    log "Validando índice ${ELASTICSEARCH_INDEX}..."

    if ! validate_index; then
        print_summary
        exit 1
    fi

    validate_analyzer
    validate_stemming
    validate_synonyms
    validate_highlight

    print_summary
}

main "$@"
