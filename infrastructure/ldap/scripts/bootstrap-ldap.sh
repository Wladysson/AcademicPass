#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP_DIR="$(cd -- "${SCRIPT_DIR}/../bootstrap" && pwd)"

LDAP_HOST="${LDAP_HOST:-localhost}"
LDAP_PORT="${LDAP_PORT:-389}"
LDAP_URL="${LDAP_URL:-ldap://${LDAP_HOST}:${LDAP_PORT}}"

LDAP_ADMIN_DN="${LDAP_ADMIN_DN:-cn=admin,dc=example,dc=org}"
LDAP_BASE_DN="${LDAP_BASE_DN:-dc=example,dc=org}"

LDAP_ADMIN_PASSWORD="${LDAP_ADMIN_PASSWORD:-}"

LDAP_STARTTLS="${LDAP_STARTTLS:-false}"
LDAP_NETWORK_TIMEOUT="${LDAP_NETWORK_TIMEOUT:-10}"

LDAPADD="${LDAPADD:-ldapadd}"
LDAPMODIFY="${LDAPMODIFY:-ldapmodify}"
LDAPSEARCH="${LDAPSEARCH:-ldapsearch}"

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

validate_environment() {
    if [[ -z "$LDAP_ADMIN_PASSWORD" ]]; then
        error "Defina LDAP_ADMIN_PASSWORD antes de executar o bootstrap."
        exit 1
    fi

    if ! [[ "$LDAP_PORT" =~ ^[0-9]+$ ]] ||
       (( LDAP_PORT < 1 || LDAP_PORT > 65535 )); then
        error "LDAP_PORT inválida."
        exit 1
    fi

    if ! [[ "$LDAP_NETWORK_TIMEOUT" =~ ^[0-9]+$ ]] ||
       (( LDAP_NETWORK_TIMEOUT < 1 )); then
        error "LDAP_NETWORK_TIMEOUT deve ser maior que zero."
        exit 1
    fi
}

ldap_common_args() {
    LDAP_ARGS=(
        -x
        -H "$LDAP_URL"
        -D "$LDAP_ADMIN_DN"
        -w "$LDAP_ADMIN_PASSWORD"
        -o "nettimeout=${LDAP_NETWORK_TIMEOUT}"
    )

    if [[ "$LDAP_STARTTLS" == "true" ]]; then
        LDAP_ARGS+=(-ZZ)
    fi
}

check_connection() {
    log "Verificando conexão com OpenLDAP..."

    if ! "$LDAPSEARCH" "${LDAP_ARGS[@]}" \
        -b "$LDAP_BASE_DN" \
        -s base \
        dn >/dev/null 2>&1; then
        error "Não foi possível consultar o diretório LDAP."
        error "Verifique endereço, credenciais e existência da base DN."
        exit 1
    fi

    log "Conexão LDAP estabelecida."
}

entry_exists() {
    local dn="$1"

    "$LDAPSEARCH" "${LDAP_ARGS[@]}" \
        -b "$dn" \
        -s base \
        dn >/dev/null 2>&1
}

apply_base() {
    local file="${BOOTSTRAP_DIR}/01-base.ldif"

    if entry_exists "$LDAP_BASE_DN"; then
        log "Estrutura base já existe. Etapa ignorada."
        return
    fi

    log "Aplicando estrutura base do LDAP..."

    "$LDAPADD" "${LDAP_ARGS[@]}" -f "$file"

    log "Estrutura base criada."
}

apply_groups() {
    local file="${BOOTSTRAP_DIR}/02-groups.ldif"

    if entry_exists "cn=STUDENT,ou=Groups,${LDAP_BASE_DN}" &&
       entry_exists "cn=PROFESSOR,ou=Groups,${LDAP_BASE_DN}"; then
        log "Grupos STUDENT e PROFESSOR já existem. Etapa ignorada."
        return
    fi

    log "Criando grupos de autorização..."

    if entry_exists "cn=STUDENT,ou=Groups,${LDAP_BASE_DN}" ||
       entry_exists "cn=PROFESSOR,ou=Groups,${LDAP_BASE_DN}"; then
        error "Foi encontrada uma inicialização parcial dos grupos."
        error "Verifique as entradas existentes antes de continuar."
        exit 1
    fi

    "$LDAPADD" "${LDAP_ARGS[@]}" -f "$file"

    log "Grupos criados."
}

apply_users() {
    local file="${BOOTSTRAP_DIR}/03-users.ldif"
    local student_dn="uid=student.test,ou=People,${LDAP_BASE_DN}"
    local professor_dn="uid=professor.test,ou=People,${LDAP_BASE_DN}"
    local admin_dn="cn=directory-admin,${LDAP_BASE_DN}"

    if entry_exists "$student_dn" &&
       entry_exists "$professor_dn" &&
       entry_exists "$admin_dn"; then
        log "Usuários de teste já existem. Etapa ignorada."
        return
    fi

    if entry_exists "$student_dn" ||
       entry_exists "$professor_dn" ||
       entry_exists "$admin_dn"; then
        error "Foi encontrada uma inicialização parcial dos usuários."
        error "Verifique as entradas existentes antes de continuar."
        exit 1
    fi

    log "Criando usuários locais de teste e associações..."

    # O arquivo contém registros de adição e modificações de grupos.
    "$LDAPMODIFY" -a "${LDAP_ARGS[@]}" -f "$file"

    log "Usuários e associações criados."
}

main() {
    require_command "$LDAPADD"
    require_command "$LDAPMODIFY"
    require_command "$LDAPSEARCH"

    validate_environment
    ldap_common_args
    check_connection

    apply_base
    apply_groups
    apply_users

    log "Bootstrap LDAP concluído."
}

main "$@"
