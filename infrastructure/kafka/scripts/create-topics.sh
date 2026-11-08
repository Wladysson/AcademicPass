#!/usr/bin/env bash

set -Eeuo pipefail

KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
KAFKA_BIN="${KAFKA_BIN:-/opt/kafka/bin}"
KAFKA_CONFIG="${KAFKA_CONFIG:-/etc/kafka/client.properties}"

PARTITIONS="${KAFKA_TOPIC_PARTITIONS:-3}"
REPLICATION_FACTOR="${KAFKA_TOPIC_REPLICATION_FACTOR:-1}"

readonly -a TOPICS=(
    "enade.pdfs.discovered"
    "enade.pdfs.discovered.dlq"
    "enade.questions.extracted"
    "enade.questions.extracted.dlq"
    "enade.questions.indexed"
    "enade.questions.indexed.dlq"
    "enade.simulados.requested"
    "enade.simulados.requested.dlq"
    "enade.simulados.completed"
    "enade.simulados.completed.dlq"
)

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

fail() {
    log "ERRO: $1"
    exit 1
}

check_dependencies() {
    command -v "${KAFKA_BIN}/kafka-topics.sh" >/dev/null 2>&1 \
        || fail "kafka-topics.sh não encontrado em ${KAFKA_BIN}."

    command -v timeout >/dev/null 2>&1 \
        || fail "O comando timeout não está instalado."

    [[ "${PARTITIONS}" =~ ^[1-9][0-9]*$ ]] \
        || fail "Número de partições inválido: ${PARTITIONS}."

    [[ "${REPLICATION_FACTOR}" =~ ^[1-9][0-9]*$ ]] \
        || fail "Fator de replicação inválido: ${REPLICATION_FACTOR}."

    [[ -f "${KAFKA_CONFIG}" ]] \
        || fail "Arquivo de configuração do cliente não encontrado: ${KAFKA_CONFIG}."
}

kafka_command() {
    timeout 30s "${KAFKA_BIN}/kafka-topics.sh" "$@" \
        --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS}" \
        --command-config "${KAFKA_CONFIG}"
}

check_broker() {
    log "Verificando conexão com Kafka em ${KAFKA_BOOTSTRAP_SERVERS}..."

    kafka_command --list >/dev/null \
        || fail "Não foi possível estabelecer comunicação com o broker Kafka."

    log "Conexão com Kafka estabelecida."
}

create_topic() {
    local topic="$1"

    if kafka_command --describe --topic "${topic}" >/dev/null 2>&1; then
        log "Tópico já existe: ${topic}"
        return 0
    fi

    log "Criando tópico: ${topic}"

    kafka_command \
        --create \
        --topic "${topic}" \
        --partitions "${PARTITIONS}" \
        --replication-factor "${REPLICATION_FACTOR}" \
        --config cleanup.policy=delete \
        --config retention.ms=604800000 \
        --config compression.type=producer \
        --if-not-exists \
        || fail "Falha ao criar o tópico ${topic}."

    log "Tópico criado: ${topic}"
}

main() {
    log "Iniciando configuração dos tópicos do AcademicPass."

    check_dependencies
    check_broker

    for topic in "${TOPICS[@]}"; do
        create_topic "${topic}"
    done

    log "Todos os tópicos foram verificados."
}

main "$@"
