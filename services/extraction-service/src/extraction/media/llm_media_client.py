from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import quote

import httpx


class GeminiMediaClientError(Exception):
    """Erro na comunicação com a API Gemini."""


class GeminiAuthenticationError(GeminiMediaClientError):
    """Erro de autenticação na API Gemini."""


class GeminiRateLimitError(GeminiMediaClientError):
    """Limite de requisições da API Gemini excedido."""


class GeminiResponseError(GeminiMediaClientError):
    """Resposta inválida ou inesperada da API Gemini."""


@dataclass(frozen=True)
class GeminiMediaConfig:
    api_key: str
    model: str = "gemini-3.8-flash"
    base_url: str = "https://generativelanguage.googleapis.com"
    api_version: str = "v1beta"
    timeout_seconds: float = 90.0
    max_retries: int = 0
    max_image_size_mb: int = 20

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("A chave da API Gemini é obrigatória.")

        if not self.model.strip():
            raise ValueError("O modelo Gemini é obrigatório.")

        if self.timeout_seconds <= 0:
            raise ValueError("O timeout deve ser maior que zero.")

        if self.max_retries < 0:
            raise ValueError("O número de tentativas não pode ser negativo.")

        if self.max_image_size_mb <= 0:
            raise ValueError("O limite de imagem deve ser maior que zero.")

        if not self.base_url.startswith("https://"):
            raise ValueError("A URL da API Gemini deve utilizar HTTPS.")

        if not self.api_version.strip():
            raise ValueError("A versão da API é obrigatória.")


@dataclass(frozen=True)
class MediaImage:
    content: bytes
    mime_type: str
    file_name: str | None = None

    SUPPORTED_MIME_TYPES = frozenset({
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    })

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("O conteúdo da imagem não pode estar vazio.")

        if self.mime_type not in self.SUPPORTED_MIME_TYPES:
            raise ValueError(
                f"Tipo de imagem não suportado: {self.mime_type}."
            )


@dataclass(frozen=True)
class GeminiUsage:
    prompt_tokens: int | None = None
    response_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class GeminiMediaResponse:
    content: str
    model: str | None
    finish_reason: str | None
    usage: GeminiUsage
    raw_response: Mapping[str, Any]

    def json(self) -> dict[str, Any]:
        try:
            result = json.loads(self.content)
        except json.JSONDecodeError as error:
            raise GeminiResponseError(
                "O Gemini retornou um conteúdo que não é JSON válido."
            ) from error

        if not isinstance(result, dict):
            raise GeminiResponseError(
                "A resposta JSON do Gemini deve ser um objeto."
            )

        return result


