#!/usr/bin/env python3
"""Preprocess raw web page demo data and upload normalized artifacts to MinIO."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import yaml


def load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def nested_get(obj: Dict[str, Any], dotted_key: str) -> Any:
    current: Any = obj
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def normalize_scalar(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def load_records(path: Path, input_format: str) -> Iterable[Dict[str, Any]]:
    if input_format == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        raise ValueError(f"Expected JSON array in {path}")
    if input_format == "jsonl":
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows
    raise ValueError(f"Unsupported input format: {input_format}")


def derive_run_id(explicit_run_id: Optional[str]) -> str:
    if explicit_run_id:
        return explicit_run_id
    return datetime.now(timezone.utc).strftime("preprocess-%Y%m%d%H%M%S")


def derive_source_id(record: Dict[str, Any], id_field: str) -> Optional[str]:
    candidates = [
        nested_get(record, id_field),
        nested_get(record, "_id.$oid"),
        nested_get(record, "_id"),
        record.get("id"),
        record.get("url"),
    ]
    for candidate in candidates:
        value = normalize_scalar(candidate)
        if value:
            return value
    return None


def derive_doc_id(
    record: Dict[str, Any],
    id_field: str,
    content_text: str,
) -> str:
    source_id = derive_source_id(record, id_field)
    if source_id:
        return source_id

    url = normalize_scalar(record.get("url"))
    if url:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    return hashlib.sha256(content_text.encode("utf-8")).hexdigest()


def derive_source_name(record: Dict[str, Any], input_path: Path) -> str:
    domain = normalize_scalar(record.get("domain"))
    if domain:
        return domain

    url = normalize_scalar(record.get("url"))
    if url:
        parsed = urlparse(url)
        if parsed.netloc:
            return parsed.netloc

    return input_path.stem


@dataclass
class NormalizeResult:
    accepted: List[Dict[str, Any]]
    rejected: List[Dict[str, Any]]
    summary: Dict[str, Any]
    output_dir: Path


def normalize_records(
    records: Iterable[Dict[str, Any]],
    *,
    input_path: Path,
    input_format: str,
    input_text_field: str,
    input_id_field: str,
    input_lang_field: str,
    metadata_fields: List[str],
    default_lang: str,
    max_records: int,
    min_content_length: int,
    output_format: str,
    normalized_filename: str,
    reject_manifest_filename: str,
    summary_manifest_filename: str,
    output_dir: Path,
    run_id: str,
) -> NormalizeResult:
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    total_input_records = 0
    valid_candidates = 0
    skipped_due_to_sampling = 0
    reject_reason_counts: Dict[str, int] = {}
    accepted_at = datetime.now(timezone.utc)

    for row_index, record in enumerate(records):
        total_input_records += 1
        raw_content = record.get(input_text_field)

        if raw_content is None:
            reason = "missing_content"
        elif not isinstance(raw_content, str):
            reason = "invalid_content_type"
        else:
            stripped = raw_content.strip()
            if not stripped:
                reason = "empty_content"
            elif len(stripped) < min_content_length:
                reason = "content_too_short"
            else:
                reason = ""

        if reason:
            reject_reason_counts[reason] = reject_reason_counts.get(reason, 0) + 1
            rejected.append(
                {
                    "reject_id": hashlib.sha256(
                        f"{run_id}||{row_index}||{reason}".encode("utf-8")
                    ).hexdigest(),
                    "source_ref": normalize_scalar(derive_source_id(record, input_id_field))
                    or normalize_scalar(record.get("url"))
                    or f"row-{row_index}",
                    "reject_reason": reason,
                    "raw_excerpt": (
                        raw_content[:280] if isinstance(raw_content, str) else normalize_scalar(raw_content)
                    ),
                    "created_ts": accepted_at.isoformat(),
                }
            )
            continue

        valid_candidates += 1
        if len(accepted) >= max_records:
            skipped_due_to_sampling += 1
            continue

        content_text = raw_content.strip()
        doc_id = derive_doc_id(record, input_id_field, content_text)
        source_id = derive_source_id(record, input_id_field)
        lang = normalize_scalar(nested_get(record, input_lang_field)) or default_lang
        metadata: Dict[str, str] = {}
        for field in metadata_fields:
            value = nested_get(record, field)
            normalized = normalize_scalar(value)
            if normalized is not None:
                metadata[field] = normalized

        accepted.append(
            {
                "doc_id": doc_id,
                "source_id": source_id,
                "content": content_text,
                "url": normalize_scalar(record.get("url")),
                "title": normalize_scalar(record.get("title")),
                "lang": lang,
                "source_name": derive_source_name(record, input_path),
                "ingest_date": accepted_at.date().isoformat(),
                "source_file": input_path.name,
                "metadata": metadata,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = output_dir / normalized_filename
    reject_path = output_dir / reject_manifest_filename
    summary_path = output_dir / summary_manifest_filename

    if output_format != "jsonl":
        raise ValueError("This implementation supports jsonl output only")

    with normalized_path.open("w", encoding="utf-8") as handle:
        for row in accepted:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    with reject_path.open("w", encoding="utf-8") as handle:
        for row in rejected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "run_id": run_id,
        "input_path": str(input_path),
        "input_format": input_format,
        "output_format": output_format,
        "created_ts": accepted_at.isoformat(),
        "total_input_records": total_input_records,
        "valid_candidates_before_sampling": valid_candidates,
        "accepted_records": len(accepted),
        "rejected_records": len(rejected),
        "skipped_due_to_sampling_limit": skipped_due_to_sampling,
        "default_lang": default_lang,
        "min_content_length": min_content_length,
        "max_records": max_records,
        "normalized_dataset_fields": [
            "doc_id",
            "source_id",
            "content",
            "url",
            "title",
            "lang",
            "source_name",
            "ingest_date",
            "source_file",
            "metadata",
        ],
        "reject_manifest_fields": [
            "reject_id",
            "source_ref",
            "reject_reason",
            "raw_excerpt",
            "created_ts",
        ],
        "reject_reason_counts": reject_reason_counts,
        "output_files": {
            "normalized_documents": normalized_path.name,
            "reject_manifest": reject_path.name,
            "summary_manifest": summary_path.name,
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return NormalizeResult(
        accepted=accepted,
        rejected=rejected,
        summary=summary,
        output_dir=output_dir,
    )


def upload_artifacts(
    *,
    artifact_dir: Path,
    normalized_filename: str,
    reject_manifest_filename: str,
    summary_manifest_filename: str,
    run_id: str,
    bucket: str,
    minio_endpoint: str,
    minio_access_key: str,
    minio_secret_key: str,
) -> None:
    commands = [
        (
            artifact_dir / normalized_filename,
            f"local/{bucket}/raw/normalized_documents/run_id={run_id}/{normalized_filename}",
        ),
        (
            artifact_dir / reject_manifest_filename,
            f"local/{bucket}/raw/reject_manifest/run_id={run_id}/{reject_manifest_filename}",
        ),
        (
            artifact_dir / summary_manifest_filename,
            f"local/{bucket}/meta/phase2/manifests/preprocess_raw_demo/run_id={run_id}/{summary_manifest_filename}",
        ),
    ]

    base_cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        "kg-construct_phase2",
        "-v",
        f"{artifact_dir}:/artifacts",
        "--entrypoint",
        "/bin/sh",
        "minio/mc",
        "-lc",
    ]

    shell_lines = [
        f"mc alias set local '{minio_endpoint}' '{minio_access_key}' '{minio_secret_key}' >/dev/null",
    ]
    for source_path, target_path in commands:
        shell_lines.append(
            f"mc cp '/artifacts/{source_path.name}' '{target_path}' >/dev/null"
        )
    shell_lines.append("echo MINIO_UPLOAD_OK")

    subprocess.run(base_cmd + [" && ".join(shell_lines)], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root path",
    )
    parser.add_argument(
        "--output-root",
        default="/tmp/kg-construct-phase2/preprocess_raw_demo",
        help="Local artifact directory before upload",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override run_id. Defaults to PHASE2_RUN_ID or timestamp",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Prepare local artifacts only",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    demo_config = load_yaml(repo_root / "config/demo.yaml")
    storage_config = load_yaml(repo_root / "config/storage.yaml")

    env = {}
    env.update(load_env_file(repo_root / ".env.example"))
    env.update(load_env_file(repo_root / ".env"))

    run_id = derive_run_id(args.run_id or env.get("PHASE2_RUN_ID"))
    input_path = repo_root / demo_config["input"]["path"]
    records = load_records(input_path, demo_config["input"]["format"])

    output_dir = Path(args.output_root).resolve() / run_id
    result = normalize_records(
        records,
        input_path=input_path,
        input_format=demo_config["input"]["format"],
        input_text_field=demo_config["input"]["text_field"],
        input_id_field=demo_config["input"]["id_field"],
        input_lang_field=demo_config["input"]["lang_field"],
        metadata_fields=demo_config["input"]["metadata_fields"],
        default_lang=demo_config["fallback"]["default_lang"],
        max_records=demo_config["sampling"]["max_records"],
        min_content_length=demo_config["filters"]["min_content_length"],
        output_format=demo_config["preprocess"]["output_format"],
        normalized_filename=demo_config["preprocess"]["normalized_filename"],
        reject_manifest_filename=demo_config["preprocess"]["reject_manifest_filename"],
        summary_manifest_filename=demo_config["preprocess"]["summary_manifest_filename"],
        output_dir=output_dir,
        run_id=run_id,
    )

    print(f"RUN_ID={run_id}")
    print(f"LOCAL_ARTIFACT_DIR={result.output_dir}")
    print(f"ACCEPTED_RECORDS={result.summary['accepted_records']}")
    print(f"REJECTED_RECORDS={result.summary['rejected_records']}")
    print(f"SKIPPED_DUE_TO_SAMPLING={result.summary['skipped_due_to_sampling_limit']}")

    if not args.skip_upload:
        upload_artifacts(
            artifact_dir=result.output_dir,
            normalized_filename=demo_config["preprocess"]["normalized_filename"],
            reject_manifest_filename=demo_config["preprocess"]["reject_manifest_filename"],
            summary_manifest_filename=demo_config["preprocess"]["summary_manifest_filename"],
            run_id=run_id,
            bucket=storage_config["bucket"],
            minio_endpoint=env.get("MINIO_ENDPOINT", "http://minio:9000"),
            minio_access_key=env.get("MINIO_ACCESS_KEY", "minioadmin"),
            minio_secret_key=env.get("MINIO_SECRET_KEY", "minioadmin123"),
        )
        print(
            "MINIO_NORMALIZED_PATH="
            f"s3://{storage_config['bucket']}/raw/normalized_documents/run_id={run_id}/"
            f"{demo_config['preprocess']['normalized_filename']}"
        )
        print(
            "MINIO_REJECT_PATH="
            f"s3://{storage_config['bucket']}/raw/reject_manifest/run_id={run_id}/"
            f"{demo_config['preprocess']['reject_manifest_filename']}"
        )
        print(
            "MINIO_SUMMARY_PATH="
            f"s3://{storage_config['bucket']}/meta/phase2/manifests/preprocess_raw_demo/run_id={run_id}/"
            f"{demo_config['preprocess']['summary_manifest_filename']}"
        )


if __name__ == "__main__":
    main()
