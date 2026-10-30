FROM python:3.12-slim

# Configurações do ambiente Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

# Diretório de trabalho
WORKDIR /app

# Dependências do sistema
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        librdkafka1 \
    && rm -rf /var/lib/apt/lists/*

# Instalação das dependências Python
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY src/ ./src/

# Usuário não privilegiado
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && chown -R app:app /app

USER app

# Porta HTTP do serviço
EXPOSE 8084

# Verificação de saúde do processo HTTP
HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8084/health', timeout=3)" || exit 1

# Inicialização da aplicação
CMD ["uvicorn", "indexing.main:app", "--host", "0.0.0.0", "--port", "8084"]
