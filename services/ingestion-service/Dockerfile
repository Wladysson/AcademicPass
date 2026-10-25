FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        gcc \
        g++ \
        make \
        pkg-config \
        librdkafka-dev \
        libsasl2-dev \
        libkrb5-dev \
        libgssapi-krb5-2 \
        libsasl2-2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY src/ ./src/

RUN groupadd --system ingestion \
    && useradd --system \
        --gid ingestion \
        --home-dir /app \
        --no-create-home \
        ingestion \
    && mkdir -p /app/data/pdfs \
    && chown -R ingestion:ingestion /app

USER ingestion

EXPOSE 8000

HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "ingestion.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
