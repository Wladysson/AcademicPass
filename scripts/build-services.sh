#!/usr/bin/env bash

set -Eeuo pipefail

# ==========================================
# AcademicPass - Build Services
# ==========================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker/docker-compose.services.yml"

# ==========================================
# Service registry
# ==========================================

declare -A SERVICES=(
    [identity]="identity-service"
    [ingestion]="ingestion-service"
    [extraction]="extraction-service"
    [indexing]="indexing-service"
    [search]="search-service"
    [selection]="question-selection-service"
    [simulado]="simulado-service"
    [gateway]="api-gateway"
    [web]="web"
)

# ==========================================
# Logging
# ==========================================

log() {
    printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

success() {
    printf '[OK] %s\n' "$*"
}

error() {
    printf '[ERRO] %s\n' "$*" >&2
}

# ==========================================
# Validation
# ==========================================

check_prerequisites() {
    command -v docker >/dev/null 2>&1 ||
        {
            error "Docker não encontrado."
            exit 1
        }

    docker compose version >/dev/null 2>&1 ||
        {
            error "Docker Compose v2 não está disponível."
            exit 1
        }

    docker info >/dev/null 2>&1 ||
        {
            error "Docker daemon não está acessível."
            exit 1
        }

    [[ -f "$COMPOSE_FILE" ]] ||
        {
            error "Compose não encontrado: $COMPOSE_FILE"
            exit 1
        }

    docker compose -f "$COMPOSE_FILE" config --quiet ||
        {
            error "Configuração Docker Compose inválida."
            exit 1
        }
}

validate_service() {
    local service="$1"

    [[ -n "${SERVICES[$service]:-}" ]] ||
        {
            error "Serviço desconhecido: $service"
            show_usage
            exit 1
        }
}

# ==========================================
# Build
# ==========================================

build_service() {
    local service_key="$1"
    local compose_service="${SERVICES[$service_key]}"

    log "Construindo imagem: $compose_service"

    docker compose \
        -f "$COMPOSE_FILE" \
        build "$compose_service" ||
        {
            error "Falha ao construir $compose_service."
            return 1
        }

    success "Imagem construída: $compose_service"
}

build_all() {
    local service
    local failures=0

    log "Iniciando build das imagens do AcademicPass"

    for service in identity ingestion extraction indexing search selection simulado gateway web; do
        if ! build_service "$service"; then
            failures=$((failures + 1))
        fi
    done

    if (( failures > 0 )); then
        error "$failures serviço(s) apresentaram falha durante o build."
        return 1
    fi

    success "Todas as imagens foram construídas com sucesso"
}

# ==========================================
# Usage
# ==========================================

show_usage() {
    cat <<'EOF'
Uso:
  ./scripts/build-services.sh [opção] [serviço]

Opções:
  --all                 Constrói todas as imagens
  --service <nome>      Constrói uma imagem específica
  --no-cache            Constrói sem utilizar cache
  --help                Exibe esta ajuda

Serviços disponíveis:
  identity
  ingestion
  extraction
  indexing
  search
  selection
  simulado
  gateway
  web

Exemplos:
  ./scripts/build-services.sh --all
  ./scripts/build-services.sh --service identity
  ./scripts/build-services.sh --service extraction
  ./scripts/build-services.sh --all --no-cache
EOF
}

# ==========================================
# Main
# ==========================================

main() {
    local mode="all"
    local selected_service=""
    local no_cache=false

    while (($# > 0)); do
        case "$1" in
            --all)
                mode="all"
                shift
                ;;
            --service)
                [[ $# -ge 2 ]] || {
                    error "Informe o nome do serviço."
                    show_usage
                    exit 1
                }

                mode="service"
                selected_service="$2"
                shift 2
                ;;
            --no-cache)
                no_cache=true
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                error "Argumento desconhecido: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    check_prerequisites

    if [[ "$no_cache" == true ]]; then
        export BUILDKIT_INLINE_CACHE=0
        export DOCKER_BUILD_NO_CACHE=1
    fi

    if [[ "$mode" == "service" ]]; then
        validate_service "$selected_service"

        if [[ "$no_cache" == true ]]; then
            docker compose \
                -f "$COMPOSE_FILE" \
                build --no-cache "${SERVICES[$selected_service]}"
        else
            build_service "$selected_service"
        fi
    else
        if [[ "$no_cache" == true ]]; then
            docker compose \
                -f "$COMPOSE_FILE" \
                build --no-cache
        else
            build_all
        fi
    fi
}

main "$@"
