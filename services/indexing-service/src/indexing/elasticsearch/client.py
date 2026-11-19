from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch import ApiError, AuthenticationException
from elasticsearch import ConnectionError as ElasticsearchConnectionError
from elasticsearch import ConnectionTimeout


logger = logging.getLogger(__name__)


class ElasticsearchClientError(Exception):
    """Erro na comunicação com o Elasticsearch."""


class ElasticsearchAuthenticationError(ElasticsearchClientError):
    """Falha de autenticação no Elasticsearch."""


class ElasticsearchConnection:
    """Gerencia a conexão autenticada com o Elasticsearch."""

    def __init__(
        self,
        hosts: str | Sequence[str],
        username: str | None = None,
        password: str | None = None,
        api_key: str | tuple[str, str] | None = None,
        bearer_auth: str | None = None,
        verify_certs: bool = True,
        ca_certs: str | None = None,
        client_cert: str | None = None,
        client_key: str | None = None,
        request_timeout: float = 30.0,
        max_retries: int = 3,
        retry_on_timeout: bool = True,
        retry_on_status: Sequence[int] = (429, 502, 503, 504),
        connections_per_node: int = 10,
        client: Elasticsearch | None = None,
    ) -> None:
        if not hosts:
            raise ValueError("É necessário informar ao menos um host.")

        if isinstance(hosts, str):
            normalized_hosts = [hosts]
        else:
            normalized_hosts = list(hosts)

        if not normalized_hosts or any(
            not isinstance(host, str) or not host.strip()
            for host in normalized_hosts
        ):
            raise ValueError("A lista de hosts contém valores inválidos.")

        if (username is None) != (password is None):
            raise ValueError(
                "username e password devem ser informados juntos."
            )

        authentication_methods = sum(
            (
                username is not None,
                api_key is not None,
                bearer_auth is not None,
            )
        )

        if authentication_methods > 1:
            raise ValueError(
                "Configure apenas um método de autenticação."
            )

        if client_key and not client_cert:
            raise ValueError(
                "client_cert é obrigatório quando client_key é informado."
            )

        if request_timeout <= 0:
            raise ValueError("request_timeout deve ser maior que zero.")

        if max_retries < 0:
            raise ValueError("max_retries não pode ser negativo.")

        if connections_per_node < 1:
            raise ValueError(
                "connections_per_node deve ser maior que zero."
            )

        if not verify_certs and ca_certs:
            raise ValueError(
                "ca_certs não deve ser configurado com verify_certs=False."
            )

        self._closed = False

        if client is not None:
            self._client = client
            logger.info(
                "Cliente Elasticsearch fornecido externamente."
            )
            return

        config: dict[str, Any] = {
            "hosts": normalized_hosts,
            "verify_certs": verify_certs,
            "request_timeout": request_timeout,
            "max_retries": max_retries,
            "retry_on_timeout": retry_on_timeout,
            "retry_on_status": list(retry_on_status),
            "connections_per_node": connections_per_node,
        }

        if ca_certs:
            config["ca_certs"] = ca_certs

        if client_cert:
            config["client_cert"] = client_cert

        if client_key:
            config["client_key"] = client_key

        if username is not None and password is not None:
            config["basic_auth"] = (username, password)

        if api_key is not None:
            config["api_key"] = api_key

        if bearer_auth is not None:
            config["bearer_auth"] = bearer_auth

        try:
            self._client = Elasticsearch(**config)
        except (ValueError, TypeError) as exc:
            raise ElasticsearchClientError(
                "Não foi possível configurar o cliente Elasticsearch."
            ) from exc

        logger.info(
            "Cliente Elasticsearch configurado para %s host(s).",
            len(normalized_hosts),
        )

    def obter_cliente(self) -> Elasticsearch:
        """Retorna a instância do cliente Elasticsearch."""
        self._validar_estado()
        return self._client

    def verificar_conexao(self) -> bool:
        """Verifica a disponibilidade do Elasticsearch."""
        self._validar_estado()

        try:
            connected = self._client.ping()

            if not connected:
                logger.warning(
                    "Elasticsearch não respondeu ao teste de conexão."
                )

            return bool(connected)

        except AuthenticationException as exc:
            raise ElasticsearchAuthenticationError(
                "O Elasticsearch rejeitou as credenciais configuradas."
            ) from exc
        except (
            ElasticsearchConnectionError,
            ConnectionTimeout,
        ) as exc:
            raise ElasticsearchClientError(
                "Não foi possível estabelecer conexão com o Elasticsearch."
            ) from exc
        except ApiError as exc:
            raise ElasticsearchClientError(
                "O Elasticsearch retornou um erro durante o teste de conexão."
            ) from exc

    def obter_informacoes(self) -> dict[str, Any]:
        """Obtém informações da instância Elasticsearch conectada."""
        self._validar_estado()

        try:
            response = self._client.info()
            body = getattr(response, "body", response)

            if not isinstance(body, Mapping):
                raise ElasticsearchClientError(
                    "O Elasticsearch retornou informações em formato inválido."
                )

            return dict(body)

        except AuthenticationException as exc:
            raise ElasticsearchAuthenticationError(
                "Falha de autenticação ao consultar o Elasticsearch."
            ) from exc
        except (
            ElasticsearchConnectionError,
            ConnectionTimeout,
        ) as exc:
            raise ElasticsearchClientError(
                "Falha de conexão ao consultar informações do Elasticsearch."
            ) from exc
        except ApiError as exc:
            raise ElasticsearchClientError(
                "O Elasticsearch retornou um erro ao consultar suas informações."
            ) from exc

    def fechar(self) -> None:
        """Fecha a conexão com o Elasticsearch."""
        if self._closed:
            return

        try:
            self._client.close()
        except Exception as exc:
            raise ElasticsearchClientError(
                "Não foi possível encerrar a conexão com o Elasticsearch."
            ) from exc
        finally:
            self._closed = True

        logger.info("Conexão Elasticsearch encerrada.")

    def _validar_estado(self) -> None:
        if self._closed:
            raise ElasticsearchClientError(
                "O cliente Elasticsearch já foi encerrado."
            )

    def __enter__(self) -> ElasticsearchConnection:
        self._validar_estado()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        self.fechar()
