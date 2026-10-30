from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class IndexingSettings(BaseSettings):
    """Configurações de execução do serviço de indexação."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    # Aplicação
    service_name: str = Field(
        default="academicpass-indexing-service",
        validation_alias="SERVICE_NAME",
    )

    service_version: str = Field(
        default="1.0.0",
        validation_alias="SERVICE_VERSION",
    )

    environment: str = Field(
        default="development",
        validation_alias="ENVIRONMENT",
    )

    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )

    api_host: str = Field(
        default="0.0.0.0",
        validation_alias="API_HOST",
    )

    api_port: int = Field(
        default=8084,
        ge=1,
        le=65535,
        validation_alias="API_PORT",
    )

    # Kafka
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        validation_alias="KAFKA_BOOTSTRAP_SERVERS",
    )

    kafka_group_id: str = Field(
        default="academicpass-indexing-group",
        validation_alias="KAFKA_GROUP_ID",
    )

    kafka_input_topic: str = Field(
        default="enade.questions.structured",
        validation_alias="KAFKA_INPUT_TOPIC",
    )

    kafka_dlq_topic: str = Field(
        default="enade.indexing.dlq",
        validation_alias="KAFKA_DLQ_TOPIC",
    )

    kafka_security_protocol: str = Field(
        default="",
        validation_alias="KAFKA_SECURITY_PROTOCOL",
    )

    kafka_sasl_mechanism: str = Field(
        default="",
        validation_alias="KAFKA_SASL_MECHANISM",
    )

    kafka_kerberos_service_name: str = Field(
        default="",
        validation_alias="KAFKA_KERBEROS_SERVICE_NAME",
    )

    kafka_kerberos_principal: str = Field(
        default="",
        validation_alias="KAFKA_KERBEROS_PRINCIPAL",
    )

    kafka_kerberos_keytab: SecretStr | None = Field(
        default=None,
        validation_alias="KAFKA_KERBEROS_KEYTAB",
    )

    consumer_poll_timeout: float = Field(
        default=1.0,
        gt=0,
        validation_alias="CONSUMER_POLL_TIMEOUT",
    )

    # Elasticsearch
    elasticsearch_url: str = Field(
        default="http://localhost:9200",
        validation_alias="ELASTICSEARCH_URL",
    )

    elasticsearch_username: str = Field(
        default="",
        validation_alias="ELASTICSEARCH_USERNAME",
    )

    elasticsearch_password: SecretStr | None = Field(
        default=None,
        validation_alias="ELASTICSEARCH_PASSWORD",
    )

    elasticsearch_index: str = Field(
        default="academicpass-questions",
        validation_alias="ELASTICSEARCH_INDEX",
    )

    elasticsearch_request_timeout: float = Field(
        default=10.0,
        gt=0,
        validation_alias="ELASTICSEARCH_REQUEST_TIMEOUT",
    )

    elasticsearch_max_retries: int = Field(
        default=3,
        ge=0,
        validation_alias="ELASTICSEARCH_MAX_RETRIES",
    )

    # Resiliência
    max_retry_attempts: int = Field(
        default=3,
        ge=1,
        validation_alias="MAX_RETRY_ATTEMPTS",
    )

    retry_initial_delay_seconds: float = Field(
        default=1.0,
        ge=0,
        validation_alias="RETRY_INITIAL_DELAY_SECONDS",
    )

    retry_max_delay_seconds: float = Field(
        default=30.0,
        ge=0,
        validation_alias="RETRY_MAX_DELAY_SECONDS",
    )

    dlq_publication_timeout: float = Field(
        default=10.0,
        gt=0,
        validation_alias="DLQ_PUBLICATION_TIMEOUT",
    )

    # Indexação
    bulk_chunk_size: int = Field(
        default=500,
        ge=1,
        validation_alias="BULK_CHUNK_SIZE",
    )

    bulk_max_chunk_bytes: int = Field(
        default=5 * 1024 * 1024,
        ge=1,
        validation_alias="BULK_MAX_CHUNK_BYTES",
    )

    # Observabilidade
    metrics_namespace: str = Field(
        default="academicpass",
        validation_alias="METRICS_NAMESPACE",
    )

    metrics_subsystem: str = Field(
        default="indexing",
        validation_alias="METRICS_SUBSYSTEM",
    )

    @model_validator(mode="after")
    def validar_configuracoes(self) -> Self:
        """Valida a consistência entre as configurações."""

        if (
            self.elasticsearch_username
            and self.elasticsearch_password is None
        ):
            raise ValueError(
                "ELASTICSEARCH_PASSWORD é obrigatório quando "
                "ELASTICSEARCH_USERNAME está configurado."
            )

        if (
            self.elasticsearch_password is not None
            and not self.elasticsearch_username
        ):
            raise ValueError(
                "ELASTICSEARCH_USERNAME é obrigatório quando "
                "ELASTICSEARCH_PASSWORD está configurado."
            )

        if (
            self.retry_max_delay_seconds
            < self.retry_initial_delay_seconds
        ):
            raise ValueError(
                "RETRY_MAX_DELAY_SECONDS não pode ser menor que "
                "RETRY_INITIAL_DELAY_SECONDS."
            )

        if self.kafka_security_protocol:
            protocolos_validos = {
                "PLAINTEXT",
                "SSL",
                "SASL_PLAINTEXT",
                "SASL_SSL",
            }

            if (
                self.kafka_security_protocol.upper()
                not in protocolos_validos
            ):
                raise ValueError(
                    "KAFKA_SECURITY_PROTOCOL inválido."
                )

        if (
            self.kafka_sasl_mechanism
            and not self.kafka_security_protocol.upper().startswith("SASL")
        ):
            raise ValueError(
                "KAFKA_SASL_MECHANISM exige um protocolo SASL."
            )

        if (
            self.kafka_sasl_mechanism.upper() == "GSSAPI"
            and not self.kafka_kerberos_service_name
        ):
            raise ValueError(
                "KAFKA_KERBEROS_SERVICE_NAME é obrigatório "
                "quando o mecanismo SASL é GSSAPI."
            )

        return self

    @property
    def elasticsearch_password_value(self) -> str | None:
        """Retorna a senha do Elasticsearch sem expô-la no repr."""

        if self.elasticsearch_password is None:
            return None

        return self.elasticsearch_password.get_secret_value()

    @property
    def kafka_kerberos_keytab_value(self) -> str | None:
        """Retorna o caminho do keytab configurado."""

        if self.kafka_kerberos_keytab is None:
            return None

        return self.kafka_kerberos_keytab.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> IndexingSettings:
    """Retorna uma instância compartilhada das configurações."""

    return IndexingSettings()
