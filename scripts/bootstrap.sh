set -Eeuo pipefail

# ==========================================
# AcademicPass - Bootstrap
# ==========================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker/docker-compose.infra.yml"

KAFKA_TOPICS_SCRIPT="${ROOT_DIR}/infra/kafka/scripts/create-topics.sh"
ELASTICSEARCH_INDEX_SCRIPT="${ROOT_DIR}/infra/elasticsearch/scripts/create-index.sh"
LDAP_BOOTSTRAP_SCRIPT="${ROOT_DIR}/infra/ldap/scripts/bootstrap-ldap.sh"
KERBEROS_PRINCIPALS_SCRIPT="${ROOT_DIR}/infra/kerberos/scripts/create-principals.sh"
KERBEROS_KEYTABS_SCRIPT="${ROOT_DIR}/infra/kerberos/scripts/create-keytabs.sh"
MINIO_INIT_SCRIPT="${ROOT_DIR}/infra/minio/config/minio-init.sh"

WAIT_TIMEOUT="${BOOTSTRAP_WAIT_TIMEOUT:-180}"
POLL_INTERVAL=5

# ==========================================
# Logging
# ==========================================

log() {
    printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

success() {
    printf '[OK] %s\n' "$*"
}

warning() {
    printf '[AVISO] %s\n' "$*" >&2
}

error() {
    printf '[ERRO] %s\n' "$*" >&2
}

fail() {
    error "$*"
    exit 1
}

# ==========================================
# Prerequisites
# ==========================================

check_command() {
    command -v "$1" >/dev/null 2>&1 ||
        fail "Comando obrigatório não encontrado: $1"
}

check_file() {
    [[ -f "$1" ]] ||
        fail "Arquivo obrigatório não encontrado: $1"
}

check_directory() {
    [[ -d "$1" ]] ||
        fail "Diretório obrigatório não encontrado: $1"
}

check_prerequisites() {
    log "Validando pré-requisitos"

    check_command docker
    check_command curl
    check_command bash

    docker compose version >/dev/null 2>&1 ||
        fail "Docker Compose v2 não está disponível."

    docker info >/dev/null 2>&1 ||
        fail "O Docker daemon não está acessível."

    check_file "$COMPOSE_FILE"

    check_file "${ROOT_DIR}/shared/contracts/kafka-topics.yaml"

    check_file "${ROOT_DIR}/infra/elasticsearch/indices/questions-settings.json"
    check_file "${ROOT_DIR}/infra/elasticsearch/indices/questions-mapping.json"

    check_file "${ROOT_DIR}/infra/ldap/bootstrap/01-base.ldif"
    check_file "${ROOT_DIR}/infra/ldap/bootstrap/02-groups.ldif"
    check_file "${ROOT_DIR}/infra/ldap/bootstrap/03-users.ldif"

    check_file "${ROOT_DIR}/infra/kerberos/config/kdc.conf"
    check_file "${ROOT_DIR}/infra/kerberos/config/krb5.conf"
    check_file "${ROOT_DIR}/infra/kerberos/config/kadm5.acl"

    check_file "$KAFKA_TOPICS_SCRIPT"
    check_file "$ELASTICSEARCH_INDEX_SCRIPT"
    check_file "$LDAP_BOOTSTRAP_SCRIPT"
    check_file "$KERBEROS_PRINCIPALS_SCRIPT"
    check_file "$KERBEROS_KEYTABS_SCRIPT"
    check_file "$MINIO_INIT_SCRIPT"

    success "Pré-requisitos e arquivos de configuração encontrados"
}

# ==========================================
# Compose
# ==========================================

compose() {
    docker compose -f "$COMPOSE_FILE" "$@"
}

validate_compose() {
    log "Validando configuração Docker Compose"

    compose config --quiet ||
        fail "A configuração do Docker Compose contém erros."

    success "Docker Compose validado"
}

start_service() {
    local service="$1"

    log "Iniciando serviço: $service"

    compose up -d "$service" ||
        fail "Não foi possível iniciar o serviço $service."
}

wait_service_running() {
    local service="$1"
    local elapsed=0

    log "Aguardando container: $service"

    while (( elapsed < WAIT_TIMEOUT )); do
        if [[ -n "$(compose ps --status running -q "$service" 2>/dev/null)" ]]; then
            success "$service está em execução"
            return 0
        fi

        if [[ -n "$(compose ps --status exited -q "$service" 2>/dev/null)" ]]; then
            compose logs --tail=50 "$service" >&2 || true
            fail "O serviço $service encerrou durante a inicialização."
        fi

        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
    done

    compose logs --tail=50 "$service" >&2 || true
    fail "Timeout aguardando o serviço $service."
}

wait_http() {
    local url="$1"
    local description="$2"
    local elapsed=0

    log "Aguardando disponibilidade: $description"

    while (( elapsed < WAIT_TIMEOUT )); do
        if curl --silent --fail "$url" >/dev/null 2>&1; then
            success "$description está disponível"
            return 0
        fi

        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
    done

    fail "Timeout aguardando $description em $url."
}

# ==========================================
# Infrastructure
# ==========================================

start_infrastructure() {
    log "Iniciando infraestrutura do AcademicPass"

    compose up -d \
        elasticsearch \
        redis \
        minio \
        ldap \
        kerberos \
        prometheus \
        grafana

    wait_service_running elasticsearch
    wait_service_running redis
    wait_service_running minio
    wait_service_running ldap
    wait_service_running kerberos

    wait_http "http://localhost:9200/_cluster/health" "Elasticsearch"

    success "Infraestrutura inicial iniciada"
}

# ==========================================
# Kerberos
# ==========================================

configure_kerberos() {
    log "Configurando Kerberos"

    bash "$KERBEROS_PRINCIPALS_SCRIPT" ||
        fail "Falha ao criar principals Kerberos."

    bash "$KERBEROS_KEYTABS_SCRIPT" ||
        fail "Falha ao gerar keytabs Kerberos."

    success "Procedimentos de Kerberos executados"
}

# ==========================================
# LDAP
# ==========================================

configure_ldap() {
    log "Configurando diretório LDAP"

    bash "$LDAP_BOOTSTRAP_SCRIPT" ||
        fail "Falha durante a configuração do LDAP."

    success "Procedimento de bootstrap LDAP executado"
}

# ==========================================
# MinIO
# ==========================================

configure_minio() {
    log "Configurando armazenamento MinIO"

    bash "$MINIO_INIT_SCRIPT" ||
        fail "Falha durante a inicialização do MinIO."

    success "Procedimento de inicialização do MinIO executado"
}

# ==========================================
# Kafka
# ==========================================

configure_kafka() {
    log "Iniciando Kafka"

    start_service kafka
    wait_service_running kafka

    log "Criando tópicos e DLQs"

    bash "$KAFKA_TOPICS_SCRIPT" ||
        fail "Falha durante a criação dos tópicos Kafka."

    success "Procedimento de criação dos tópicos executado"
}

# ==========================================
# Elasticsearch
# ==========================================

configure_elasticsearch() {
    log "Configurando índice de questões"

    wait_http "http://localhost:9200/_cluster/health" "Elasticsearch"

    bash "$ELASTICSEARCH_INDEX_SCRIPT" ||
        fail "Falha durante a criação do índice Elasticsearch."

    success "Procedimento de criação do índice executado"
}

# ==========================================
# Bootstrap execution
# ==========================================

main() {
    log "AcademicPass - Inicialização da infraestrutura"

    check_prerequisites
    validate_compose

    start_infrastructure

    configure_kerberos
    configure_ldap
    configure_minio

    configure_kafka
    configure_elasticsearch

    log "Bootstrap finalizado"

    compose ps

    success "Infraestrutura do AcademicPass inicializada"
}

main "$@"
