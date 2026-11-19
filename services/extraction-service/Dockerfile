FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Dependências do sistema necessárias para bibliotecas Python.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        gcc \
        g++ \
        librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências da aplicação.
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia somente o código do serviço.
COPY src/ ./src/

# Usuário sem privilégios administrativos.
RUN groupadd --system extraction \
    && useradd --system --gid extraction --no-create-home extraction \
    && chown -R extraction:extraction /app

USER extraction

EXPOSE 8082

CMD ["python", "-m", "extraction.main"]
