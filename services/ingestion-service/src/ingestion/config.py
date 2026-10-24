from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    """Carrega e valida as configurações do ingestion-service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    #aplicação
    app_name: str = "academicpass-ingestion-service"
    app_environment: Literal["development", "testing", "staging", "production"] = (
        "development"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    #downloader
    downloader_timeout_seconds: float = Field(default=30.0, gt=0)
    downloader_max_file_size_mb: int = Field(default=50, gt=0)
    downloader_max_retries: int = Field(default=3, ge=0)
    downloader_chunk_size: int = Field(default=65536, gt=0)
    downloader_allowed_domains: str = ""

    #armazenamento
    storage_backend: Literal["minio", "local"] = "minio"
    storage_max_file_size_mb: int = Field(default=50, gt=0)

    #minIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: SecretStr = SecretStr("")
    minio_secret_key: SecretStr = SecretStr("")
    minio_bucket_name: str = "academicpass-pdfs"
    minio_secure: bool = False
    minio_region: str | None = None

    #volume local
    local_storage_path: str = "./data/pdfs"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "enade.pdfs.discovered"
    kafka_client_id: str = "academicpass-ingestion-service"
    kafka_delivery_timeout_seconds: float = Field(default=30.0, gt=0)
    kafka_request_timeout_ms: int = Field(default=10000, gt=0)

    # Segurança Kafka
    kafka_security_protocol: Literal[
        "PLAINTEXT",
        "SSL",
        "SASL_PLAINTEXT",
        "SASL_SSL",
    ] = "PLAINTEXT"

    kafka_sasl_mechanism: Literal[
        "PLAIN",
        "SCRAM-SHA-256",
        "SCRAM-SHA-512",
        "GSSAPI",
    ] | None = None

    kafka_sasl_username: str | None = None
    kafka_sasl_password: SecretStr | None = None
    kafka_kerberos_service_name: str = "kafka"
    kafka_ssl_ca_location: str | None = None

    # Observabilidade
    metrics_enabled: bool = True

    @field_validator("app_name", "minio_bucket_name", "kafka_topic")
    @classmethod
    def validar_identificadores_obrigatorios(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("O valor não pode ser vazio.")

        return normalized

    @field_validator("minio_endpoint", "kafka_bootstrap_servers")
    @classmethod
    def validar_endpoints(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("O endpoint deve ser informado.")

        return normalized

    @field_validator("local_storage_path")
    @classmethod
    def validar_caminho_local(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("O caminho do armazenamento local deve ser informado.")

        return normalized

    @field_validator("downloader_allowed_domains")
    @classmethod
    def normalizar_dominios_permitidos(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validar_configuracao_kafka(self) -> IngestionSettings:
        sasl_protocols = {"SASL_PLAINTEXT", "SASL_SSL"}

        if self.kafka_security_protocol in sasl_protocols:
            if self.kafka_sasl_mechanism is None:
                raise ValueError(
                    "É necessário informar kafka_sasl_mechanism "
                    "quando a segurança SASL estiver habilitada."
                )

        if self.kafka_sasl_mechanism in {"PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"}:
            if not self.kafka_sasl_username:
                raise ValueError(
                    "O usuário SASL deve ser informado para o mecanismo selecionado."
                )

            if self.kafka_sasl_password is None:
                raise ValueError(
                    "A senha SASL deve ser informada para o mecanismo selecionado."
                )

        if self.kafka_sasl_mechanism == "GSSAPI":
            if not self.kafka_kerberos_service_name.strip():
                raise ValueError(
                    "O serviço Kerberos do Kafka deve ser informado."
                )

        if self.storage_backend == "minio":
            if not self.minio_endpoint.strip():
                raise ValueError("O endpoint do MinIO deve ser informado.")

        return self

    @property
    def allowed_domains(self) -> tuple[str, ...]:
        """Retorna os domínios permitidos pelo downloader."""

        return tuple(
            domain.strip().lower()
            for domain in self.downloader_allowed_domains.split(",")
            if domain.strip()
        )

    @property
    def kafka_security_config(self) -> dict[str, str]:
        """Monta as configurações de segurança aceitas pelo librdkafka."""

        config: dict[str, str] = {
            "security.protocol": self.kafka_security_protocol,
        }

        if self.kafka_sasl_mechanism is not None:
            config["sasl.mechanism"] = self.kafka_sasl_mechanism

        if self.kafka_sasl_username:
            config["sasl.username"] = self.kafka_sasl_username

        if self.kafka_sasl_password is not None:
            config["sasl.password"] = self.kafka_sasl_password.get_secret_value()

        if self.kafka_sasl_mechanism == "GSSAPI":
            config["sasl.kerberos.service.name"] = (
                self.kafka_kerberos_service_name
            )

        if self.kafka_ssl_ca_location:
            config["ssl.ca.location"] = self.kafka_ssl_ca_location

        return config


@lru_cache(maxsize=1)
def get_settings() -> IngestionSettings:
    """retorna a instância compartilhada das configuraçao"""

    return IngestionSettings()
