"""OpenAI-compatible async client with retry, rate limit, and metrics."""

from __future__ import annotations

import asyncio
import json
import socket
import time
import urllib.error
import urllib.request
from functools import partial
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from pipeline.common.async_batcher import AsyncBatcher
from pipeline.common.config_loader import load_yaml
from pipeline.common.io import (
    collect_runtime_env,
    get_env_float,
    get_env_int,
    get_env_value,
    json_dumps,
)
from pipeline.common.rate_limit import AsyncSlidingWindowRateLimiter


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class LLMTransportError(Exception):
    """Base error for transport-layer failures."""


class LLMHTTPError(LLMTransportError):
    def __init__(self, status_code: int, body_text: str) -> None:
        super().__init__(f"HTTP {status_code}: {body_text}")
        self.status_code = status_code
        self.body_text = body_text


class LLMTimeoutError(LLMTransportError):
    """Raised when the underlying HTTP call times out."""


@dataclass
class LLMSettings:
    provider: str
    api_key: str | None
    base_url: str
    generation_model: str
    embedding_model: str
    embedding_dimension: int
    embedding_token_limit: int
    timeout_seconds: int
    max_retries: int
    backoff_seconds: float
    calls_per_minute_per_worker: int
    async_concurrency: int

    @classmethod
    def from_repo_root(
        cls,
        repo_root: str | Path,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "LLMSettings":
        root = Path(repo_root)
        llm_cfg = load_yaml(root / "config/llm.yaml")
        runtime_env = collect_runtime_env(root, environ)

        return cls(
            provider=str(llm_cfg["provider"]),
            api_key=get_env_value("OPENAI_API_KEY", None, environ=runtime_env),
            base_url=get_env_value(
                "OPENAI_BASE_URL",
                DEFAULT_OPENAI_BASE_URL,
                environ=runtime_env,
            ).rstrip("/"),
            generation_model=str(llm_cfg["generation"]["model"]),
            embedding_model=str(llm_cfg["embedding"]["model"]),
            embedding_dimension=int(llm_cfg["embedding"]["dimension"]),
            embedding_token_limit=int(llm_cfg["embedding"]["token_limit"]),
            timeout_seconds=get_env_int(
                "OPENAI_TIMEOUT_SECONDS",
                int(llm_cfg["request"]["timeout_seconds"]),
                environ=runtime_env,
            ),
            max_retries=get_env_int(
                "OPENAI_MAX_RETRIES",
                int(llm_cfg["request"]["max_retries"]),
                environ=runtime_env,
            ),
            backoff_seconds=get_env_float(
                "OPENAI_BACKOFF_SECONDS",
                float(llm_cfg["request"]["backoff_seconds"]),
                environ=runtime_env,
            ),
            calls_per_minute_per_worker=int(
                llm_cfg["rate_limit"]["calls_per_minute_per_worker"]
            ),
            async_concurrency=int(llm_cfg["rate_limit"]["async_concurrency"]),
        )


@dataclass
class ChatRequest:
    system_prompt: str
    user_prompt: str
    request_id: str | None = None
    model_name: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class EmbeddingRequest:
    text: str
    request_id: str | None = None
    model_name: str | None = None
    dimension: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class LLMCallResult:
    status: str
    request_id: str | None
    model_name: str
    response_text: str | None = None
    response_json: str | None = None
    embedding: list[float] | None = None
    usage: dict[str, Any] | None = None
    latency_seconds: float = 0.0
    retry_count: int = 0
    rate_limit_wait_seconds: float = 0.0
    rate_limit_wait_count: int = 0
    error_type: str | None = None
    error_message: str | None = None
    http_status: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class LLMClientMetrics:
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    rate_limited_count: int = 0
    total_retry_count: int = 0
    total_latency_seconds: float = 0.0
    total_rate_limit_wait_seconds: float = 0.0
    rate_limit_wait_events: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    error_counts: dict[str, int] = field(default_factory=dict)
    usage_totals: dict[str, int] = field(default_factory=dict)

    def record(self, result: LLMCallResult) -> None:
        self.total_requests += 1
        self.total_latency_seconds += result.latency_seconds
        self.total_retry_count += result.retry_count
        self.total_rate_limit_wait_seconds += result.rate_limit_wait_seconds
        self.rate_limit_wait_events += result.rate_limit_wait_count
        self.status_counts[result.status] = self.status_counts.get(result.status, 0) + 1

        if result.status == "SUCCESS":
            self.success_count += 1
        elif result.status == "TIMEOUT":
            self.timeout_count += 1
            self.failure_count += 1
        elif result.status == "RATE_LIMITED":
            self.rate_limited_count += 1
            self.failure_count += 1
        else:
            self.failure_count += 1

        if result.error_type:
            self.error_counts[result.error_type] = (
                self.error_counts.get(result.error_type, 0) + 1
            )
        if result.usage:
            for key, value in result.usage.items():
                if isinstance(value, int):
                    self.usage_totals[key] = self.usage_totals.get(key, 0) + value

    def snapshot(self) -> dict[str, Any]:
        avg_latency = 0.0
        if self.total_requests > 0:
            avg_latency = self.total_latency_seconds / self.total_requests
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_count": self.timeout_count,
            "rate_limited_count": self.rate_limited_count,
            "total_retry_count": self.total_retry_count,
            "total_latency_seconds": self.total_latency_seconds,
            "avg_latency_seconds": avg_latency,
            "total_rate_limit_wait_seconds": self.total_rate_limit_wait_seconds,
            "rate_limit_wait_events": self.rate_limit_wait_events,
            "status_counts": dict(self.status_counts),
            "error_counts": dict(self.error_counts),
            "usage_totals": dict(self.usage_totals),
        }


