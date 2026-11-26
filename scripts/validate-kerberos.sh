#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KERBEROS_DIR="$ROOT_DIR/infra/kerberos"
KEYTAB_DIR="$KERBEROS_DIR/keytabs"

echo "Iniciando validação do Kerberos..."

if ! command -v kinit >/dev/null 2>&1; then
    echo "Erro: kinit não está instalado."
    exit 1
fi

if ! command -v klist >/dev/null 2>&1; then
    echo "Erro: klist não está instalado."
    exit 1
fi

if [[ ! -f "$KERBEROS_DIR/krb5.conf" ]]; then
    echo "Erro: krb5.conf não encontrado."
    exit 1
fi

if [[ ! -d "$KEYTAB_DIR" ]]; then
    echo "Erro: diretório de keytabs não encontrado."
    exit 1
fi

export KRB5_CONFIG="$KERBEROS_DIR/krb5.conf"

KEYTAB_COUNT=0

for keytab in "$KEYTAB_DIR"/*.keytab; do
    [[ -f "$keytab" ]] || continue

    KEYTAB_COUNT=$((KEYTAB_COUNT + 1))

    echo "Validando: $(basename "$keytab")"

    klist -kte "$keytab"

done

if [[ "$KEYTAB_COUNT" -eq 0 ]]; then
    echo "Erro: nenhum keytab encontrado."
    exit 1
fi

echo "Verificando autenticação Kerberos..."

for keytab in "$KEYTAB_DIR"/*.keytab; do
    [[ -f "$keytab" ]] || continue

    PRINCIPAL="$(klist -kte "$keytab" | awk 'NR == 4 {print $NF}')"

    if [[ -z "$PRINCIPAL" ]]; then
        echo "Erro: não foi possível identificar o principal em $(basename "$keytab")."
        exit 1
    fi

    echo "Autenticando: $PRINCIPAL"

    kinit -kt "$keytab" "$PRINCIPAL"
    klist
    kdestroy
done

echo "Validação Kerberos concluída."
