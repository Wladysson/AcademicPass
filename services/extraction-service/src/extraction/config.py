from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExtractionConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    # Aplicação
    app_name: str = "AcademicPass Extraction Service"
    app_version: str = "1.0.0"
    environment: Literal["development", "testing", "staging", "production"] = (
        "development"
    )
    host: str = "0.0.0.0"
    port: int = Field(default=8082, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "extraction-service"
    kafka_input_topic: str = "enade.pdfs.discovered"
    kafka_output_topic: str = "enade.questions.structured"
    kafka_dlq_topic: str = "enade.extraction.dlq"
    kafka_client_id: str = "academicpass-extraction"

    kafka_auto_offset_reset: Literal["earliest", "latest", "error"] = "earliest"
    kafka_poll_timeout_seconds: float = Field(default=1.0, gt=0, le=60)
    kafka_session_timeout_ms: int = Field(default=45000, ge=6000)
    kafka_max_poll_interval_ms: int = Field(default=300000, ge=1000)

    kafka_security_protocol: str = "PLAINTEXT"
    kafka_sasl_mechanism: str | None = None
    kafka_sasl_username: str | None = None
    kafka_sasl_password: SecretStr | None = None
    kafka_sasl_kerberos_service_name: str | None = None
    kafka_kerberos_keytab: str | None = None
    kafka_kerberos_principal: str | None = None

    # Armazenamento de PDFs
    pdf_storage_backend: Literal["minio", "local"] = "minio"
    pdf_max_file_size_mb: int = Field(default=50, ge=1, le=1024)

    minio_endpoint: str = "localhost:9000"
    minio_access_key: SecretStr | None = None
    minio_secret_key: SecretStr | None = None
    minio_bucket_name: str = "enade-documents"
    minio_secure: bool = False
    minio_region: str | None = None

    pdf_storage_path: Path | None = None

    # Processamento de PDFs
    pdf_max_pages: int = Field(default=1000, ge=1)
    pdf_min_text_characters: int = Field(default=1, ge=0)
    pdf_preserve_whitespace: bool = True
    pdf_sort_blocks: bool = True
    pdf_extract_images_info: bool = True

    # Gemini / Google AI Studio
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_api_version: str = "v1beta"
    gemini_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    gemini_max_image_size_mb: int = Field(default=10, ge=1, le=50)

    # Resiliência
    retry_max_attempts: int = Field(default=3, ge=1, le=10)
    retry_initial_delay_seconds: float = Field(default=1.0, gt=0)
    retry_max_delay_seconds: float = Field(default=30.0, gt=0)
    retry_multiplier: float = Field(default=2.0, ge=1.0)
    retry_jitter: bool = True

    # Observabilidade
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"
    health_path: str = "/health"
    readiness_path: str = "/ready"

    @field_validator("kafka_bootstrap_servers")
    @classmethod
    def validate_kafka_servers(cls, value: str) -> str:
        servers = [server.strip() for server in value.split(",")]

        if not servers or any(not server for server in servers):
            raise ValueError("kafka_bootstrap_servers contém endereço inválido.")

        return ",".join(servers)

    @field_validator("kafka_security_protocol")
    @classmethod
    def normalize_security_protocol(cls, value: str) -> str:
        normalized = value.strip().upper()

        allowed = {
            "PLAINTEXT",
            "SSL",
            "SASL_PLAINTEXT",
            "SASL_SSL",
        }

        if normalized not in allowed:
            raise ValueError(
                f"kafka_security_protocol deve ser um destes valores: {allowed}."
            )

        return normalized

    @field_validator("minio_bucket_name")
    @classmethod
    def validate_bucket_name(cls, value: str) -> str:
        normalized = value.strip().lower()

        if not normalized:
            raise ValueError("minio_bucket_name não pode ser vazio.")

        if len(normalized) < 3 or len(normalized) > 63:
            raise ValueError("O nome do bucket deve possuir entre 3 e 63 caracteres.")

        return normalized

    @field_validator("metrics_path", "health_path", "readiness_path")
    @classmethod
    def validate_http_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("Os caminhos HTTP devem começar com '/'.")

        return value

    @model_validator(mode="after")
    def validate_storage_configuration(self) -> ExtractionConfig:
        if self.pdf_storage_backend == "minio":
            if not self.minio_access_key or not self.minio_secret_key:
                if self.environment == "production":
                    raise ValueError(
                        "Credenciais MinIO são obrigatórias em produção."
                    )

        if self.pdf_storage_backend == "local":
            if self.pdf_storage_path is None:
                raise ValueError(
                    "PDF_STORAGE_PATH é obrigatório para armazenamento local."
                )

        if self.kafka_security_protocol.startswith("SASL_"):
            if not self.kafka_sasl_mechanism:
                raise ValueError(
                    "KAFKA_SASL_MECHANISM é obrigatório para conexões SASL."
                )

            if self.kafka_sasl_mechanism.upper() != "GSSAPI":
                if not self.kafka_sasl_username or not self.kafka_sasl_password:
                    raise ValueError(
                        "Credenciais SASL são obrigatórias para o mecanismo configurado."
                    )

        if self.retry_max_delay_seconds < self.retry_initial_delay_seconds:
            raise ValueError(
                "O atraso máximo de retry não pode ser menor que o atraso inicial."
            )

        return self

    def kafka_consumer_config(self) -> dict:
        config = {
            "bootstrap.servers": self.kafka_bootstrap_servers,
            "group.id": self.kafka_consumer_group,
            "client.id": self.kafka_client_id,
            "auto.offset.reset": self.kafka_auto_offset_reset,
            "enable.auto.commit": False,
            "session.timeout.ms": self.kafka_session_timeout_ms,
            "max.poll.interval.ms": self.kafka_max_poll_interval_ms,
            "security.protocol": self.kafka_security_protocol,
        }

        if self.kafka_sasl_mechanism:
            config["sasl.mechanism"] = self.kafka_sasl_mechanism

        if self.kafka_sasl_username:
            config["sasl.username"] = self.kafka_sasl_username

        if self.kafka_sasl_password:
            config["sasl.password"] = self.kafka_sasl_password.get_secret_value()

        if self.kafka_sasl_kerberos_service_name:
            config["sasl.kerberos.service.name"] = (
                self.kafka_sasl_kerberos_service_name
            )

        return config

    def kafka_producer_config(self) -> dict:
        config = self.kafka_consumer_config()

        config.pop("group.id", None)
        config.pop("auto.offset.reset", None)
        config.pop("enable.auto.commit", None)
        config.pop("session.timeout.ms", None)
        config.pop("max.poll.interval.ms", None)

        config.update(
            {
                "client.id": f"{self.kafka_client_id}-producer",
                "acks": "all",
                "enable.idempotence": True,
            }
        )

        return config


@lru_cache(maxsize=1)
def get_config() -> ExtractionConfig:
    return ExtractionConfig()
