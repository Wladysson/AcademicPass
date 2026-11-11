import logging
import os
import random
import signal
import time
from typing import Any

import requests
from prometheus_client import Gauge, start_http_server


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("academicpass.extraction-quality")


ELASTICSEARCH_URL = os.getenv(
    "ELASTICSEARCH_URL",
    "http://elasticsearch:9200",
).rstrip("/")

ELASTICSEARCH_INDEX = os.getenv(
    "ELASTICSEARCH_INDEX",
    "enade-questions",
)

ELASTICSEARCH_USERNAME = os.getenv("ELASTICSEARCH_USERNAME")
ELASTICSEARCH_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD")
ELASTICSEARCH_API_TOKEN = os.getenv("ELASTICSEARCH_API_TOKEN")

SAMPLE_SIZE = max(
    50,
    int(os.getenv("EXTRACTION_QUALITY_SAMPLE_SIZE", "50")),
)

COLLECTION_INTERVAL = int(
    os.getenv("EXTRACTION_QUALITY_INTERVAL", "300")
)

REQUEST_TIMEOUT = int(
    os.getenv("EXTRACTION_QUALITY_TIMEOUT", "30")
)

METRICS_PORT = int(
    os.getenv("EXTRACTION_QUALITY_METRICS_PORT", "9205")
)

MIN_VALID_QUALITY_RATE = float(
    os.getenv("EXTRACTION_QUALITY_MIN_VALID_RATE", "0.95")
)

running = True


SAMPLED_QUESTIONS = Gauge(
    "academicpass_extraction_quality_sampled_questions",
    "Quantidade de questões avaliadas na última amostra.",
)

VALID_QUESTIONS = Gauge(
    "academicpass_extraction_quality_valid_questions",
    "Quantidade de questões aprovadas na validação estrutural.",
)

INVALID_QUESTIONS = Gauge(
    "academicpass_extraction_quality_invalid_questions",
    "Quantidade de questões reprovadas na validação estrutural.",
)

QUALITY_RATE = Gauge(
    "academicpass_extraction_quality_rate",
    "Percentual de questões aprovadas na validação estrutural.",
)

FIELD_VALIDATION_RATE = Gauge(
    "academicpass_extraction_field_validation_rate",
    "Percentual de questões aprovadas em cada validação de campo.",
    ["field"],
)

VALIDATION_FAILURES = Gauge(
    "academicpass_extraction_validation_failures",
    "Quantidade de falhas encontradas por tipo de validação.",
    ["field"],
)

SAMPLE_SUFFICIENT = Gauge(
    "academicpass_extraction_quality_sample_sufficient",
    "Indica se a amostra possui pelo menos 50 questões.",
)

QUALITY_THRESHOLD_MET = Gauge(
    "academicpass_extraction_quality_threshold_met",
    "Indica se a taxa de qualidade atingiu o limite configurado.",
)

COLLECTION_ERRORS = Gauge(
    "academicpass_extraction_quality_collection_errors",
    "Indica se ocorreu erro na última coleta: 1 para erro e 0 para sucesso.",
)

COLLECTION_DURATION = Gauge(
    "academicpass_extraction_quality_collection_duration_seconds",
    "Duração da última avaliação de qualidade.",
)

LAST_COLLECTION_TIMESTAMP = Gauge(
    "academicpass_extraction_quality_last_collection_timestamp",
    "Timestamp Unix da última coleta bem-sucedida.",
)


VALIDATION_FIELDS = (
    "question_id",
    "statement",
    "exam_metadata",
    "source_metadata",
    "alternatives",
)


def stop_collector(signum: int, frame: Any) -> None:
    global running

    logger.info("Recebido sinal de encerramento: %s", signum)
    running = False


def create_session() -> requests.Session:
    session = requests.Session()

    if ELASTICSEARCH_API_TOKEN:
        session.headers.update({
            "Authorization": f"Bearer {ELASTICSEARCH_API_TOKEN}",
        })
    elif ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD:
        session.auth = (
            ELASTICSEARCH_USERNAME,
            ELASTICSEARCH_PASSWORD,
        )

    session.headers.update({
        "Content-Type": "application/json",
    })

    return session


