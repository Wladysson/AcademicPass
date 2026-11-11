import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import requests


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("academicpass.report-artifacts")


PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://prometheus:9090",
).rstrip("/")

PROMETHEUS_TIMEOUT = int(
    os.getenv("PROMETHEUS_TIMEOUT", "30")
)

OUTPUT_DIR = Path(
    os.getenv(
        "REPORT_OUTPUT_DIR",
        "./report-artifacts",
    )
).expanduser()

DEFAULT_RANGE = os.getenv(
    "REPORT_RANGE",
    "24h",
)

DEFAULT_STEP = os.getenv(
    "REPORT_STEP",
    "5m",
)

REQUEST_VERIFY_TLS = (
    os.getenv("PROMETHEUS_VERIFY_TLS", "true").lower()
    == "true"
)

PROMETHEUS_TOKEN = os.getenv("PROMETHEUS_TOKEN")
PROMETHEUS_USERNAME = os.getenv("PROMETHEUS_USERNAME")
PROMETHEUS_PASSWORD = os.getenv("PROMETHEUS_PASSWORD")


METRIC_QUERIES = {
    "search_latency_p95": {
        "title": "Latência de busca p95",
        "query": (
            'academicpass_search_latency_seconds'
            '{quantile="p95"}'
        ),
        "unit": "seconds",
        "description": "Percentil 95 da latência das buscas.",
    },
    "search_latency_p99": {
        "title": "Latência de busca p99",
        "query": (
            'academicpass_search_latency_seconds'
            '{quantile="p99"}'
        ),
        "unit": "seconds",
        "description": "Percentil 99 da latência das buscas.",
    },
    "ingestion_throughput": {
        "title": "Throughput de indexação",
        "query": (
            "academicpass_ingestion_throughput_documents_per_second"
        ),
        "unit": "documents/second",
        "description": (
            "Taxa estimada de variação de documentos indexados por segundo."
        ),
    },
    "kafka_consumer_lag": {
        "title": "Lag dos consumer groups Kafka",
        "query": (
            "academicpass_kafka_consumer_group_lag"
        ),
        "unit": "messages",
        "description": (
            "Quantidade de mensagens pendentes por tópico e consumer group."
        ),
    },
    "redis_hit_rate": {
        "title": "Taxa de acerto do Redis",
        "query": (
            "academicpass_redis_hit_rate"
        ),
        "unit": "ratio",
        "description": (
            "Proporção de leituras atendidas pelo cache Redis."
        ),
    },
    "extraction_quality": {
        "title": "Qualidade estrutural da extração",
        "query": (
            "academicpass_extraction_quality_rate"
        ),
        "unit": "percent",
        "description": (
            "Percentual de questões aprovadas na validação estrutural."
        ),
    },
    "extraction_invalid_questions": {
        "title": "Questões reprovadas na extração",
        "query": (
            "academicpass_extraction_quality_invalid_questions"
        ),
        "unit": "questions",
        "description": (
            "Quantidade de questões reprovadas na última amostra."
        ),
    },
}


class PrometheusClient:
    def __init__(self) -> None:
        self.session = requests.Session()

        if PROMETHEUS_TOKEN:
            self.session.headers.update({
                "Authorization": f"Bearer {PROMETHEUS_TOKEN}",
            })
        elif PROMETHEUS_USERNAME and PROMETHEUS_PASSWORD:
            self.session.auth = (
                PROMETHEUS_USERNAME,
                PROMETHEUS_PASSWORD,
            )

    def query_range(
        self,
        query: str,
        start: float,
        end: float,
        step: str,
    ) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={
                "query": query,
                "start": start,
                "end": end,
                "step": step,
            },
            timeout=PROMETHEUS_TIMEOUT,
            verify=REQUEST_VERIFY_TLS,
        )

        response.raise_for_status()

        payload = response.json()

        if payload.get("status") != "success":
            raise RuntimeError(
                f"Consulta Prometheus malsucedida: {payload}"
            )

        return payload.get("data", {}).get("result", [])

    def close(self) -> None:
        self.session.close()


def parse_duration(value: str) -> int:
    match = re.fullmatch(
        r"(\d+)([smhd])",
        value.strip().lower(),
    )

    if not match:
        raise ValueError(
            "Intervalo inválido. Utilize formatos como 30m, 6h, 24h ou 7d."
        )

    amount = int(match.group(1))
    unit = match.group(2)

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }

    return amount * multipliers[unit]


