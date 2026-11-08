#!/usr/bin/env bash

set -Eeuo pipefail

KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
KAFKA_BIN="${KAFKA_BIN:-/opt/kafka/bin}"
KAFKA_CONFIG="${KAFKA_CONFIG:-/etc/kafka/client.properties}"

readonly -a CONSUMER_GROUPS=(
    "academicpass-extraction-service"
    "academicpass-indexing-service"
    "academicpass-search-service"
    "academicpass-simulado-service"
)

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

fail() {
    log "ERRO: $1"
    exit 1
}

check_dependencies() {
    command -v "${KAFKA_BIN}/kafka-consumer-groups.sh" >/dev/null 2>&1 \
        || fail "kafka-consumer-groups.sh não encontrado em ${KAFKA_BIN}."

    command -v timeout >/dev/null 2>&1 \
        || fail "O comando timeout não está instalado."

    [[ -f "${KAFKA_CONFIG}" ]] \
        || fail "Arquivo de configuração do cliente não encontrado: ${KAFKA_CONFIG}."
}

kafka_command() {
    timeout 30s "${KAFKA_BIN}/kafka-consumer-groups.sh" "$@" \
        --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS}" \
        --command-config "${KAFKA_CONFIG}"
}

check_broker() {
    log "Verificando conexão com Kafka em ${KAFKA_BOOTSTRAP_SERVERS}..."

    kafka_command --list >/dev/null \
        || fail "Não foi possível estabelecer comunicação com o broker Kafka."

    log "Conexão com Kafka estabelecida."
}

show_group_lag() {
    local group="$1"

    log "Consultando consumer group: ${group}"

    if ! kafka_command --describe --group "${group}"; then
        log "Não foi possível consultar o consumer group ${group}."
        return 1
    fi
}

main() {
    log "Iniciando monitoramento de consumer lag do AcademicPass."

    check_dependencies
    check_broker

    for group in "${CONSUMER_GROUPS[@]}"; do
        show_group_lag "${group}" || true
        printf '\n'
    done

    log "Monitoramento de consumer lag concluído."
}

main "$@"
