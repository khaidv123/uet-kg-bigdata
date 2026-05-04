"""Bootstrap helpers for storage, metadata, and logging setup."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

CRAWL_STATE_FIELDS = [
    "url",
    "normalized_url",
    "doc_id",
    "etag",
    "last_modified",
    "content_hash",
    "fetched_at",
    "status",
    "object_key",
]

DEFAULT_SQLITE_STATUSES = ("NEW", "UPDATED", "SKIPPED_UNCHANGED", "FAILED")


@dataclass(frozen=True)
class BucketTargets:
    raw: str
    meta: str


def project_root() -> Path:
    """Return the repository root from the installed package layout."""
    return Path(__file__).resolve().parents[2]


def resolve_project_path(raw_path: str | Path, base_dir: Path | None = None) -> Path:
    """Resolve project-relative paths for both host and container execution."""
    path = Path(raw_path)
    if path.is_absolute():
        return path
    root = project_root() if base_dir is None else base_dir
    return root / path


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    """Load a YAML config file into a dictionary."""
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise TypeError(f"Expected a mapping in {path}, got {type(data).__name__}")
    return data


def bucket_targets_from_env(environ: dict[str, str] | None = None) -> BucketTargets:
    """Read the MinIO bucket names with stable defaults."""
    env = os.environ if environ is None else environ
    return BucketTargets(
        raw=env.get("MINIO_BUCKET_RAW", "uet-raw"),
        meta=env.get("MINIO_BUCKET_META", "uet-meta"),
    )


def normalize_endpoint_url(endpoint: str) -> str:
    """Ensure the MinIO endpoint contains a scheme for boto3."""
    if endpoint.startswith(("http://", "https://")):
        return endpoint
    return f"http://{endpoint}"


def render_storage_prefixes(layout: dict[str, Any], run_date: date) -> dict[str, list[str]]:
    """Render the configured logical prefixes into bucket-scoped object keys."""
    placeholder_name = layout.get("placeholder_name", ".keep")
    raw_templates = layout.get("raw_prefix_templates", {})
    meta_prefixes = layout.get("meta_prefixes", {})

    values = {
        "yyyy": f"{run_date:%Y}",
        "mm": f"{run_date:%m}",
        "dd": f"{run_date:%d}",
    }

    rendered = {
        "raw": [f"{template.format(**values)}{placeholder_name}" for template in raw_templates.values()],
        "meta": [f"{prefix}{placeholder_name}" for prefix in meta_prefixes.values()],
    }
    return rendered


def crawl_state_schema_definition() -> dict[str, Any]:
    """Return a machine-readable definition of the crawl state contract."""
    return {
        "table": "crawl_state",
        "fields": [
            {"name": "url", "type": "TEXT", "nullable": False},
            {"name": "normalized_url", "type": "TEXT", "nullable": False, "primary_key": True},
            {"name": "doc_id", "type": "TEXT", "nullable": False},
            {"name": "etag", "type": "TEXT", "nullable": True},
            {"name": "last_modified", "type": "TEXT", "nullable": True},
            {"name": "content_hash", "type": "TEXT", "nullable": True},
            {"name": "fetched_at", "type": "TEXT", "nullable": False},
            {"name": "status", "type": "TEXT", "nullable": False, "allowed_values": list(DEFAULT_SQLITE_STATUSES)},
            {"name": "object_key", "type": "TEXT", "nullable": False},
        ],
        "indexes": [
            {"name": "idx_crawl_state_doc_id", "columns": ["doc_id"]},
            {"name": "idx_crawl_state_status", "columns": ["status"]},
        ],
    }


def ensure_crawl_state_schema(db_path: str | Path) -> dict[str, Any]:
    """Create the SQLite crawl state schema if it does not already exist."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crawl_state (
                url TEXT NOT NULL,
                normalized_url TEXT NOT NULL PRIMARY KEY,
                doc_id TEXT NOT NULL,
                etag TEXT,
                last_modified TEXT,
                content_hash TEXT,
                fetched_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('NEW', 'UPDATED', 'SKIPPED_UNCHANGED', 'FAILED')),
                object_key TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_crawl_state_doc_id ON crawl_state (doc_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_crawl_state_status ON crawl_state (status)"
        )
        columns = connection.execute("PRAGMA table_info(crawl_state)").fetchall()
        connection.commit()

    return {
        "db_path": str(path.resolve()),
        "table": "crawl_state",
        "columns": [row[1] for row in columns],
        "journal_mode": "wal",
    }


def write_schema_snapshot(target_path: str | Path) -> Path:
    """Write the crawl state contract to a JSON file for human review."""
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(crawl_state_schema_definition(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
