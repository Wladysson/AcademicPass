#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TOOL="${1:-}"

case "$TOOL" in
    locust)
        TEST_DIR="$ROOT_DIR/tests/load/locust"

        if ! command -v locust >/dev/null 2>&1; then
            echo "Erro: Locust não está instalado."
            exit 1
        fi

        if [[ ! -f "$TEST_DIR/locustfile.py" ]]; then
            echo "Erro: locustfile.py não encontrado em $TEST_DIR"
            exit 1
        fi

        echo "Iniciando testes de carga com Locust..."
        cd "$TEST_DIR"
        locust -f locustfile.py
        ;;

    k6)
        TEST_FILE="$ROOT_DIR/tests/load/k6/load-test.js"

        if ! command -v k6 >/dev/null 2>&1; then
            echo "Erro: k6 não está instalado."
            exit 1
        fi

        if [[ ! -f "$TEST_FILE" ]]; then
            echo "Erro: arquivo load-test.js não encontrado."
            exit 1
        fi

        echo "Iniciando testes de carga com k6..."
        k6 run "$TEST_FILE"
        ;;

    *)
        echo "Uso: $0 {locust|k6}"
        exit 1
        ;;
esac