class OpenAICompatibleClient:
    """OpenAI-compatible client with internal async batching."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        rate_limiter: AsyncSlidingWindowRateLimiter | None = None,
        async_batcher: AsyncBatcher | None = None,
    ) -> None:
        self.settings = settings
        self.rate_limiter = rate_limiter or AsyncSlidingWindowRateLimiter(
            settings.calls_per_minute_per_worker
        )
        self.async_batcher = async_batcher or AsyncBatcher(settings.async_concurrency)
        self._metrics = LLMClientMetrics()

    @classmethod
    def from_repo_root(
        cls,
        repo_root: str | Path,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "OpenAICompatibleClient":
        return cls(LLMSettings.from_repo_root(repo_root, environ=environ))

    def metrics_snapshot(self) -> dict[str, Any]:
        snapshot = self._metrics.snapshot()
        snapshot["rate_limiter"] = asdict(self.rate_limiter.snapshot())
        return snapshot

    async def _run_blocking(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args))

    async def generate_text(self, request: ChatRequest) -> LLMCallResult:
        model_name = request.model_name or self.settings.generation_model
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        return await self._request_json(
            endpoint="/chat/completions",
            payload=payload,
            request_id=request.request_id,
            model_name=model_name,
            metadata=request.metadata,
            parser=self._parse_chat_response,
        )

    async def generate_text_batch(
        self,
        requests: Sequence[ChatRequest],
    ) -> list[LLMCallResult]:
        return await self.async_batcher.map(requests, self.generate_text)

    async def embed_text(self, request: EmbeddingRequest) -> LLMCallResult:
        model_name = request.model_name or self.settings.embedding_model
        dimensions = request.dimension or self.settings.embedding_dimension
        payload = {
            "model": model_name,
            "input": request.text,
            "dimensions": dimensions,
        }
        return await self._request_json(
            endpoint="/embeddings",
            payload=payload,
            request_id=request.request_id,
            model_name=model_name,
            metadata=request.metadata,
            parser=self._parse_embedding_response,
        )

    async def embed_text_batch(
        self,
        requests: Sequence[EmbeddingRequest],
    ) -> list[LLMCallResult]:
        return await self.async_batcher.map(requests, self.embed_text)

    async def _request_json(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        request_id: str | None,
        model_name: str,
        metadata: dict[str, Any] | None,
        parser,
    ) -> LLMCallResult:
        total_wait_seconds = 0.0
        wait_count = 0
        retry_count = 0
        started_at = time.monotonic()
        last_error_type: str | None = None
        last_error_message: str | None = None
        last_http_status: int | None = None

        for attempt in range(self.settings.max_retries + 1):
            waited = await self.rate_limiter.acquire()
            total_wait_seconds += waited
            if waited > 0:
                wait_count += 1

            try:
                response_json = await self._run_blocking(
                    self._post_json_sync,
                    endpoint,
                    payload,
                )
                parsed = parser(response_json)
                result = LLMCallResult(
                    status="SUCCESS",
                    request_id=request_id,
                    model_name=model_name,
                    response_text=parsed.get("response_text"),
                    response_json=json_dumps(response_json),
                    embedding=parsed.get("embedding"),
                    usage=response_json.get("usage"),
                    latency_seconds=time.monotonic() - started_at,
                    retry_count=retry_count,
                    rate_limit_wait_seconds=total_wait_seconds,
                    rate_limit_wait_count=wait_count,
                    metadata=metadata,
                )
                self._metrics.record(result)
                return result
            except LLMTimeoutError as exc:
                last_error_type = "timeout"
                last_error_message = str(exc)
                if attempt < self.settings.max_retries:
                    retry_count += 1
                    await asyncio.sleep(self.settings.backoff_seconds * (2**attempt))
                    continue
                result = LLMCallResult(
                    status="TIMEOUT",
                    request_id=request_id,
                    model_name=model_name,
                    latency_seconds=time.monotonic() - started_at,
                    retry_count=retry_count,
                    rate_limit_wait_seconds=total_wait_seconds,
                    rate_limit_wait_count=wait_count,
                    error_type=last_error_type,
                    error_message=last_error_message,
                    metadata=metadata,
                )
                self._metrics.record(result)
                return result
            except LLMHTTPError as exc:
                last_http_status = exc.status_code
                last_error_type = f"http_{exc.status_code}"
                last_error_message = exc.body_text
                should_retry = exc.status_code == 429 or exc.status_code >= 500
                if should_retry and attempt < self.settings.max_retries:
                    retry_count += 1
                    await asyncio.sleep(self.settings.backoff_seconds * (2**attempt))
                    continue
                status = "RATE_LIMITED" if exc.status_code == 429 else "FAILED"
                result = LLMCallResult(
                    status=status,
                    request_id=request_id,
                    model_name=model_name,
                    latency_seconds=time.monotonic() - started_at,
                    retry_count=retry_count,
                    rate_limit_wait_seconds=total_wait_seconds,
                    rate_limit_wait_count=wait_count,
                    error_type=last_error_type,
                    error_message=last_error_message,
                    http_status=last_http_status,
                    metadata=metadata,
                )
                self._metrics.record(result)
                return result
            except (LLMTransportError, ValueError, KeyError, IndexError) as exc:
                last_error_type = exc.__class__.__name__.lower()
                last_error_message = str(exc)
                if attempt < self.settings.max_retries:
                    retry_count += 1
                    await asyncio.sleep(self.settings.backoff_seconds * (2**attempt))
                    continue
                result = LLMCallResult(
                    status="FAILED",
                    request_id=request_id,
                    model_name=model_name,
                    latency_seconds=time.monotonic() - started_at,
                    retry_count=retry_count,
                    rate_limit_wait_seconds=total_wait_seconds,
                    rate_limit_wait_count=wait_count,
                    error_type=last_error_type,
                    error_message=last_error_message,
                    http_status=last_http_status,
                    metadata=metadata,
                )
                self._metrics.record(result)
                return result

        raise RuntimeError("Unreachable retry loop state")

    def _post_json_sync(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self.settings.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"

        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(
                request, timeout=self.settings.timeout_seconds
            ) as response:
                payload_text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            payload_text = exc.read().decode("utf-8", errors="replace")
            raise LLMHTTPError(exc.code, payload_text) from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise LLMTimeoutError("HTTP request timed out") from exc
            raise LLMTransportError(str(reason)) from exc
        except TimeoutError as exc:
            raise LLMTimeoutError("HTTP request timed out") from exc
        except socket.timeout as exc:
            raise LLMTimeoutError("HTTP request timed out") from exc

        parsed = json.loads(payload_text)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object response from provider")
        return parsed

    @staticmethod
    def _parse_chat_response(response_json: dict[str, Any]) -> dict[str, Any]:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Missing choices in chat completion response")

        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ValueError("Missing message in chat completion response")

        content = message.get("content")
        if isinstance(content, str):
            response_text = content
        elif isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            response_text = "".join(parts)
        else:
            raise ValueError("Unsupported message.content shape in chat response")

        return {"response_text": response_text}

    @staticmethod
    def _parse_embedding_response(response_json: dict[str, Any]) -> dict[str, Any]:
        data = response_json.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Missing data in embedding response")

        item = data[0]
        if not isinstance(item, dict):
            raise ValueError("Invalid embedding item")
        embedding = item.get("embedding")
        if not isinstance(embedding, list):
            raise ValueError("Missing embedding vector")
        return {"embedding": [float(value) for value in embedding]}
