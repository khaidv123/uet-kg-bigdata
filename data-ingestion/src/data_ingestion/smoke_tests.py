"""Smoke-test helpers for Phase 0 infrastructure validation."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
import psycopg2
import requests
from botocore.exceptions import ClientError

from .bootstrap import (
    bucket_targets_from_env,
    ensure_crawl_state_schema,
    normalize_endpoint_url,
    project_root,
    resolve_project_path,
)


def check_postgres_connection(environ: dict[str, str] | None = None) -> dict[str, Any]:
    """Connect to Postgres and return server metadata."""
    env = os.environ if environ is None else environ
    connection = psycopg2.connect(
        host=env.get("POSTGRES_HOST", "postgres"),
        port=int(env.get("POSTGRES_PORT", "5432")),
        dbname=env.get("POSTGRES_DB", "airflow"),
        user=env.get("POSTGRES_USER", "airflow"),
        password=env.get("POSTGRES_PASSWORD", "change-me"),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, version()")
            current_database, current_user, version = cursor.fetchone()
    finally:
        connection.close()

    return {
        "database": current_database,
        "user": current_user,
        "version": version,
    }


def check_dependency_imports(module_names: list[str]) -> dict[str, str]:
    """Import the required crawler modules and return their file paths."""
    imported: dict[str, str] = {}

    for module_name in module_names:
        module = __import__(module_name)
        imported[module_name] = getattr(module, "__file__", "built-in")

    return imported


def build_smoke_bucket_name(project_name: str) -> str:
    """Create a deterministic, MinIO-safe bucket prefix for smoke checks."""
    sanitized = re.sub(r"[^a-z0-9-]+", "-", project_name.lower()).strip("-")
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    return f"{sanitized[:40]}-smoke"


def check_minio_round_trip(environ: dict[str, str] | None = None) -> dict[str, Any]:
    """Verify MinIO access, raw/meta buckets, and temporary bucket creation."""
    env = os.environ if environ is None else environ
    buckets = bucket_targets_from_env(env)
    client = boto3.client(
        "s3",
        endpoint_url=normalize_endpoint_url(env.get("MINIO_ENDPOINT", "minio:9000")),
        aws_access_key_id=env.get("MINIO_ROOT_USER", "minioadmin"),
        aws_secret_access_key=env.get("MINIO_ROOT_PASSWORD", "change-me"),
        region_name="us-east-1",
    )

    existing_buckets = sorted(bucket["Name"] for bucket in client.list_buckets().get("Buckets", []))
    for bucket_name in (buckets.raw, buckets.meta):
        client.head_bucket(Bucket=bucket_name)

    smoke_bucket = f"{build_smoke_bucket_name(env.get('PROJECT_NAME', 'data-ingestion'))}-{uuid4().hex[:8]}"
    smoke_key = "healthcheck.txt"
    client.create_bucket(Bucket=smoke_bucket)
    client.put_object(Bucket=smoke_bucket, Key=smoke_key, Body=b"ok")
    listed_keys = [obj["Key"] for obj in client.list_objects_v2(Bucket=smoke_bucket).get("Contents", [])]
    client.delete_object(Bucket=smoke_bucket, Key=smoke_key)
    client.delete_bucket(Bucket=smoke_bucket)

    return {
        "existing_buckets": existing_buckets,
        "required_buckets": [buckets.raw, buckets.meta],
        "created_bucket": smoke_bucket,
        "round_trip_keys": listed_keys,
    }


def check_sqlite_round_trip(db_path: str | Path) -> dict[str, Any]:
    """Ensure the crawl-state DB exists and supports write/read/delete."""
    summary = ensure_crawl_state_schema(db_path)
    row_id = uuid4().hex
    record = {
        "url": f"https://example.local/smoke/{row_id}",
        "normalized_url": f"https://example.local/smoke/{row_id}",
        "doc_id": f"smoke-{row_id}",
        "etag": "etag-smoke",
        "last_modified": datetime.now(timezone.utc).isoformat(),
        "content_hash": f"hash-{row_id}",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "status": "NEW",
        "object_key": f"logs/ingestion/smoke/{row_id}.json",
    }

    with sqlite3.connect(db_path) as connection:
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
            """,
            tuple(record.values()),
        )
        fetched = connection.execute(
            "SELECT doc_id, status, object_key FROM crawl_state WHERE normalized_url = ?",
            (record["normalized_url"],),
        ).fetchone()
        connection.execute(
            "DELETE FROM crawl_state WHERE normalized_url = ?",
            (record["normalized_url"],),
        )
        connection.commit()

    return {
        "db_path": summary["db_path"],
        "table": summary["table"],
        "columns": summary["columns"],
        "round_trip_row": {
            "doc_id": fetched[0],
            "status": fetched[1],
            "object_key": fetched[2],
        },
    }


