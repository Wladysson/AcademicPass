from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch import ApiError, NotFoundError


logger = logging.getLogger(__name__)

DEFAULT_INDEX = "academicpass-questions"


class IndexManagerError(Exception):
    """Erro durante o gerenciamento de índices."""


class IndexMappingError(IndexManagerError):
    """Mapping incompatível com a estrutura esperada."""


class IndexManager:
    """Gerencia a criação e validação do índice de questões."""

    def __init__(
        self,
        client: Elasticsearch | Any,
        index_name: str = DEFAULT_INDEX,
        number_of_shards: int = 1,
        number_of_replicas: int = 0,
        refresh_interval: str = "5s",
    ) -> None:
        if client is None:
            raise ValueError("O cliente Elasticsearch é obrigatório.")

        if not self._validar_nome_indice(index_name):
            raise ValueError(
                f"Nome de índice inválido: {index_name!r}."
            )

        if number_of_shards < 1:
            raise ValueError(
                "number_of_shards deve ser maior que zero."
            )

        if number_of_replicas < 0:
            raise ValueError(
                "number_of_replicas não pode ser negativo."
            )

        if not isinstance(refresh_interval, str) or not refresh_interval.strip():
            raise ValueError("refresh_interval não pode ser vazio.")

        self._client = (
            client.obter_cliente()
            if hasattr(client, "obter_cliente")
            else client
        )

        self._index_name = index_name
        self._number_of_shards = number_of_shards
        self._number_of_replicas = number_of_replicas
        self._refresh_interval = refresh_interval

    @property
    def index_name(self) -> str:
        return self._index_name

    @staticmethod
    def _validar_nome_indice(index_name: str) -> bool:
        if not isinstance(index_name, str):
            return False

        if not index_name or len(index_name) > 255:
            return False

        if index_name != index_name.lower():
            return False

        if index_name in {".", ".."}:
            return False

        if index_name.startswith(("-", "_", "+")):
            return False

        return all(
            character.isalnum() or character in "._-"
            for character in index_name
        )

    def obter_settings(self) -> dict[str, Any]:
        """Retorna as configurações esperadas para o índice."""
        return {
            "number_of_shards": self._number_of_shards,
            "number_of_replicas": self._number_of_replicas,
            "refresh_interval": self._refresh_interval,
            "analysis": {
                "analyzer": {
                    "academicpass_portuguese": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "asciifolding",
                            "brazilian_stop",
                            "brazilian_stemmer",
                        ],
                    }
                },
                "filter": {
                    "brazilian_stop": {
                        "type": "stop",
                        "stopwords": "_brazilian_",
                    },
                    "brazilian_stemmer": {
                        "type": "stemmer",
                        "language": "brazilian",
                    },
                },
            },
        }

    def obter_mapping(self) -> dict[str, Any]:
        """Retorna a definição dos campos do índice."""
        return {
            "dynamic": True,
            "properties": {
                "question_id": {
                    "type": "keyword",
                },
                "event_id": {
                    "type": "keyword",
                },
                "event_type": {
                    "type": "keyword",
                },
                "schema_version": {
                    "type": "keyword",
                },
                "published_at": {
                    "type": "date",
                    "format": "strict_date_optional_time||epoch_millis",
                },
                "document_checksum": {
                    "type": "keyword",
                },
                "storage_key": {
                    "type": "keyword",
                },
                "question_number": {
                    "type": "integer",
                },
                "question_type": {
                    "type": "keyword",
                },
                "statement": {
                    "type": "text",
                    "analyzer": "academicpass_portuguese",
                    "fields": {
                        "raw": {
                            "type": "keyword",
                            "ignore_above": 512,
                        }
                    },
                },
                "base_text": {
                    "type": "text",
                    "analyzer": "academicpass_portuguese",
                },
                "alternatives": {
                    "type": "nested",
                    "properties": {
                        "label": {
                            "type": "keyword",
                        },
                        "text": {
                            "type": "text",
                            "analyzer": "academicpass_portuguese",
                        },
                    },
                },
                "correct_answer": {
                    "type": "keyword",
                },
                "answer_status": {
                    "type": "keyword",
                },
                "start_page": {
                    "type": "integer",
                },
                "end_page": {
                    "type": "integer",
                },
                "metadata": {
                    "type": "object",
                    "dynamic": True,
                    "properties": {
                        "area": {
                            "type": "keyword",
                        },
                        "course": {
                            "type": "keyword",
                        },
                        "course_name": {
                            "type": "keyword",
                        },
                        "course_code": {
                            "type": "keyword",
                        },
                        "edition_year": {
                            "type": "integer",
                        },
                        "document_type": {
                            "type": "keyword",
                        },
                        "exam_component": {
                            "type": "keyword",
                        },
                        "competencies": {
                            "type": "nested",
                            "dynamic": True,
                        },
                    },
                },
                "formulas": {
                    "type": "object",
                    "dynamic": True,
                },
                "diagrams": {
                    "type": "object",
                    "dynamic": True,
                },
                "tables": {
                    "type": "object",
                    "dynamic": True,
                },
                "search_text": {
                    "type": "text",
                    "analyzer": "academicpass_portuguese",
                },
            },
        }

    def indice_existe(self) -> bool:
        """Verifica a existência do índice configurado."""
        try:
            return bool(
                self._client.indices.exists(
                    index=self._index_name
                )
            )
        except ApiError as exc:
            raise IndexManagerError(
                "Não foi possível verificar a existência do índice."
            ) from exc

    def criar_indice(self) -> bool:
        """Cria o índice utilizando as configurações e mappings definidos."""
        if self.indice_existe():
            logger.info(
                "O índice %s já existe.",
                self._index_name,
            )
            return False

        body = {
            "settings": self.obter_settings(),
            "mappings": self.obter_mapping(),
        }

        try:
            self._client.indices.create(
                index=self._index_name,
                **body,
            )

            logger.info(
                "Índice %s criado com sucesso.",
                self._index_name,
            )

            return True

        except ApiError as exc:
            if self._is_resource_already_exists(exc):
                logger.info(
                    "O índice %s foi criado por outra operação.",
                    self._index_name,
                )
                return False

            raise IndexManagerError(
                f"Não foi possível criar o índice {self._index_name}."
            ) from exc

    def garantir_indice(self) -> bool:
        """Garante a existência do índice e valida seu mapping."""
        created = self.criar_indice()
        self.validar_mapping()

        return created

    def validar_mapping(self) -> bool:
        """Valida os campos e tipos do mapping existente."""
        try:
            response = self._client.indices.get_mapping(
                index=self._index_name
            )
        except NotFoundError as exc:
            raise IndexManagerError(
                f"O índice {self._index_name} não existe."
            ) from exc
        except ApiError as exc:
            raise IndexManagerError(
                "Não foi possível consultar o mapping do índice."
            ) from exc

        index_mapping = self._extrair_mapping(response)

        expected_mapping = self.obter_mapping()
        expected_properties = expected_mapping["properties"]

        actual_properties = index_mapping.get("properties", {})

        if not isinstance(actual_properties, Mapping):
            raise IndexMappingError(
                "O índice não possui uma estrutura válida de properties."
            )

        errors: list[str] = []

        self._comparar_campos(
            expected_properties,
            actual_properties,
            "",
            errors,
        )

        if errors:
            raise IndexMappingError(
                "O mapping do índice apresenta incompatibilidades: "
                + "; ".join(errors)
            )

        logger.info(
            "Mapping do índice %s validado com sucesso.",
            self._index_name,
        )

        return True

    def _extrair_mapping(
        self,
        response: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Extrai o mapping correspondente ao índice configurado."""
        index_data = response.get(self._index_name)

        if not isinstance(index_data, Mapping):
            raise IndexMappingError(
                "A resposta do Elasticsearch não contém o índice esperado."
            )

        mappings = index_data.get("mappings")

        if not isinstance(mappings, Mapping):
            raise IndexMappingError(
                "O índice não possui um mapping válido."
            )

        return mappings

    def _comparar_campos(
        self,
        expected: Mapping[str, Any],
        actual: Mapping[str, Any],
        parent: str,
        errors: list[str],
    ) -> None:
        """Compara recursivamente os campos esperados e existentes."""
        for field_name, expected_definition in expected.items():
            field_path = (
                f"{parent}.{field_name}"
                if parent
                else field_name
            )

            actual_definition = actual.get(field_name)

            if not isinstance(actual_definition, Mapping):
                errors.append(
                    f"Campo obrigatório ausente: {field_path}"
                )
                continue

            expected_type = expected_definition.get("type")
            actual_type = actual_definition.get("type")

            if expected_type != actual_type:
                errors.append(
                    f"Tipo incompatível em {field_path}: "
                    f"esperado={expected_type}, encontrado={actual_type}"
                )
                continue

            expected_analyzer = expected_definition.get("analyzer")

            if (
                expected_analyzer is not None
                and actual_definition.get("analyzer") != expected_analyzer
            ):
                errors.append(
                    f"Analyzer incompatível em {field_path}."
                )

            expected_fields = expected_definition.get("fields", {})
            actual_fields = actual_definition.get("fields", {})

            if expected_fields:
                if not isinstance(actual_fields, Mapping):
                    errors.append(
                        f"Subcampos ausentes em {field_path}."
                    )
                else:
                    self._comparar_campos(
                        expected_fields,
                        actual_fields,
                        field_path,
                        errors,
                    )

            expected_properties = expected_definition.get(
                "properties",
                {},
            )
            actual_properties = actual_definition.get(
                "properties",
                {},
            )

            if expected_properties:
                if not isinstance(actual_properties, Mapping):
                    errors.append(
                        f"Propriedades ausentes em {field_path}."
                    )
                else:
                    self._comparar_campos(
                        expected_properties,
                        actual_properties,
                        field_path,
                        errors,
                    )

    @staticmethod
    def _is_resource_already_exists(exc: ApiError) -> bool:
        """Identifica conflito de criação por índice já existente."""
        body = getattr(exc, "body", None)

        if not isinstance(body, Mapping):
            return False

        error = body.get("error")

        if isinstance(error, Mapping):
            return error.get("type") == "resource_already_exists_exception"

        return False

    def obter_informacoes(self) -> dict[str, Any]:
        """Retorna informações básicas do índice."""
        try:
            response = self._client.indices.get(
                index=self._index_name
            )

            index_data = response.get(self._index_name, {})

            return {
                "index": self._index_name,
                "settings": index_data.get("settings", {}),
                "mappings": index_data.get("mappings", {}),
            }

        except NotFoundError as exc:
            raise IndexManagerError(
                f"O índice {self._index_name} não existe."
            ) from exc
        except ApiError as exc:
            raise IndexManagerError(
                "Não foi possível obter informações do índice."
            ) from exc