def parse_timestamp(value: float) -> str:
    return datetime.fromtimestamp(
        value,
        tz=timezone.utc,
    ).isoformat()


def normalize_series(
    metric_name: str,
    series: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = []

    for item in series:
        labels = item.get("metric", {})

        for timestamp, value in item.get("values", []):
            try:
                numeric_value = float(value)
                numeric_timestamp = float(timestamp)
            except (TypeError, ValueError):
                logger.warning(
                    "Ignorando amostra inválida da métrica %s",
                    metric_name,
                )
                continue

            if numeric_value != numeric_value:
                continue

            if numeric_value in (float("inf"), float("-inf")):
                continue

            normalized.append({
                "metric": metric_name,
                "timestamp": numeric_timestamp,
                "datetime": parse_timestamp(numeric_timestamp),
                "value": numeric_value,
                "labels": labels,
            })

    return normalized


def collect_report_data(
    client: PrometheusClient,
    start: float,
    end: float,
    step: str,
) -> dict[str, Any]:
    report_data = {}

    for metric_name, definition in METRIC_QUERIES.items():
        logger.info(
            "Consultando métrica: %s",
            metric_name,
        )

        try:
            series = client.query_range(
                query=definition["query"],
                start=start,
                end=end,
                step=step,
            )

            report_data[metric_name] = {
                "title": definition["title"],
                "description": definition["description"],
                "unit": definition["unit"],
                "query": definition["query"],
                "samples": normalize_series(
                    metric_name,
                    series,
                ),
                "status": "collected",
            }

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ):
            logger.exception(
                "Não foi possível coletar a métrica %s",
                metric_name,
            )

            report_data[metric_name] = {
                "title": definition["title"],
                "description": definition["description"],
                "unit": definition["unit"],
                "query": definition["query"],
                "samples": [],
                "status": "error",
            }

    return report_data


def calculate_statistics(
    samples: list[dict[str, Any]],
) -> dict[str, float | int | None]:
    values = [
        sample["value"]
        for sample in samples
    ]

    if not values:
        return {
            "count": 0,
            "minimum": None,
            "maximum": None,
            "average": None,
            "latest": None,
        }

    return {
        "count": len(values),
        "minimum": min(values),
        "maximum": max(values),
        "average": sum(values) / len(values),
        "latest": samples[-1]["value"],
    }


def build_summary(
    report_data: dict[str, Any],
) -> dict[str, Any]:
    summary = {}

    for metric_name, metric_data in report_data.items():
        summary[metric_name] = {
            "title": metric_data["title"],
            "unit": metric_data["unit"],
            "status": metric_data["status"],
            "statistics": calculate_statistics(
                metric_data["samples"]
            ),
        }

    return summary


