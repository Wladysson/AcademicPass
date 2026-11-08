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
    log "Verificando conexão com Kafka..."

    kafka_command --list >/dev/null \
        || fail "Não foi possível estabelecer comunicação com o broker Kafka."

    log "Conexão com Kafka estabelecida."
}

register_consumer_group() {
    local group="$1"

    if kafka_command --describe --group "${group}" >/dev/null 2>&1; then
        log "Consumer group já registrado ou existente: ${group}"
    else
        log "Registrando consumer group: ${group}"

        kafka_command \
            --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS}" \
            --command-config "${KAFKA_CONFIG}" \
            --group "${group}" \
            --topic "__consumer_offsets" \
            --reset-offsets \
            --to-earliest \
            --dry-run >/dev/null 2>&1 \
            || log "Consumer group ${group} ainda não possui offsets ou consumidores ativos."
    fi
}

main() {
    log "Iniciando verificação dos consumer groups do AcademicPass."

    check_dependencies
    check_broker

    for group in "${CONSUMER_GROUPS[@]}"; do
        register_consumer_group "${group}"
    done

    log "Verificação dos consumer groups concluída."
    log "Os grupos serão efetivamente inicializados quando seus consumidores se conectarem."
}

main "$@"