class GeminiMediaClient:

    def __init__(
        self,
        config: GeminiMediaConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._owns_client = client is None

        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": config.api_key,
            },
        )

        model = quote(config.model, safe="-._")
        base_url = config.base_url.rstrip("/")
        api_version = config.api_version.strip("/")

        self._endpoint = (
            f"{base_url}/{api_version}/models/"
            f"{model}:generateContent"
        )

    async def analyze(
        self,
        prompt: str,
        images: Sequence[MediaImage] | None = None,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
        response_mime_type: str | None = None,
        response_schema: Mapping[str, Any] | None = None,
    ) -> GeminiMediaResponse:
        if not prompt.strip():
            raise ValueError("O prompt não pode estar vazio.")

        if not 0.0 <= temperature <= 2.0:
            raise ValueError("A temperatura deve estar entre 0 e 2.")

        if max_output_tokens <= 0:
            raise ValueError(
                "O limite de tokens da resposta deve ser positivo."
            )

        parts: list[dict[str, Any]] = [
            {"text": prompt}
        ]

        for media in images or ():
            self._validate_image_size(media)

            parts.append({
                "inlineData": {
                    "mimeType": media.mime_type,
                    "data": base64.b64encode(
                        media.content
                    ).decode("ascii"),
                }
            })

        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }

        if response_mime_type is not None:
            if response_mime_type not in {
                "text/plain",
                "application/json",
            }:
                raise ValueError(
                    "Formato de resposta não suportado."
                )

            generation_config["responseMimeType"] = response_mime_type

        if response_schema is not None:
            if response_mime_type != "application/json":
                raise ValueError(
                    "response_schema exige response_mime_type="
                    "'application/json'."
                )

            generation_config["responseSchema"] = dict(response_schema)

        request_body: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            "generationConfig": generation_config,
        }

        if system_instruction:
            request_body["systemInstruction"] = {
                "parts": [
                    {"text": system_instruction}
                ]
            }

        response_data = await self._send_request(request_body)

        return self._parse_response(response_data)

    async def analyze_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
    ) -> GeminiMediaResponse:
        return await self.analyze(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    async def analyze_image(
        self,
        prompt: str,
        image: MediaImage,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
        response_mime_type: str | None = None,
        response_schema: Mapping[str, Any] | None = None,
    ) -> GeminiMediaResponse:
        return await self.analyze(
            prompt=prompt,
            images=[image],
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
            response_schema=response_schema,
        )

    async def _send_request(
        self,
        request_body: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        try:
            response = await self._client.post(
                self._endpoint,
                json=request_body,
            )

        except httpx.TimeoutException as error:
            raise GeminiMediaClientError(
                "Tempo limite excedido ao consultar o Gemini."
            ) from error

        except httpx.RequestError as error:
            raise GeminiMediaClientError(
                "Não foi possível estabelecer comunicação com o Gemini."
            ) from error

        if response.status_code in (401, 403):
            raise GeminiAuthenticationError(
                "A API Gemini rejeitou a autenticação. "
                "Verifique a chave e as permissões."
            )

        if response.status_code == 429:
            raise GeminiRateLimitError(
                "O limite de requisições da API Gemini foi excedido."
            )

        if response.is_error:
            message = self._extract_api_error(response)

            raise GeminiMediaClientError(
                f"Erro na API Gemini (HTTP {response.status_code}): "
                f"{message}"
            )

        try:
            data = response.json()
        except ValueError as error:
            raise GeminiResponseError(
                "A API Gemini retornou uma resposta JSON inválida."
            ) from error

        if not isinstance(data, dict):
            raise GeminiResponseError(
                "A estrutura da resposta Gemini é inválida."
            )

        return data

    @staticmethod
    def _extract_api_error(response: httpx.Response) -> str:
        try:
            data = response.json()
            error = data.get("error", {})

            if isinstance(error, dict):
                return str(
                    error.get("message", "Erro não especificado.")
                )

        except ValueError:
            pass

        return "A solicitação não pôde ser processada."

    def _parse_response(
        self,
        data: Mapping[str, Any],
    ) -> GeminiMediaResponse:
        prompt_feedback = data.get("promptFeedback", {})

        if isinstance(prompt_feedback, dict):
            block_reason = prompt_feedback.get("blockReason")

            if block_reason:
                raise GeminiResponseError(
                    f"Solicitação bloqueada pelo Gemini: {block_reason}."
                )

        candidates = data.get("candidates")

        if not isinstance(candidates, list) or not candidates:
            raise GeminiResponseError(
                "O Gemini não retornou candidatos de resposta."
            )

        candidate = candidates[0]

        if not isinstance(candidate, dict):
            raise GeminiResponseError(
                "O candidato retornado pelo Gemini é inválido."
            )

        content = candidate.get("content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else []

        texts = [
            part["text"]
            for part in parts
            if isinstance(part, dict)
            and isinstance(part.get("text"), str)
        ]

        if not texts:
            raise GeminiResponseError(
                "O Gemini não retornou conteúdo textual."
            )

        usage_metadata = data.get("usageMetadata", {})

        if not isinstance(usage_metadata, dict):
            usage_metadata = {}

        usage = GeminiUsage(
            prompt_tokens=usage_metadata.get("promptTokenCount"),
            response_tokens=usage_metadata.get(
                "candidatesTokenCount"
            ),
            total_tokens=usage_metadata.get("totalTokenCount"),
        )

        return GeminiMediaResponse(
            content="\n".join(texts),
            model=data.get("modelVersion"),
            finish_reason=candidate.get("finishReason"),
            usage=usage,
            raw_response=data,
        )

    def _validate_image_size(self, image: MediaImage) -> None:
        max_size = self.config.max_image_size_mb * 1024 * 1024

        if len(image.content) > max_size:
            raise ValueError(
                f"A imagem excede o limite de "
                f"{self.config.max_image_size_mb} MB."
            )

    async def close(self) -> None:
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> GeminiMediaClient:
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        await self.close()
