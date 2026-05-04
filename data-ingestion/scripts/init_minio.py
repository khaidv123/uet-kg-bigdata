#!/usr/bin/env python3
"""Create the MinIO buckets and prefix placeholders required for ingestion."""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date

import boto3
from botocore.exceptions import ClientError

from data_ingestion.bootstrap import (
    bucket_targets_from_env,
    load_yaml_file,
    normalize_endpoint_url,
    project_root,
    render_storage_prefixes,
    resolve_project_path,
)
from data_ingestion.logging_utils import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config/storage_layout.yaml",
        help="Path to the storage layout YAML file.",
    )
    parser.add_argument(
        "--run-date",
        default=date.today().isoformat(),
        help="Date used for date-partitioned prefix placeholders in YYYY-MM-DD format.",
    )
    return parser.parse_args()


def ensure_bucket(client, bucket_name: str) -> str:
    try:
        client.head_bucket(Bucket=bucket_name)
        return "exists"
    except ClientError:
        client.create_bucket(Bucket=bucket_name)
        return "created"


def main() -> None:
    args = parse_args()
    root = project_root()
    configure_logging(project_dir=root)
    logger = logging.getLogger("data_ingestion.bootstrap.minio")

    config_path = resolve_project_path(args.config, base_dir=root)
    storage_layout = load_yaml_file(config_path)
    run_day = date.fromisoformat(args.run_date)
    rendered_prefixes = render_storage_prefixes(storage_layout, run_day)
    buckets = bucket_targets_from_env()

    client = boto3.client(
        "s3",
        endpoint_url=normalize_endpoint_url(os.environ.get("MINIO_ENDPOINT", "minio:9000")),
        aws_access_key_id=os.environ.get("MINIO_ROOT_USER", "minioadmin"),
        aws_secret_access_key=os.environ.get("MINIO_ROOT_PASSWORD", "change-me"),
        region_name="us-east-1",
    )

    bucket_status = {
        buckets.raw: ensure_bucket(client, buckets.raw),
        buckets.meta: ensure_bucket(client, buckets.meta),
    }

    created_objects: dict[str, list[str]] = {buckets.raw: [], buckets.meta: []}
    for key in rendered_prefixes["raw"]:
        client.put_object(Bucket=buckets.raw, Key=key, Body=b"")
        created_objects[buckets.raw].append(key)
    for key in rendered_prefixes["meta"]:
        client.put_object(Bucket=buckets.meta, Key=key, Body=b"")
        created_objects[buckets.meta].append(key)

    summary = {
        "config_path": str(config_path.resolve()),
        "run_date": args.run_date,
        "bucket_status": bucket_status,
        "objects_written": created_objects,
    }
    logger.info("Initialized MinIO layout: %s", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
