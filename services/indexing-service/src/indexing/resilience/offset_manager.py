from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from confluent_kafka import KafkaException, TopicPartition


logger = logging.getLogger(__name__)


class OffsetManagerError(Exception):
    """Erro durante o gerenciamento de offsets Kafka."""


class OffsetNotRegisteredError(OffsetManagerError):
    """Offset não registrado para acompanhamento."""


@dataclass(slots=True)
class PartitionState:
    """Estado de processamento dos offsets de uma partição."""

    topic: str
    partition: int
    pending_offsets: list[int] = field(default_factory=list)
    completed_offsets: set[int] = field(default_factory=set)
    last_committed_offset: int | None = None


@dataclass(frozen=True, slots=True)
class OffsetCommitResult:
    """Resultado de uma confirmação de offsets."""

    topic: str
    partition: int
    committed_offset: int
    processed_offsets: tuple[int, ...]


class OffsetManager:
    """Controla o processamento e a confirmação manual de offsets."""

    def __init__(
        self,
        consumer: Any,
        asynchronous: bool = False,
    ) -> None:
        if consumer is None:
            raise ValueError("O consumidor Kafka é obrigatório.")

        self._consumer = consumer
        self._asynchronous = asynchronous
        self._partitions: dict[tuple[str, int], PartitionState] = {}
        self._lock = threading.RLock()

    def registrar_mensagem(
        self,
        topic: str,
        partition: int,
        offset: int,
    ) -> None:
        """Registra uma mensagem recebida para acompanhamento."""
        self._validar_identificacao(topic, partition, offset)

        key = (topic, partition)

        with self._lock:
            state = self._partitions.setdefault(
                key,
                PartitionState(
                    topic=topic,
                    partition=partition,
                ),
            )

            if offset in state.pending_offsets:
                return

            if (
                state.pending_offsets
                and offset < state.pending_offsets[-1]
            ):
                raise OffsetManagerError(
                    "Os offsets recebidos precisam respeitar "
                    "a ordem de processamento da partição."
                )

            state.pending_offsets.append(offset)

    def marcar_processado(
        self,
        topic: str,
        partition: int,
        offset: int,
        confirmar: bool = True,
    ) -> OffsetCommitResult | None:
        """Marca uma mensagem como processada e confirma offsets elegíveis."""
        key = (topic, partition)

        with self._lock:
            state = self._partitions.get(key)

            if state is None or offset not in state.pending_offsets:
                raise OffsetNotRegisteredError(
                    f"Offset {offset} não registrado para "
                    f"{topic}[{partition}]."
                )

            state.completed_offsets.add(offset)

            if not confirmar:
                return None

            return self._confirmar_particao(state)

    def marcar_lote_processado(
        self,
        messages: list[Any],
        confirmar: bool = True,
    ) -> list[OffsetCommitResult]:
        """Marca várias mensagens e confirma os offsets elegíveis."""
        with self._lock:
            for message in messages:
                self.registrar_mensagem(
                    topic=message.topic(),
                    partition=message.partition(),
                    offset=message.offset(),
                )

                self.marcar_processado(
                    topic=message.topic(),
                    partition=message.partition(),
                    offset=message.offset(),
                    confirmar=False,
                )

            if not confirmar:
                return []

            return self.confirmar_pendentes()

    def confirmar_pendentes(self) -> list[OffsetCommitResult]:
        """Confirma os offsets concluídos sem ultrapassar mensagens pendentes."""
        results: list[OffsetCommitResult] = []

        with self._lock:
            for state in self._partitions.values():
                result = self._confirmar_particao(state)

                if result is not None:
                    results.append(result)

        return results

    def _confirmar_particao(
        self,
        state: PartitionState,
    ) -> OffsetCommitResult | None:
        """Confirma somente a sequência inicial de mensagens concluídas."""
        if not state.pending_offsets:
            return None

        processed: list[int] = []

        for offset in state.pending_offsets:
            if offset not in state.completed_offsets:
                break

            processed.append(offset)

        if not processed:
            return None

        last_offset = processed[-1]
        next_offset = last_offset + 1

        topic_partition = TopicPartition(
            state.topic,
            state.partition,
            next_offset,
        )

        try:
            self._consumer.commit(
                offsets=[topic_partition],
                asynchronous=self._asynchronous,
            )
        except KafkaException as exc:
            logger.exception(
                "Falha ao confirmar offsets de %s[%s].",
                state.topic,
                state.partition,
            )
            raise OffsetManagerError(
                f"Não foi possível confirmar os offsets de "
                f"{state.topic}[{state.partition}]."
            ) from exc

        if self._asynchronous:
            logger.debug(
                "Solicitada confirmação assíncrona de %s[%s] até %s.",
                state.topic,
                state.partition,
                next_offset,
            )
        else:
            logger.debug(
                "Offsets confirmados de %s[%s] até %s.",
                state.topic,
                state.partition,
                next_offset,
            )

        processed_set = set(processed)

        state.pending_offsets = [
            offset
            for offset in state.pending_offsets
            if offset not in processed_set
        ]

        state.completed_offsets.difference_update(processed_set)
        state.last_committed_offset = next_offset

        return OffsetCommitResult(
            topic=state.topic,
            partition=state.partition,
            committed_offset=next_offset,
            processed_offsets=tuple(processed),
        )

    def obter_offsets_pendentes(
        self,
        topic: str | None = None,
        partition: int | None = None,
    ) -> dict[str, list[int]]:
        """Retorna os offsets ainda não confirmados."""
        with self._lock:
            result: dict[str, list[int]] = {}

            for state in self._partitions.values():
                if topic is not None and state.topic != topic:
                    continue

                if (
                    partition is not None
                    and state.partition != partition
                ):
                    continue

                key = f"{state.topic}[{state.partition}]"
                result[key] = list(state.pending_offsets)

            return result

    def obter_offsets_processados(
        self,
        topic: str,
        partition: int,
    ) -> tuple[int, ...]:
        """Retorna os offsets processados que aguardam confirmação."""
        with self._lock:
            state = self._partitions.get((topic, partition))

            if state is None:
                return ()

            return tuple(
                sorted(state.completed_offsets)
            )

    def obter_ultimo_offset_confirmado(
        self,
        topic: str,
        partition: int,
    ) -> int | None:
        """Retorna o próximo offset confirmado para uma partição."""
        with self._lock:
            state = self._partitions.get((topic, partition))

            if state is None:
                return None

            return state.last_committed_offset

    def reiniciar_particao(
        self,
        topic: str,
        partition: int,
    ) -> None:
        """Remove o estado local de uma partição após revogação ou reassociação."""
        with self._lock:
            self._partitions.pop((topic, partition), None)

            logger.info(
                "Estado local da partição %s[%s] reiniciado.",
                topic,
                partition,
            )

    def reiniciar_todas_particoes(self) -> None:
        """Remove o acompanhamento local de todas as partições."""
        with self._lock:
            self._partitions.clear()

            logger.info(
                "Estado local de todas as partições foi reiniciado."
            )

    @staticmethod
    def _validar_identificacao(
        topic: str,
        partition: int,
        offset: int,
    ) -> None:
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("O tópico Kafka precisa ser informado.")

        if partition < 0:
            raise ValueError("A partição não pode ser negativa.")

        if offset < 0:
            raise ValueError("O offset não pode ser negativo.")