def fetch_random_sample(
    session: requests.Session,
) -> list[dict[str, Any]]:
    response = session.post(
        f"{ELASTICSEARCH_URL}/{ELASTICSEARCH_INDEX}/_search",
        json={
            "size": SAMPLE_SIZE,
            "track_total_hits": True,
            "query": {
                "function_score": {
                    "query": {
                        "match_all": {},
                    },
                    "random_score": {},
                    "boost_mode": "replace",
                },
            },
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    payload = response.json()

    hits = payload.get("hits", {}).get("hits", [])

    return [
        hit.get("_source", {})
        for hit in hits
    ]


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_question_id(
    question: dict[str, Any],
) -> bool:
    return is_non_empty_string(
        question.get("question_id")
    )


def validate_statement(
    question: dict[str, Any],
) -> bool:
    return is_non_empty_string(
        question.get("statement")
    )


def validate_exam_metadata(
    question: dict[str, Any],
) -> bool:
    exam = question.get("exam")

    if not isinstance(exam, dict):
        return False

    year = exam.get("year")
    area = exam.get("area")
    discipline = exam.get("discipline")

    return (
        isinstance(year, int)
        and 1900 <= year <= 2100
        and is_non_empty_string(area)
        and is_non_empty_string(discipline)
    )


def validate_source_metadata(
    question: dict[str, Any],
) -> bool:
    source = question.get("source")

    if not isinstance(source, dict):
        return False

    storage_key = source.get("storage_key")
    page_start = source.get("page_start")
    page_end = source.get("page_end")

    return (
        is_non_empty_string(storage_key)
        and isinstance(page_start, int)
        and isinstance(page_end, int)
        and page_start > 0
        and page_end >= page_start
    )


def validate_alternatives(
    question: dict[str, Any],
) -> bool:
    question_type = str(
        question.get("question_type", "")
    ).strip().lower()

    alternatives = question.get("alternatives")

    objective_types = {
        "objective",
        "multiple_choice",
        "multiple-choice",
        "multiple choice",
        "objetiva",
        "múltipla escolha",
        "multipla escolha",
    }

    if question_type not in objective_types:
        return True

    if not isinstance(alternatives, list):
        return False

    if len(alternatives) < 2:
        return False

    for alternative in alternatives:
        if not isinstance(alternative, dict):
            return False

        if not is_non_empty_string(
            alternative.get("text")
        ):
            return False

    return True


def validate_question(
    question: dict[str, Any],
) -> dict[str, bool]:
    return {
        "question_id": validate_question_id(question),
        "statement": validate_statement(question),
        "exam_metadata": validate_exam_metadata(question),
        "source_metadata": validate_source_metadata(question),
        "alternatives": validate_alternatives(question),
    }


def evaluate_sample(
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    field_failures = {
        field: 0
        for field in VALIDATION_FIELDS
    }

    valid_questions = 0

    for question in questions:
        validation = validate_question(question)

        for field, is_valid in validation.items():
            if not is_valid:
                field_failures[field] += 1

        if all(validation.values()):
            valid_questions += 1

    total_questions = len(questions)
    invalid_questions = total_questions - valid_questions

    field_rates = {
        field: (
            (total_questions - failures) / total_questions
            if total_questions
            else 0.0
        )
        for field, failures in field_failures.items()
    }

    quality_rate = (
        valid_questions / total_questions
        if total_questions
        else 0.0
    )

    return {
        "total": total_questions,
        "valid": valid_questions,
        "invalid": invalid_questions,
        "quality_rate": quality_rate,
        "field_rates": field_rates,
        "field_failures": field_failures,
    }


def publish_metrics(
    results: dict[str, Any],
) -> None:
    total = results["total"]
    quality_rate = results["quality_rate"]

    SAMPLED_QUESTIONS.set(total)
    VALID_QUESTIONS.set(results["valid"])
    INVALID_QUESTIONS.set(results["invalid"])

    QUALITY_RATE.set(quality_rate * 100)

    SAMPLE_SUFFICIENT.set(
        1 if total >= 50 else 0
    )

    QUALITY_THRESHOLD_MET.set(
        1 if total >= 50 and quality_rate >= MIN_VALID_QUALITY_RATE else 0
    )

    for field in VALIDATION_FIELDS:
        FIELD_VALIDATION_RATE.labels(
            field=field,
        ).set(
            results["field_rates"][field] * 100
        )

        VALIDATION_FAILURES.labels(
            field=field,
        ).set(
            results["field_failures"][field]
        )


def collect_metrics(
    session: requests.Session,
) -> None:
    started_at = time.monotonic()

    questions = fetch_random_sample(session)

    if len(questions) < 50:
        SAMPLE_SUFFICIENT.set(0)

        logger.warning(
            "Amostra insuficiente: encontradas %s questões; mínimo exigido: 50",
            len(questions),
        )

        results = evaluate_sample(questions)
        publish_metrics(results)

        QUALITY_THRESHOLD_MET.set(0)
        COLLECTION_ERRORS.set(0)
        LAST_COLLECTION_TIMESTAMP.set(time.time())

        return

    results = evaluate_sample(questions)

    publish_metrics(results)

    COLLECTION_ERRORS.set(0)
    LAST_COLLECTION_TIMESTAMP.set(time.time())

    logger.info(
        (
            "Avaliação concluída: total=%s válidas=%s inválidas=%s "
            "taxa_de_qualidade=%.2f%%"
        ),
        results["total"],
        results["valid"],
        results["invalid"],
        results["quality_rate"] * 100,
    )

    for field, failures in results["field_failures"].items():
        logger.info(
            "Validação %s: falhas=%s taxa_aprovação=%.2f%%",
            field,
            failures,
            results["field_rates"][field] * 100,
        )

    if results["quality_rate"] < MIN_VALID_QUALITY_RATE:
        logger.warning(
            "Taxa de qualidade abaixo do limite configurado: %.2f%%",
            MIN_VALID_QUALITY_RATE * 100,
        )

    COLLECTION_DURATION.set(
        time.monotonic() - started_at
    )


def main() -> None:
    signal.signal(signal.SIGINT, stop_collector)
    signal.signal(signal.SIGTERM, stop_collector)

    session = create_session()

    start_http_server(METRICS_PORT)

    logger.info(
        "Coletor de qualidade da extração iniciado na porta %s",
        METRICS_PORT,
    )

    logger.info(
        "Amostra mínima: 50 | Amostra configurada: %s | Limite de qualidade: %.2f%%",
        SAMPLE_SIZE,
        MIN_VALID_QUALITY_RATE * 100,
    )

    try:
        while running:
            started_at = time.monotonic()

            try:
                collect_metrics(session)

            except (
                requests.RequestException,
                ValueError,
                TypeError,
            ):
                logger.exception(
                    "Falha durante a avaliação da qualidade da extração"
                )
                COLLECTION_ERRORS.set(1)

            elapsed = time.monotonic() - started_at

            sleep_time = max(
                COLLECTION_INTERVAL - elapsed,
                0,
            )

            if running:
                time.sleep(sleep_time)

    finally:
        session.close()
        logger.info("Coletor de qualidade da extração finalizado")


if __name__ == "__main__":
    main()
