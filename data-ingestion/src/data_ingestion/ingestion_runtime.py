"""Helpers for orchestrating ingestion crawl runs, manifests, and quality checks."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import boto3
from pydantic import ValidationError

from .bootstrap import (
    bucket_targets_from_env,
    normalize_endpoint_url,
    project_root,
    resolve_project_path,
)
from .contracts import RawHtmlRecord
from .source_registry import enabled_sources, load_source_registry

_FAILED_REQUEST_PATTERN = re.compile(r"<GET\s+([^>]+)>")


def load_json_file(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_file(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def normalize_source_selector(source_id: str | None) -> str | None:
    value = (source_id or "").strip()
    if not value or value.lower() in {"all", "*"}:
        return None
    return value


def resolve_selected_sources(
    *,
    source_id: str | None = None,
    registry_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    source_selector = normalize_source_selector(source_id)
    registry = load_source_registry(path=registry_path)
    selected = [
        source
        for source in enabled_sources(registry)
        if source_selector is None or source.id == source_selector
    ]
    return [
        {
            "id": source.id,
            "source_type": source.source_type,
            "display_name": source.display_name,
            "start_urls": [str(url) for url in source.start_urls],
            "crawl_interval_hours": source.crawl_interval_hours,
        }
        for source in selected
    ]


def summarize_feed_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    record_type_counts: dict[str, int] = {}
    crawl_status_counts: dict[str, int] = {}

    for record in records:
        record_type = record.get("record_type", "unknown")
        crawl_status = record.get("crawl_status", "unknown")
        record_type_counts[record_type] = record_type_counts.get(record_type, 0) + 1
        crawl_status_counts[crawl_status] = crawl_status_counts.get(crawl_status, 0) + 1

    return {
        "item_count": len(records),
        "record_type_counts": record_type_counts,
        "crawl_status_counts": crawl_status_counts,
    }


def summarize_feed_file(path: str | Path) -> dict[str, Any]:
    payload = load_json_file(path)
    if not isinstance(payload, list):
        raise TypeError(f"Expected a list feed payload in {path}")
    return summarize_feed_records(payload)


def load_feed_records(feed_paths: list[str | Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in feed_paths:
        payload = load_json_file(path)
        if not isinstance(payload, list):
            raise TypeError(f"Expected a list feed payload in {path}")
        records.extend(record for record in payload if isinstance(record, dict))
    return records


def summarize_pdf_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {"path": str(manifest_path), "pdf_url_count": 0}

    count = 0
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return {
        "path": str(manifest_path),
        "pdf_url_count": count,
    }


def load_crawl_reports(report_paths: list[str | Path]) -> list[dict[str, Any]]:
    return [load_json_file(path) for path in report_paths]


def summarize_scrapy_log_text(log_text: str) -> dict[str, Any]:
    lines = [line for line in log_text.splitlines() if line.strip()]
    timeout_lines = [line for line in lines if "TimeoutError" in line or "DownloadTimeoutError" in line]
    retry_exhausted_lines = [line for line in lines if "Gave up retrying" in line]
    download_error_lines = [line for line in lines if "Error downloading <GET" in line]
    robots_error_lines = [line for line in lines if "robotstxt" in line and "ERROR" in line]

    failed_urls: list[str] = []
    for line in retry_exhausted_lines + download_error_lines:
        match = _FAILED_REQUEST_PATTERN.search(line)
        if match is not None:
            failed_urls.append(match.group(1))

    failed_urls = _dedupe_preserving_order(failed_urls)
    return {
        "timeout_count": len(timeout_lines),
        "retry_exhausted_count": len(retry_exhausted_lines),
        "download_error_count": len(download_error_lines),
        "robots_error_count": len(robots_error_lines),
        "failed_url_count": len(failed_urls),
        "failed_urls": failed_urls[:20],
        "total_failures": len(retry_exhausted_lines) + len(download_error_lines),
    }


def build_ingestion_manifest(
    *,
    dag_id: str,
    selected_sources: list[dict[str, Any]],
    crawl_reports: list[dict[str, Any]],
    pdf_summary: dict[str, Any],
    max_pages_per_source: int,
    iterations: int,
) -> dict[str, Any]:
    html_items = 0
    pdf_reference_items = 0
    crawl_status_counts: dict[str, int] = {}
    html_new = 0
    html_updated = 0
    html_skipped_unchanged = 0
    errors = 0
    network_error_summary = {
        "timeout_count": 0,
        "retry_exhausted_count": 0,
        "download_error_count": 0,
        "robots_error_count": 0,
        "failed_url_count": 0,
        "failed_urls": [],
        "total_failures": 0,
    }

    for report in crawl_reports:
        counts = report.get("record_type_counts", {})
        html_items += counts.get("html_page", 0)
        pdf_reference_items += counts.get("pdf_reference", 0)

        for status, value in report.get("crawl_status_counts", {}).items():
            crawl_status_counts[status] = crawl_status_counts.get(status, 0) + value

        html_new += report.get("crawl_status_counts", {}).get("NEW", 0)
        html_updated += report.get("crawl_status_counts", {}).get("UPDATED", 0)
        html_skipped_unchanged += report.get("crawl_status_counts", {}).get("SKIPPED_UNCHANGED", 0)
        errors += report.get("crawl_status_counts", {}).get("FAILED", 0)
        errors += report.get("crawl_status_counts", {}).get("unknown", 0)
        report_network_errors = report.get("network_error_summary", {})
        for key in (
            "timeout_count",
            "retry_exhausted_count",
            "download_error_count",
            "robots_error_count",
            "failed_url_count",
            "total_failures",
        ):
            network_error_summary[key] += int(report_network_errors.get(key, 0))
        network_error_summary["failed_urls"] = _dedupe_preserving_order(
            network_error_summary["failed_urls"] + list(report_network_errors.get("failed_urls", []))
        )[:20]

    pdf_url_discovered = int(pdf_summary.get("pdf_url_count", 0))
    errors += int(network_error_summary["total_failures"])

    return {
        "dag_id": dag_id,
        "selected_sources": selected_sources,
        "iterations": iterations,
        "max_pages_per_source": max_pages_per_source,
        "crawl_report_count": len(crawl_reports),
        "html_items": html_items,
        "html_fetched": html_items,
        "html_new": html_new,
        "html_updated": html_updated,
        "html_skipped_unchanged": html_skipped_unchanged,
        "pdf_reference_items_in_feed": pdf_reference_items,
        "pdf_url_discovered": pdf_url_discovered,
        "pdf_downloaded": 0,
        "pdf_text_extracted": 0,
        "pdf_scanned_detected": 0,
        "errors": errors,
        "deferred_pdf_processing": True,
        "pdf_manifest_summary": pdf_summary,
        "crawl_status_counts": crawl_status_counts,
        "network_error_summary": network_error_summary,
    }


def default_project_artifact_dir(raw_path: str | Path | None = None) -> Path:
    root = project_root()
    target = raw_path or "/opt/project/metadata/ingestion_runs"
    return resolve_project_path(target, base_dir=root)


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def html_object_keys_from_records(records: list[dict[str, Any]]) -> list[str]:
    keys = [
        record["object_key"]
        for record in records
        if record.get("record_type") == "html_page" and isinstance(record.get("object_key"), str)
    ]
    return _dedupe_preserving_order(keys)


def fetch_html_objects_from_minio(
    object_keys: list[str],
    *,
    environ: dict[str, str] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    if not object_keys:
        return {}, []

    env = os.environ if environ is None else environ
    buckets = bucket_targets_from_env(env)
    client = boto3.client(
        "s3",
        endpoint_url=normalize_endpoint_url(env.get("MINIO_ENDPOINT", "minio:9000")),
        aws_access_key_id=env.get("MINIO_ROOT_USER", "minioadmin"),
        aws_secret_access_key=env.get("MINIO_ROOT_PASSWORD", "change-me"),
        region_name="us-east-1",
    )

    objects: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    for object_key in _dedupe_preserving_order(object_keys):
        try:
            response = client.get_object(Bucket=buckets.raw, Key=object_key)
            body = response["Body"].read().decode("utf-8")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise TypeError("Expected JSON object payload")
            objects[object_key] = payload
        except Exception as exc:
            failures.append({"object_key": object_key, "error": str(exc)})
    return objects, failures


def build_quality_report(
    *,
    manifest: dict[str, Any],
    feed_records: list[dict[str, Any]],
    stored_html_objects: dict[str, dict[str, Any]],
    object_fetch_failures: list[dict[str, str]],
    thresholds: dict[str, float | int],
    manifest_path: str | Path,
    quality_report_path: str | Path,
) -> dict[str, Any]:
    html_records = [record for record in feed_records if record.get("record_type") == "html_page"]
    html_count = len(html_records)
    html_object_keys = html_object_keys_from_records(feed_records)

    title_present_count = sum(1 for record in html_records if _non_empty_text(record.get("title")))
    text_preview_present_count = sum(
        1 for record in html_records if _non_empty_text(record.get("text_preview"))
    )

    metadata_complete_count = 0
    invalid_html_objects: list[dict[str, str]] = []
    for object_key in html_object_keys:
        payload = stored_html_objects.get(object_key)
        if payload is None:
            continue
        try:
            RawHtmlRecord.model_validate(payload)
            metadata_complete_count += 1
        except ValidationError as exc:
            invalid_html_objects.append(
                {
                    "object_key": object_key,
                    "error": str(exc).splitlines()[0],
                }
            )

    object_expected_count = len(html_object_keys)
    object_found_count = len(stored_html_objects)
    title_ratio = (title_present_count / html_count) if html_count else 1.0
    text_preview_ratio = (text_preview_present_count / html_count) if html_count else 1.0
    metadata_complete_ratio = (
        metadata_complete_count / object_expected_count if object_expected_count else 1.0
    )
    object_match_ratio = (object_found_count / object_expected_count) if object_expected_count else 1.0

    total_errors = int(manifest.get("errors", 0)) + len(object_fetch_failures) + len(invalid_html_objects)
    pdf_url_count = int(manifest.get("pdf_url_discovered", 0))

    failures: list[str] = []
    if html_count <= 0 and pdf_url_count <= 0:
        failures.append("No HTML items and no discovered PDF URLs were produced in this run.")
    if html_count > 0 and title_ratio < float(thresholds["min_title_ratio"]):
        failures.append(
            f"title ratio {title_ratio:.3f} is below threshold {float(thresholds['min_title_ratio']):.3f}"
        )
    if html_count > 0 and text_preview_ratio < float(thresholds["min_text_preview_ratio"]):
        failures.append(
            "text_preview ratio "
            f"{text_preview_ratio:.3f} is below threshold {float(thresholds['min_text_preview_ratio']):.3f}"
        )
    if object_expected_count > 0 and metadata_complete_ratio < float(
        thresholds["min_metadata_completeness_ratio"]
    ):
        failures.append(
            "metadata completeness ratio "
            f"{metadata_complete_ratio:.3f} is below threshold "
            f"{float(thresholds['min_metadata_completeness_ratio']):.3f}"
        )
    if object_expected_count > 0 and object_match_ratio < float(thresholds["min_object_match_ratio"]):
        failures.append(
            f"MinIO object match ratio {object_match_ratio:.3f} is below threshold "
            f"{float(thresholds['min_object_match_ratio']):.3f}"
        )
    if total_errors > int(thresholds["max_error_count"]):
        failures.append(
            f"error count {total_errors} exceeds threshold {int(thresholds['max_error_count'])}"
        )

    return {
        "status": "passed" if not failures else "failed",
        "manifest_path": str(manifest_path),
        "quality_report_path": str(quality_report_path),
        "html_fetched": int(manifest.get("html_fetched", html_count)),
        "html_skipped_unchanged": int(manifest.get("html_skipped_unchanged", 0)),
        "pdf_url_discovered": pdf_url_count,
        "pdf_downloaded": int(manifest.get("pdf_downloaded", 0)),
        "pdf_text_extracted": int(manifest.get("pdf_text_extracted", 0)),
        "pdf_scanned_detected": int(manifest.get("pdf_scanned_detected", 0)),
        "errors": total_errors,
        "html_with_title_count": title_present_count,
        "html_with_title_ratio": round(title_ratio, 4),
        "html_with_text_preview_count": text_preview_present_count,
        "html_with_text_preview_ratio": round(text_preview_ratio, 4),
        "minio_object_expected_count": object_expected_count,
        "minio_object_found_count": object_found_count,
        "minio_object_match_ratio": round(object_match_ratio, 4),
        "metadata_complete_count": metadata_complete_count,
        "metadata_complete_ratio": round(metadata_complete_ratio, 4),
        "object_fetch_failures_count": len(object_fetch_failures),
        "invalid_html_objects_count": len(invalid_html_objects),
        "thresholds": {
            "min_title_ratio": float(thresholds["min_title_ratio"]),
            "min_text_preview_ratio": float(thresholds["min_text_preview_ratio"]),
            "min_metadata_completeness_ratio": float(thresholds["min_metadata_completeness_ratio"]),
            "min_object_match_ratio": float(thresholds["min_object_match_ratio"]),
            "max_error_count": int(thresholds["max_error_count"]),
        },
        "failures": failures,
        "deferred_pdf_processing": bool(manifest.get("deferred_pdf_processing", True)),
        "object_fetch_failures": object_fetch_failures[:10],
        "invalid_html_objects": invalid_html_objects[:10],
    }
