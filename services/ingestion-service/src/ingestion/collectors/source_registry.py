from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse


class SourceRegistryError(Exception):
    """Erro relacionado ao cadastro de fontes documentais."""


class RegisteredDocumentType(str, Enum):
    EXAM = "exam"
    ANSWER_KEY = "answer_key"
    GUIDELINE = "guideline"


@dataclass(frozen=True, slots=True)
class DocumentSource:
    document_type: RegisteredDocumentType
    url: str
    file_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.document_type, RegisteredDocumentType):
            raise SourceRegistryError(
                "O tipo de documento informado é inválido."
            )

        if not self.url or not self.url.strip():
            raise SourceRegistryError(
                "A URL da fonte documental é obrigatória."
            )

        parsed_url = urlparse(self.url)

        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise SourceRegistryError(
                "A fonte documental deve utilizar uma URL HTTPS válida."
            )

        if parsed_url.username or parsed_url.password:
            raise SourceRegistryError(
                "URLs com credenciais embutidas não são permitidas."
            )

        if self.file_name is not None:
            if not self.file_name.strip():
                raise SourceRegistryError(
                    "O nome do arquivo não pode ser vazio."
                )

            if "/" in self.file_name or "\\" in self.file_name:
                raise SourceRegistryError(
                    "O nome do arquivo não pode conter separadores."
                )


@dataclass(frozen=True, slots=True)
class EnadeEdition:
    year: int
    sources: tuple[DocumentSource, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.year, int) or isinstance(self.year, bool):
            raise SourceRegistryError(
                "O ano da edição deve ser um número inteiro."
            )

        if self.year < 2004:
            raise SourceRegistryError(
                "O ano informado não corresponde a uma edição válida do ENADE."
            )

        if not self.sources:
            raise SourceRegistryError(
                "A edição precisa possuir pelo menos uma fonte documental."
            )

        document_types = [
            source.document_type for source in self.sources
        ]

        if len(document_types) != len(set(document_types)):
            raise SourceRegistryError(
                "Uma edição não pode possuir fontes duplicadas "
                "para o mesmo tipo de documento."
            )

    def buscar_fonte(
        self,
        document_type: RegisteredDocumentType,
    ) -> DocumentSource | None:
        return next(
            (
                source
                for source in self.sources
                if source.document_type == document_type
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class EnadeCourse:
    code: str
    name: str
    editions: tuple[EnadeEdition, ...]

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise SourceRegistryError(
                "O código do curso é obrigatório."
            )

        if not self.name or not self.name.strip():
            raise SourceRegistryError(
                "O nome do curso é obrigatório."
            )

        if not self.editions:
            raise SourceRegistryError(
                "O curso precisa possuir pelo menos uma edição cadastrada."
            )

        years = [edition.year for edition in self.editions]

        if len(years) != len(set(years)):
            raise SourceRegistryError(
                "Não é permitido cadastrar edições duplicadas para o curso."
            )

    def buscar_edicao(self, year: int) -> EnadeEdition | None:
        return next(
            (
                edition
                for edition in self.editions
                if edition.year == year
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class EnadeSource:
    source_id: str
    name: str
    base_url: str
    official: bool
    courses: tuple[EnadeCourse, ...]

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_id.strip():
            raise SourceRegistryError(
                "O identificador da fonte é obrigatório."
            )

        if not self.name or not self.name.strip():
            raise SourceRegistryError(
                "O nome da fonte é obrigatório."
            )

        parsed_url = urlparse(self.base_url)

        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise SourceRegistryError(
                "A URL principal da fonte deve utilizar HTTPS."
            )

        if parsed_url.username or parsed_url.password:
            raise SourceRegistryError(
                "A URL principal não pode conter credenciais."
            )

        if not isinstance(self.official, bool):
            raise SourceRegistryError(
                "O indicador de fonte oficial deve ser booleano."
            )

        if not self.courses:
            raise SourceRegistryError(
                "A fonte precisa possuir pelo menos um curso cadastrado."
            )

        course_codes = [course.code for course in self.courses]

        if len(course_codes) != len(set(course_codes)):
            raise SourceRegistryError(
                "Não é permitido cadastrar cursos duplicados na mesma fonte."
            )


@dataclass(slots=True)
class SourceRegistry:
    sources: dict[str, EnadeSource] = field(default_factory=dict)

    def registrar(self, source: EnadeSource) -> None:
        if not isinstance(source, EnadeSource):
            raise SourceRegistryError(
                "O registro precisa ser uma instância de EnadeSource."
            )

        if source.source_id in self.sources:
            raise SourceRegistryError(
                f"A fonte '{source.source_id}' já está cadastrada."
            )

        self.sources[source.source_id] = source

    def remover(self, source_id: str) -> None:
        if source_id not in self.sources:
            raise SourceRegistryError(
                f"A fonte '{source_id}' não está cadastrada."
            )

        del self.sources[source_id]

    def buscar_fonte(self, source_id: str) -> EnadeSource:
        source = self.sources.get(source_id)

        if source is None:
            raise SourceRegistryError(
                f"Fonte documental '{source_id}' não encontrada."
            )

        return source

    def listar_fontes(self) -> tuple[EnadeSource, ...]:
        return tuple(self.sources.values())

    def buscar_curso(
        self,
        source_id: str,
        course_code: str,
    ) -> EnadeCourse:
        source = self.buscar_fonte(source_id)

        course = next(
            (
                course
                for course in source.courses
                if course.code == course_code
            ),
            None,
        )

        if course is None:
            raise SourceRegistryError(
                f"Curso '{course_code}' não encontrado na fonte "
                f"'{source_id}'."
            )

        return course

    def buscar_edicao(
        self,
        source_id: str,
        course_code: str,
        year: int,
    ) -> EnadeEdition:
        course = self.buscar_curso(source_id, course_code)
        edition = course.buscar_edicao(year)

        if edition is None:
            raise SourceRegistryError(
                f"Edição {year} não encontrada para o curso "
                f"'{course_code}'."
            )

        return edition

    def listar_cursos(
        self,
        source_id: str,
    ) -> tuple[EnadeCourse, ...]:
        source = self.buscar_fonte(source_id)
        return source.courses

    def listar_edicoes(
        self,
        source_id: str,
        course_code: str,
    ) -> tuple[EnadeEdition, ...]:
        course = self.buscar_curso(source_id, course_code)
        return course.editions

    def buscar_documento(
        self,
        source_id: str,
        course_code: str,
        year: int,
        document_type: RegisteredDocumentType,
    ) -> DocumentSource:
        edition = self.buscar_edicao(
            source_id=source_id,
            course_code=course_code,
            year=year,
        )

        document = edition.buscar_fonte(document_type)

        if document is None:
            raise SourceRegistryError(
                f"Documento do tipo '{document_type.value}' "
                f"não encontrado para a edição {year}."
            )

        return document
