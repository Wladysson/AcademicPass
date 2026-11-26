#!/usr/bin/env bash

set -Eeuo pipefail

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
ELASTICSEARCH_PRINCIPAL="${ELASTICSEARCH_PRINCIPAL:-elasticsearch-client@ACADEMICPASS.LOCAL}"
ELASTICSEARCH_KEYTAB="${ELASTICSEARCH_KEYTAB:-/etc/academicpass/keytabs/elasticsearch.keytab}"
KRB5_CONFIG="${KRB5_CONFIG:-/etc/krb5.conf}"

KINIT_CMD="${KINIT_CMD:-kinit}"
KLIST_CMD="${KLIST_CMD:-klist}"
KDESTROY_CMD="${KDESTROY_CMD:-kdestroy}"
CURL_CMD="${CURL_CMD:-curl}"

TEMP_RESPONSE=""

log() {
    printf '[INFO] %s\n' "$1"
}

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

cleanup() {
    if [[ -n "$TEMP_RESPONSE" ]]; then
        rm -f -- "$TEMP_RESPONSE"
    fi

    "$KDESTROY_CMD" -q >/dev/null 2>&1 || true
}

trap cleanup EXIT

for command_name in \
    "$KINIT_CMD" \
    "$KLIST_CMD" \
    "$KDESTROY_CMD" \
    "$CURL_CMD"; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        error "Comando não encontrado: $command_name"
        exit 1
    fi
done

if [[ ! -f "$KRB5_CONFIG" ]]; then
    error "Configuração Kerberos não encontrada: $KRB5_CONFIG"
    exit 1
fi

if [[ ! -r "$ELASTICSEARCH_KEYTAB" ]]; then
    error "Keytab inexistente ou sem permissão de leitura: $ELASTICSEARCH_KEYTAB"
    exit 1
fi

if [[ ! "$ELASTICSEARCH_PRINCIPAL" =~ ^[a-zA-Z0-9._/-]+@ACADEMICPASS\.LOCAL$ ]]; then
    error "Principal Elasticsearch inválido: $ELASTICSEARCH_PRINCIPAL"
    exit 1
fi

if [[ ! "$ELASTICSEARCH_URL" =~ ^https?://[^[:space:]]+$ ]]; then
    error "URL do Elasticsearch inválida: $ELASTICSEARCH_URL"
    exit 1
fi

export KRB5_CONFIG

log "Obtendo ticket Kerberos para $ELASTICSEARCH_PRINCIPAL"

if ! "$KINIT_CMD" -kt "$ELASTICSEARCH_KEYTAB" "$ELASTICSEARCH_PRINCIPAL"; then
    error "Falha na autenticação Kerberos via keytab."
    exit 1
fi

if ! "$KLIST_CMD" -s; then
    error "Nenhum ticket Kerberos válido foi encontrado."
    exit 1
fi

TEMP_RESPONSE="$(mktemp)"

log "Testando autenticação SPNEGO no Elasticsearch: $ELASTICSEARCH_URL"

if ! HTTP_STATUS="$("$CURL_CMD" \
    --negotiate \
    --user : \
    --silent \
    --show-error \
    --fail-with-body \
    --output "$TEMP_RESPONSE" \
    --write-out '%{http_code}' \
    --connect-timeout 5 \
    --max-time 20 \
    "${ELASTICSEARCH_URL%/}/_security/_authenticate")"; then
    error "Falha na requisição autenticada ao Elasticsearch."

    if [[ -s "$TEMP_RESPONSE" ]]; then
        cat "$TEMP_RESPONSE" >&2
        printf '\n' >&2
    fi

    exit 1
fi

if [[ "$HTTP_STATUS" != "200" ]]; then
    error "Resposta HTTP inesperada: $HTTP_STATUS"
    cat "$TEMP_RESPONSE" >&2
    exit 1
fi

if command -v jq >/dev/null 2>&1; then
    if ! jq -e '.username and .authentication_realm.type == "kerberos"' \
        "$TEMP_RESPONSE" >/dev/null; then
        error "A resposta não confirmou uma identidade autenticada pelo realm Kerberos."
        cat "$TEMP_RESPONSE" >&2
        exit 1
    fi

    AUTHENTICATED_USER="$(jq -r '.username' "$TEMP_RESPONSE")"
    AUTHENTICATION_REALM="$(jq -r '.authentication_realm.name // "não informado"' "$TEMP_RESPONSE")"

    log "Usuário autenticado: $AUTHENTICATED_USER"
    log "Realm de autenticação: $AUTHENTICATION_REALM"
else
    log "Resposta HTTP 200 recebida. Instale jq para validar os campos da resposta."
    cat "$TEMP_RESPONSE"
fi

log "Autenticação Kerberos no Elasticsearch validada."
