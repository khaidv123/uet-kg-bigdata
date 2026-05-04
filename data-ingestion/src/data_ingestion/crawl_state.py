"""SQLite helpers for crawl-state reads and writes."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bootstrap import ensure_crawl_state_schema


@dataclass(frozen=True)
class CrawlStateDecision:
    status: str
    matched_on: tuple[str, ...]
    existing: dict[str, Any] | None


class CrawlStateStore:
    """Small wrapper around the Phase 1 SQLite crawl-state table."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        ensure_crawl_state_schema(self.db_path)

    def fetch(self, normalized_url: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT
                    url,
                    normalized_url,
                    doc_id,
                    etag,
                    last_modified,
                    content_hash,
                    fetched_at,
                    status,
                    object_key
                FROM crawl_state
                WHERE normalized_url = ?
                """,
                (normalized_url,),
            ).fetchone()

        if row is None:
            return None

        return {
            "url": row[0],
            "normalized_url": row[1],
            "doc_id": row[2],
            "etag": row[3],
            "last_modified": row[4],
            "content_hash": row[5],
            "fetched_at": row[6],
            "status": row[7],
            "object_key": row[8],
        }

    def upsert(self, record: dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO crawl_state (
                    url,
                    normalized_url,
                    doc_id,
                    etag,
                    last_modified,
                    content_hash,
                    fetched_at,
                    status,
                    object_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_url) DO UPDATE SET
                    url = excluded.url,
                    doc_id = excluded.doc_id,
                    etag = excluded.etag,
                    last_modified = excluded.last_modified,
                    content_hash = excluded.content_hash,
                    fetched_at = excluded.fetched_at,
                    status = excluded.status,
                    object_key = excluded.object_key
                """,
                (
                    record["url"],
                    record["normalized_url"],
                    record["doc_id"],
                    record.get("etag"),
                    record.get("last_modified"),
                    record.get("content_hash"),
                    record["fetched_at"],
                    record["status"],
                    record["object_key"],
                ),
            )
            connection.commit()

    def evaluate_change(
        self,
        normalized_url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        content_hash: str | None = None,
    ) -> CrawlStateDecision:
        """Classify the incoming record against the stored crawl-state entry."""
        existing = self.fetch(normalized_url)
        if existing is None:
            return CrawlStateDecision(status="NEW", matched_on=(), existing=None)

        matched_on: list[str] = []
        existing_content_hash = existing.get("content_hash")
        existing_etag = existing.get("etag")
        existing_last_modified = existing.get("last_modified")

        if content_hash and existing_content_hash:
            if content_hash == existing_content_hash:
                matched_on.append("content_hash")
                if etag and existing_etag and etag == existing_etag:
                    matched_on.append("etag")
                if last_modified and existing_last_modified and last_modified == existing_last_modified:
                    matched_on.append("last_modified")
                return CrawlStateDecision(
                    status="SKIPPED_UNCHANGED",
                    matched_on=tuple(matched_on),
                    existing=existing,
                )
            return CrawlStateDecision(
                status="UPDATED",
                matched_on=(),
                existing=existing,
            )

        if etag and existing_etag and etag == existing_etag:
            matched_on.append("etag")
        if last_modified and existing_last_modified and last_modified == existing_last_modified:
            matched_on.append("last_modified")

        if matched_on:
            return CrawlStateDecision(
                status="SKIPPED_UNCHANGED",
                matched_on=tuple(matched_on),
                existing=existing,
            )

        return CrawlStateDecision(status="UPDATED", matched_on=(), existing=existing)
