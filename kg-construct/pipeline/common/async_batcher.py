"""Small async batching utilities used by Phase 2 workers."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Iterable, TypeVar


T = TypeVar("T")
R = TypeVar("R")


class AsyncBatcher:
    """Runs many awaitables with bounded concurrency while preserving order."""

    def __init__(self, concurrency: int) -> None:
        if concurrency <= 0:
            raise ValueError("concurrency must be > 0")
        self.concurrency = concurrency

    async def map(
        self,
        items: Iterable[T],
        worker: Callable[[T], Awaitable[R]],
    ) -> list[R]:
        materialized = list(items)
        results: list[R | None] = [None] * len(materialized)
        semaphore = asyncio.Semaphore(self.concurrency)

        async def run_one(index: int, item: T) -> None:
            async with semaphore:
                results[index] = await worker(item)

        await asyncio.gather(
            *(run_one(index, item) for index, item in enumerate(materialized))
        )
        return [result for result in results if result is not None]
