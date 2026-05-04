"""Export current MinIO raw data and run artifacts to a Hugging Face dataset repo."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import boto3
from dotenv import load_dotenv
from huggingface_hub import HfApi

from data_ingestion.bootstrap import (
    bucket_targets_from_env,
    normalize_endpoint_url,
    project_root,
    resolve_project_path,
)
from data_ingestion.ingestion_runtime import load_json_file


def _as_bool(value: str | bool | None, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default=os.environ.get("HF_REPO_ID"))
    parser.add_argument("--repo-type", default=os.environ.get("HF_REPO_TYPE", "dataset"))
    parser.add_argument("--private", default=os.environ.get("HF_PRIVATE", "true"))
    parser.add_argument("--token-env", default="HF_TOKEN")
    parser.add_argument(
        "--stage-dir",
        default=os.environ.get(
            "HF_STAGE_DIR",
            "/opt/project/metadata/hf_stage/full_batch_2026_04_18",
        ),
    )
    parser.add_argument(
        "--raw-prefix",
        default=os.environ.get("HF_RAW_PREFIX", "html/"),
        help="MinIO raw-bucket prefix to export.",
    )
    parser.add_argument(
        "--ingestion-manifest-path",
        default=os.environ.get(
            "INGESTION_MANIFEST_PATH",
            "/opt/project/metadata/full_batch_runs/2026-04-18/ingestion_manifest.json",
        ),
    )
    parser.add_argument(
        "--ingestion-quality-report-path",
        default=os.environ.get(
            "INGESTION_QUALITY_REPORT_PATH",
            "/opt/project/metadata/full_batch_runs/2026-04-18/ingestion_quality_report.json",
        ),
    )
    parser.add_argument(
        "--crawl-report-path",
        default=os.environ.get(
            "HF_CRAWL_REPORT_PATH",
            "/opt/project/metadata/full_batch_runs/2026-04-18/ingestion_runs/crawl_report_run_1.json",
        ),
    )
    parser.add_argument(
        "--feed-path",
        default=os.environ.get(
            "HF_FEED_PATH",
            "/opt/project/metadata/full_batch_runs/2026-04-18/ingestion_runs/crawl_feed_run_1.json",
        ),
    )
    parser.add_argument(
        "--pdf-manifest-path",
        default=os.environ.get("PDF_URL_DISCOVERY_PATH", "/opt/project/metadata/discovered_pdf_urls.jsonl"),
    )
    parser.add_argument(
        "--crawl-state-path",
        default=os.environ.get("METADATA_DB_PATH", "/opt/project/metadata/crawl_state.db"),
    )
    parser.add_argument(
        "--skip-feed",
        action="store_true",
        help="Skip uploading the large crawl feed JSON if you only want manifests and raw objects.",
    )
    parser.add_argument(
        "--skip-stage-refresh",
        action="store_true",
        help="Reuse an existing stage dir instead of rebuilding it.",
    )
    return parser.parse_args()


def ensure_repo(api: HfApi, repo_id: str, repo_type: str, private: bool) -> None:
    api.create_repo(repo_id=repo_id, repo_type=repo_type, private=private, exist_ok=True)


def build_s3_client() -> boto3.client:
    env = os.environ
    return boto3.client(
        "s3",
        endpoint_url=normalize_endpoint_url(env.get("MINIO_ENDPOINT", "minio:9000")),
        aws_access_key_id=env.get("MINIO_ROOT_USER", "minioadmin"),
        aws_secret_access_key=env.get("MINIO_ROOT_PASSWORD", "change-me"),
        region_name="us-east-1",
    )


def stage_raw_bucket(stage_dir: Path, raw_prefix: str) -> tuple[int, int]:
    client = build_s3_client()
    bucket = bucket_targets_from_env(os.environ).raw
    raw_target = stage_dir / "minio" / bucket
    raw_target.mkdir(parents=True, exist_ok=True)

    count = 0
    total_bytes = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=raw_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            size = int(obj["Size"])
            if size == 0:
                continue
            destination = raw_target / key
            destination.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(destination))
            count += 1
            total_bytes += size
    return count, total_bytes


def copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build_dataset_card(
    *,
    stage_dir: Path,
    repo_id: str,
    manifest_path: Path,
    quality_report_path: Path,
    crawl_report_path: Path,
    exported_object_count: int,
    exported_total_bytes: int,
) -> None:
    manifest = load_json_file(manifest_path)
    quality_report = load_json_file(quality_report_path)
    crawl_report = load_json_file(crawl_report_path)

    readme = stage_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                f"# {repo_id}",
                "",
                "Exported from the Phase 1 UET ingestion stack.",
                "",
                "## Summary",
                "",
                f"- html_fetched: {manifest.get('html_fetched')}",
                f"- html_new: {manifest.get('html_new')}",
                f"- html_updated: {manifest.get('html_updated')}",
                f"- html_skipped_unchanged: {manifest.get('html_skipped_unchanged')}",
                f"- pdf_url_discovered: {manifest.get('pdf_url_discovered')}",
                f"- network_failures: {manifest.get('network_error_summary', {}).get('total_failures', 0)}",
                f"- quality_status: {quality_report.get('status')}",
                f"- raw_object_count_exported: {exported_object_count}",
                f"- raw_bytes_exported: {exported_total_bytes}",
                f"- crawl_duration_seconds: {crawl_report.get('duration_seconds')}",
                "",
                "## Layout",
                "",
                "- `minio/uet-raw/html/...`: exported raw HTML JSON objects from MinIO",
                "- `artifacts/`: manifests, reports, SQLite state DB, and optional crawl feed",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    root = project_root()
    load_dotenv(root / ".env", override=False)
    args = parse_args()

    if not args.repo_id:
        raise ValueError("HF_REPO_ID is required.")

    token = os.environ.get(args.token_env)
    if not token:
        raise ValueError(f"{args.token_env} is required.")

    stage_dir = resolve_project_path(args.stage_dir, base_dir=root)
    if not args.skip_stage_refresh and stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = resolve_project_path(args.ingestion_manifest_path, base_dir=root)
    quality_report_path = resolve_project_path(args.ingestion_quality_report_path, base_dir=root)
    crawl_report_path = resolve_project_path(args.crawl_report_path, base_dir=root)
    feed_path = resolve_project_path(args.feed_path, base_dir=root)
    pdf_manifest_path = resolve_project_path(args.pdf_manifest_path, base_dir=root)
    crawl_state_path = resolve_project_path(args.crawl_state_path, base_dir=root)

    exported_object_count = 0
    exported_total_bytes = 0
    if not args.skip_stage_refresh:
        exported_object_count, exported_total_bytes = stage_raw_bucket(stage_dir, args.raw_prefix)

        artifacts_dir = stage_dir / "artifacts"
        copy_if_exists(manifest_path, artifacts_dir / "ingestion_manifest.json")
        copy_if_exists(quality_report_path, artifacts_dir / "ingestion_quality_report.json")
        copy_if_exists(crawl_report_path, artifacts_dir / "crawl_report_run_1.json")
        copy_if_exists(pdf_manifest_path, artifacts_dir / "discovered_pdf_urls.jsonl")
        copy_if_exists(crawl_state_path, artifacts_dir / "crawl_state.db")
        if not args.skip_feed:
            copy_if_exists(feed_path, artifacts_dir / "crawl_feed_run_1.json")

        build_dataset_card(
            stage_dir=stage_dir,
            repo_id=args.repo_id,
            manifest_path=manifest_path,
            quality_report_path=quality_report_path,
            crawl_report_path=crawl_report_path,
            exported_object_count=exported_object_count,
            exported_total_bytes=exported_total_bytes,
        )

        export_summary = stage_dir / "export_summary.json"
        export_summary.write_text(
            json.dumps(
                {
                    "repo_id": args.repo_id,
                    "repo_type": args.repo_type,
                    "exported_object_count": exported_object_count,
                    "exported_total_bytes": exported_total_bytes,
                    "raw_prefix": args.raw_prefix,
                    "skip_feed": args.skip_feed,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    api = HfApi(token=token)
    ensure_repo(api, args.repo_id, args.repo_type, _as_bool(args.private, default=True))

    api.upload_folder(
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        folder_path=str(stage_dir),
        path_in_repo=".",
    )

    print(json.dumps({"repo_id": args.repo_id, "repo_type": args.repo_type, "stage_dir": str(stage_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
