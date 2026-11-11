#!/usr/bin/env bash

set -Eeuo pipefail

KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
KAFKA_SECURITY_PROTOCOL="${KAFKA_SECURITY_PROTOCOL:-SASL_PLAINTEXT}"
KAFKA_SERVICE_NAME="${KAFKA_SERVICE_NAME:-kafka}"
KAFKA_PRINCIPAL="${KAFKA_PRINCIPAL:-kafka-client@ACADEMICPASS.LOCAL}"
KAFKA_KEYTAB="${KAFKA_KEYTAB:-/etc/academicpass/keytabs/kafka.principals.keytab}"
KRB5_CONFIG="${KRB5_CONFIG:-/etc/krb5.conf}"

KINIT_CMD="${KINIT_CMD:-kinit}"
KLIST_CMD="${KLIST_CMD:-klist}"
KAFKA_API_VERSIONS_CMD="${KAFKA_API_VERSIONS_CMD:-kafka-broker-api-versions.sh}"

TEMP_CONFIG=""

log() {
    printf '[INFO] %s\n' "$1"
}

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

cleanup() {
    if [[ -n "$TEMP_CONFIG" ]]; then
        rm -f -- "$TEMP_CONFIG"
    fi

    "$KINIT_CMD" -R >/dev/null 2>&1 || true
}

trap cleanup EXIT

for command_name in \
    "$KINIT_CMD" \
    "$KLIST_CMD" \
    "$KAFKA_API_VERSIONS_CMD"; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        error "Comando não encontrado: $command_name"
        exit 1
    fi
done

if [[ ! -f "$KRB5_CONFIG" ]]; then
    error "Configuração Kerberos não encontrada: $KRB5_CONFIG"
    exit 1
fi

if [[ ! -r "$KAFKA_KEYTAB" ]]; then
    error "Keytab inexistente ou sem permissão de leitura: $KAFKA_KEYTAB"
    exit 1
fi

if [[ -z "$KAFKA_BOOTSTRAP_SERVERS" || "$KAFKA_BOOTSTRAP_SERVERS" == *$'\n'* ]]; then
    error "Endereço de bootstrap Kafka inválido."
    exit 1
fi

if [[ ! "$KAFKA_SECURITY_PROTOCOL" =~ ^(SASL_PLAINTEXT|SASL_SSL)$ ]]; then
    error "KAFKA_SECURITY_PROTOCOL deve ser SASL_PLAINTEXT ou SASL_SSL."
    exit 1
fi

if [[ ! "$KAFKA_SERVICE_NAME" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    error "Nome do serviço Kafka inválido."
    exit 1
fi

if [[ ! "$KAFKA_PRINCIPAL" =~ ^[a-zA-Z0-9._/-]+@ACADEMICPASS\.LOCAL$ ]]; then
    error "Principal Kafka inválido: $KAFKA_PRINCIPAL"
    exit 1
fi

export KRB5_CONFIG

log "Obtendo ticket Kerberos para $KAFKA_PRINCIPAL"

if ! "$KINIT_CMD" -kt "$KAFKA_KEYTAB" "$KAFKA_PRINCIPAL"; then
    error "Falha na autenticação Kerberos via keytab."
    exit 1
fi

if ! "$KLIST_CMD" -s; then
    error "Nenhum ticket Kerberos válido foi encontrado."
    exit 1
fi

TEMP_CONFIG="$(mktemp)"
chmod 0600 "$TEMP_CONFIG"

cat > "$TEMP_CONFIG" <<EOF
security.protocol=${KAFKA_SECURITY_PROTOCOL}
sasl.mechanism=GSSAPI
sasl.kerberos.service.name=${KAFKA_SERVICE_NAME}
sasl.jaas.config=com.sun.security.auth.module.Krb5LoginModule required useKeyTab=true storeKey=true doNotPrompt=true useTicketCache=false keyTab="${KAFKA_KEYTAB}" principal="${KAFKA_PRINCIPAL}";
EOF

log "Testando comunicação SASL/GSSAPI com Kafka em $KAFKA_BOOTSTRAP_SERVERS"

if "$KAFKA_API_VERSIONS_CMD" \
    --bootstrap-server "$KAFKA_BOOTSTRAP_SERVERS" \
    --command-config "$TEMP_CONFIG"; then
    log "Autenticação Kerberos e comunicação com Kafka validadas."
else
    error "Falha na comunicação autenticada com Kafka."
    exit 1
fi
