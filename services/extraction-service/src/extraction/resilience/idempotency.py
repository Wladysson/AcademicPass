from __future__ import annotations

import hashlib
import json
import re

from dataclasses import dataclass
from typing import Any


class IdempotencyError(Exception):
    """Erro relacionado ao controle de idempotência."""


class InvalidIdempotencyKeyError(IdempotencyError):
    """Dados inválidos para geração de identificadores."""


@dataclass(frozen=True)
class IdempotencyKey:
    document_checksum: str
    page_number: int
    question_number: int
    identifier: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-fA-F0-9]{64}", self.document_checksum):
            raise InvalidIdempotencyKeyError(
                "O checksum deve possuir 64 caracteres hexadecimais."
            )

        if self.page_number < 1:
            raise InvalidIdempotencyKeyError(
                "O número da página deve ser positivo."
            )

        if self.question_number < 1:
            raise InvalidIdempotencyKeyError(
                "O número da questão deve ser positivo."
            )

        if not re.fullmatch(r"[a-fA-F0-9]{64}", self.identifier):
            raise InvalidIdempotencyKeyError(
                "O identificador deve ser um SHA-256 válido."
            )


class IdempotencyManager:

    HASH_ALGORITHM = "sha256"
    IDENTIFIER_VERSION = "v1"

    @classmethod
    def generate_key(
        cls,
        document_checksum: str,
        page_number: int,
        question_number: int,
    ) -> IdempotencyKey:
        """Gera uma chave determinística por documento, página e questão."""

        checksum = cls._normalize_checksum(document_checksum)

        cls._validate_positive_integer(
            page_number,
            "page_number",
        )

        cls._validate_positive_integer(
            question_number,
            "question_number",
        )

        payload = {
            "version": cls.IDENTIFIER_VERSION,
            "document_checksum": checksum,
            "page_number": page_number,
            "question_number": question_number,
        }

        identifier = cls._generate_hash(payload)

        return IdempotencyKey(
            document_checksum=checksum,
            page_number=page_number,
            question_number=question_number,
            identifier=identifier,
        )

    @classmethod
    def generate_document_key(
        cls,
        document_checksum: str,
    ) -> str:
        """gera um identificador determinístico para o documento"""

        checksum = cls._normalize_checksum(document_checksum)

        payload = {
            "version": cls.IDENTIFIER_VERSION,
            "document_checksum": checksum,
        }

        return cls._generate_hash(payload)

    @classmethod
    def generate_question_key(
        cls,
        document_checksum: str,
        question_number: int,
    ) -> str:
        """gera um identificador para uma questão sem localizacao"""

        checksum = cls._normalize_checksum(document_checksum)

        cls._validate_positive_integer(
            question_number,
            "question_number",
        )

        payload = {
            "version": cls.IDENTIFIER_VERSION,
            "document_checksum": checksum,
            "question_number": question_number,
        }

        return cls._generate_hash(payload)

    @classmethod
    def is_same_question(
        cls,
        first: IdempotencyKey,
        second: IdempotencyKey,
    ) -> bool:
        """verifica se duas chaves representam a mesma questão"""

        return first.identifier == second.identifier

    @classmethod
    def _generate_hash(cls, payload: dict[str, Any]) -> str:
        try:
            serialized = json.dumps(
                payload,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")

            return hashlib.sha256(serialized).hexdigest()

        except (TypeError, ValueError) as error:
            raise IdempotencyError(
                "Não foi possível gerar o identificador determinístico."
            ) from error

    @staticmethod
    def _normalize_checksum(checksum: str) -> str:
        if not isinstance(checksum, str):
            raise InvalidIdempotencyKeyError(
                "O checksum deve ser uma string."
            )

        normalized = checksum.strip().lower()

        if not re.fullmatch(r"[a-f0-9]{64}", normalized):
            raise InvalidIdempotencyKeyError(
                "Checksum SHA-256 inválido."
            )

        return normalized

    @staticmethod
    def _validate_positive_integer(
        value: int,
        field_name: str,
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise InvalidIdempotencyKeyError(
                f"{field_name} deve ser um inteiro positivo."
            )