def _airflow_session(environ: dict[str, str] | None = None) -> tuple[requests.Session, str]:
    env = os.environ if environ is None else environ
    base_url = env.get("AIRFLOW_API_URL", "http://airflow-webserver:8080").rstrip("/")
    session = requests.Session()
    session.auth = (
        env.get("AIRFLOW_ADMIN_USERNAME", "admin"),
        env.get("AIRFLOW_ADMIN_PASSWORD", "admin"),
    )
    session.headers.update({"Content-Type": "application/json"})
    return session, base_url


def _request_json(session: requests.Session, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    response = session.request(method=method, url=url, timeout=15, **kwargs)
    response.raise_for_status()
    if not response.text:
        return {}
    return response.json()


def _wait_for_airflow_api(
    session: requests.Session,
    base_url: str,
    *,
    timeout_seconds: int = 90,
) -> dict[str, Any]:
    """Wait until the Airflow API health endpoint responds successfully."""
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            return _request_json(session, "GET", f"{base_url}/api/v1/health")
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(3)

    raise TimeoutError(f"Timed out waiting for Airflow API at {base_url}") from last_error


def check_airflow_smoke_dag(
    environ: dict[str, str] | None = None,
    *,
    dag_id: str = "airflow_smoke_dag",
    poll_seconds: int = 60,
) -> dict[str, Any]:
    """Verify that the Airflow smoke DAG exists and can complete successfully."""
    session, base_url = _airflow_session(environ)

    health = _wait_for_airflow_api(session, base_url)
    dag = _request_json(session, "GET", f"{base_url}/api/v1/dags/{dag_id}")

    existing_runs = _request_json(
        session,
        "GET",
        f"{base_url}/api/v1/dags/{dag_id}/dagRuns",
        params={"order_by": "-start_date", "limit": 10},
    ).get("dag_runs", [])

    latest_success = next((run for run in existing_runs if run.get("state") == "success"), None)
    if latest_success is not None:
        return {
            "health": health,
            "dag_id": dag_id,
            "is_paused": dag.get("is_paused"),
            "validated_run_id": latest_success.get("dag_run_id"),
            "validated_state": latest_success.get("state"),
            "triggered_new_run": False,
        }

    run_id = f"phase0_smoke_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    _request_json(
        session,
        "POST",
        f"{base_url}/api/v1/dags/{dag_id}/dagRuns",
        json={"dag_run_id": run_id},
    )

    deadline = time.time() + poll_seconds
    while time.time() < deadline:
        run = _request_json(session, "GET", f"{base_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}")
        state = run.get("state")
        if state == "success":
            return {
                "health": health,
                "dag_id": dag_id,
                "is_paused": dag.get("is_paused"),
                "validated_run_id": run_id,
                "validated_state": state,
                "triggered_new_run": True,
            }
        if state in {"failed", "upstream_failed"}:
            raise RuntimeError(f"Airflow smoke DAG run failed: {run_id}")
        time.sleep(3)

    raise TimeoutError(f"Timed out waiting for Airflow smoke DAG run: {run_id}")


def run_phase0_smoke_checks(
    *,
    environ: dict[str, str] | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the full Phase 0 smoke suite and return the JSON report."""
    env = os.environ if environ is None else environ
    root = project_root()
    resolved_db_path = resolve_project_path(env.get("METADATA_DB_PATH", "metadata/crawl_state.db"), base_dir=root)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "postgres": check_postgres_connection(env),
            "minio": check_minio_round_trip(env),
            "dependency_imports": check_dependency_imports(
                [
                    "bs4",
                    "boto3",
                    "fitz",
                    "pdfplumber",
                    "pydantic",
                    "requests",
                    "scrapy",
                    "tenacity",
                ]
            ),
            "sqlite": check_sqlite_round_trip(resolved_db_path),
            "airflow": check_airflow_smoke_dag(env),
        },
    }

    if report_path is not None:
        path = resolve_project_path(report_path, base_dir=root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return report
