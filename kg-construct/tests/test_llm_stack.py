from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pipeline.common.async_batcher import AsyncBatcher
from pipeline.common.io import collect_runtime_env, load_dotenv_values
from pipeline.common.llm_client import (
    ChatRequest,
    EmbeddingRequest,
    LLMSettings,
    OpenAICompatibleClient,
)
from pipeline.common.rate_limit import AsyncSlidingWindowRateLimiter


class RateLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_sliding_window_waits_after_limit(self) -> None:
        limiter = AsyncSlidingWindowRateLimiter(2, window_seconds=0.25)
        await limiter.acquire()
        await limiter.acquire()

        started_at = time.monotonic()
        waited = await limiter.acquire()
        elapsed = time.monotonic() - started_at

        self.assertGreaterEqual(waited, 0.18)
        self.assertGreaterEqual(elapsed, 0.18)
        self.assertEqual(limiter.snapshot().total_acquires, 3)
        self.assertEqual(limiter.snapshot().wait_events, 1)


class AsyncBatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_batcher_preserves_order_and_concurrency(self) -> None:
        batcher = AsyncBatcher(2)
        active = 0
        max_active = 0
        lock = asyncio.Lock()

        async def worker(value: int) -> int:
            nonlocal active, max_active
            async with lock:
                active += 1
                max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            async with lock:
                active -= 1
            return value * 10

        results = await batcher.map([1, 2, 3, 4], worker)
        self.assertEqual(results, [10, 20, 30, 40])
        self.assertLessEqual(max_active, 2)


class _MockOpenAIHandler(BaseHTTPRequestHandler):
    chat_attempts = 0
    embedding_attempts = 0

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(content_length).decode("utf-8"))

        if self.path == "/v1/chat/completions":
            type(self).chat_attempts += 1
            if type(self).chat_attempts == 1:
                self._write_json(429, {"error": {"message": "retry later"}})
                return

            user_prompt = payload["messages"][1]["content"]
            self._write_json(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": f"echo::{user_prompt}",
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 11,
                        "completion_tokens": 7,
                        "total_tokens": 18,
                    },
                },
            )
            return

        if self.path == "/v1/embeddings":
            type(self).embedding_attempts += 1
            text = payload["input"]
            self._write_json(
                200,
                {
                    "data": [
                        {
                            "embedding": [
                                float(len(text)),
                                1.0,
                                2.0,
                            ]
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 5,
                        "total_tokens": 5,
                    },
                },
            )
            return

        self._write_json(404, {"error": {"message": "not found"}})

    def _write_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LLMClientTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _MockOpenAIHandler)
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)

    def test_load_settings_from_repo_root_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config").mkdir(parents=True, exist_ok=True)
            (root / ".env").write_text(
                "OPENAI_API_KEY=repo-key\nOPENAI_BASE_URL=http://repo.local/v1\n",
                encoding="utf-8",
            )
            (root / "config/llm.yaml").write_text(
                "\n".join(
                    [
                        "provider: openai_compatible",
                        "generation:",
                        "  model: gpt-5.4-nano-2026-03-17",
                        "embedding:",
                        "  model: text-embedding-3-small",
                        "  dimension: 1536",
                        "  token_limit: 8192",
                        "request:",
                        "  timeout_seconds: 120",
                        "  max_retries: 3",
                        "  backoff_seconds: 2",
                        "rate_limit:",
                        "  calls_per_minute_per_worker: 50",
                        "  async_concurrency: 10",
                    ]
                ),
                encoding="utf-8",
            )

            settings = LLMSettings.from_repo_root(
                root,
                environ={
                    "OPENAI_BASE_URL": self.base_url,
                    "OPENAI_TIMEOUT_SECONDS": "9",
                    "OPENAI_MAX_RETRIES": "4",
                },
            )

        self.assertEqual(settings.api_key, "repo-key")
        self.assertEqual(settings.base_url, self.base_url)
        self.assertEqual(settings.timeout_seconds, 9)
        self.assertEqual(settings.max_retries, 4)
        self.assertEqual(settings.async_concurrency, 10)

    async def test_generate_text_retries_and_collects_metrics(self) -> None:
        _MockOpenAIHandler.chat_attempts = 0
        settings = LLMSettings(
            provider="openai_compatible",
            api_key=None,
            base_url=self.base_url,
            generation_model="gpt-5.4-nano-2026-03-17",
            embedding_model="text-embedding-3-small",
            embedding_dimension=1536,
            embedding_token_limit=8192,
            timeout_seconds=5,
            max_retries=2,
            backoff_seconds=0.01,
            calls_per_minute_per_worker=50,
            async_concurrency=10,
        )
        client = OpenAICompatibleClient(settings)

        result = await client.generate_text(
            ChatRequest(
                request_id="chat-1",
                system_prompt="Bạn là trợ lý.",
                user_prompt="Xin chào",
            )
        )

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.retry_count, 1)
        self.assertEqual(result.response_text, "echo::Xin chào")
        self.assertEqual(_MockOpenAIHandler.chat_attempts, 2)
        metrics = client.metrics_snapshot()
        self.assertEqual(metrics["success_count"], 1)
        self.assertEqual(metrics["total_retry_count"], 1)
        self.assertEqual(metrics["usage_totals"]["total_tokens"], 18)

    async def test_embedding_batch_runs_against_mock_endpoint(self) -> None:
        _MockOpenAIHandler.embedding_attempts = 0
        settings = LLMSettings(
            provider="openai_compatible",
            api_key=None,
            base_url=self.base_url,
            generation_model="gpt-5.4-nano-2026-03-17",
            embedding_model="text-embedding-3-small",
            embedding_dimension=1536,
            embedding_token_limit=8192,
            timeout_seconds=5,
            max_retries=1,
            backoff_seconds=0.01,
            calls_per_minute_per_worker=50,
            async_concurrency=2,
        )
        client = OpenAICompatibleClient(settings)

        results = await client.embed_text_batch(
            [
                EmbeddingRequest(request_id="emb-1", text="alpha"),
                EmbeddingRequest(request_id="emb-2", text="beta"),
            ]
        )

        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.status == "SUCCESS" for result in results))
        self.assertEqual(results[0].embedding, [5.0, 1.0, 2.0])
        self.assertEqual(results[1].embedding, [4.0, 1.0, 2.0])
        self.assertEqual(_MockOpenAIHandler.embedding_attempts, 2)


class IOTests(unittest.TestCase):
    def test_dotenv_loader_and_env_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                "# comment\nOPENAI_API_KEY=from-file\nOPENAI_BASE_URL=\"http://file.local/v1\"\n",
                encoding="utf-8",
            )

            parsed = load_dotenv_values(root / ".env")
            merged = collect_runtime_env(
                root,
                environ={"OPENAI_BASE_URL": "http://env.local/v1"},
            )

        self.assertEqual(parsed["OPENAI_API_KEY"], "from-file")
        self.assertEqual(parsed["OPENAI_BASE_URL"], "http://file.local/v1")
        self.assertEqual(merged["OPENAI_API_KEY"], "from-file")
        self.assertEqual(merged["OPENAI_BASE_URL"], "http://env.local/v1")