def export_csv(
    report_data: dict[str, Any],
    output_path: Path,
) -> None:
    columns = [
        "metric",
        "datetime",
        "timestamp",
        "value",
        "unit",
        "labels",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=columns,
        )

        writer.writeheader()

        for metric_name, metric_data in report_data.items():
            for sample in metric_data["samples"]:
                writer.writerow({
                    "metric": metric_name,
                    "datetime": sample["datetime"],
                    "timestamp": sample["timestamp"],
                    "value": sample["value"],
                    "unit": metric_data["unit"],
                    "labels": json.dumps(
                        sample["labels"],
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                })


def export_json(
    report_data: dict[str, Any],
    summary: dict[str, Any],
    metadata: dict[str, Any],
    output_path: Path,
) -> None:
    payload = {
        "project": "AcademicPass",
        "report": "SBC Observability Report",
        "metadata": metadata,
        "summary": summary,
        "metrics": report_data,
    }

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as json_file:
        json.dump(
            payload,
            json_file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )


def generate_metric_chart(
    metric_name: str,
    metric_data: dict[str, Any],
    output_path: Path,
) -> bool:
    samples = metric_data["samples"]

    if not samples:
        logger.warning(
            "Sem amostras para gerar gráfico: %s",
            metric_name,
        )
        return False

    grouped_series: dict[str, list[dict[str, Any]]] = {}

    for sample in samples:
        labels = sample["labels"]

        series_name = (
            ", ".join(
                f"{key}={value}"
                for key, value in sorted(labels.items())
            )
            or metric_name
        )

        grouped_series.setdefault(
            series_name,
            [],
        ).append(sample)

    figure, axis = plt.subplots(
        figsize=(11, 5),
    )

    for series_name, series_samples in grouped_series.items():
        series_samples.sort(
            key=lambda sample: sample["timestamp"]
        )

        timestamps = [
            datetime.fromtimestamp(
                sample["timestamp"],
                tz=timezone.utc,
            )
            for sample in series_samples
        ]

        values = [
            sample["value"]
            for sample in series_samples
        ]

        axis.plot(
            timestamps,
            values,
            label=series_name,
            linewidth=1.5,
        )

    axis.set_title(metric_data["title"])
    axis.set_xlabel("Tempo (UTC)")
    axis.set_ylabel(metric_data["unit"])

    axis.grid(
        True,
        linestyle="--",
        alpha=0.4,
    )

    if len(grouped_series) > 1:
        axis.legend(
            loc="best",
            fontsize="small",
        )

    figure.autofmt_xdate()
    figure.tight_layout()

    figure.savefig(
        output_path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(figure)

    return True


def generate_charts(
    report_data: dict[str, Any],
    charts_dir: Path,
) -> list[str]:
    charts_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated_charts = []

    for metric_name, metric_data in report_data.items():
        filename = f"{metric_name}.png"

        output_path = charts_dir / filename

        if generate_metric_chart(
            metric_name,
            metric_data,
            output_path,
        ):
            generated_charts.append(filename)

    return generated_charts


def generate_report(
    output_dir: Path,
    report_range: str,
    step: str,
) -> dict[str, Any]:
    duration_seconds = parse_duration(report_range)

    end = time.time()
    start = end - duration_seconds

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    charts_dir = output_dir / "charts"

    client = PrometheusClient()

    try:
        report_data = collect_report_data(
            client,
            start,
            end,
            step,
        )
    finally:
        client.close()

    summary = build_summary(report_data)

    metadata = {
        "project": "AcademicPass",
        "report_type": "SBC observability",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "period": {
            "start": parse_timestamp(start),
            "end": parse_timestamp(end),
            "duration": report_range,
            "step": step,
        },
        "prometheus_url": PROMETHEUS_URL,
        "metrics_collected": len(report_data),
        "metrics_with_errors": sum(
            1
            for metric in report_data.values()
            if metric["status"] == "error"
        ),
    }

    generated_charts = generate_charts(
        report_data,
        charts_dir,
    )

    metadata["generated_charts"] = generated_charts

    export_csv(
        report_data,
        output_dir / "observability_metrics.csv",
    )

    export_json(
        report_data,
        summary,
        metadata,
        output_dir / "observability_report.json",
    )

    export_csv(
        {
            metric_name: {
                "unit": metric_data["unit"],
                "samples": [
                    {
                        **sample,
                        "metric": metric_name,
                    }
                    for sample in metric_data["samples"]
                ],
            }
            for metric_name, metric_data in report_data.items()
        },
        output_dir / "observability_summary.csv",
    )

    logger.info(
        "Artefatos gerados em: %s",
        output_dir.resolve(),
    )

    logger.info(
        "Gráficos gerados: %s",
        len(generated_charts),
    )

    return metadata


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Gera CSV, JSON e gráficos de observabilidade "
            "do AcademicPass para o relatório SBC."
        ),
    )

    parser.add_argument(
        "--range",
        default=DEFAULT_RANGE,
        help="Período analisado: 30m, 6h, 24h ou 7d.",
    )

    parser.add_argument(
        "--step",
        default=DEFAULT_STEP,
        help="Intervalo entre amostras do Prometheus.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help="Diretório de saída dos artefatos.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        metadata = generate_report(
            output_dir=args.output,
            report_range=args.range,
            step=args.step,
        )

        if metadata["metrics_with_errors"] > 0:
            logger.warning(
                "Relatório gerado com %s métricas indisponíveis.",
                metadata["metrics_with_errors"],
            )
            return 1

        return 0

    except (
        ValueError,
        OSError,
        requests.RequestException,
        RuntimeError,
    ):
        logger.exception(
            "Não foi possível gerar os artefatos do relatório SBC."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
