#!/usr/bin/env python3
"""Load normalized raw documents from MinIO into bronze.documents."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pyspark.sql import DataFrame, SparkSession, functions as F

from pipeline.common.config_loader import load_yaml
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(repo_root))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def derive_run_id(explicit_run_id: Optional[str]) -> str:
    if explicit_run_id:
        return explicit_run_id
    return datetime.now(timezone.utc).strftime("ingest-%Y%m%d%H%M%S")


def load_configs(repo_root: Path) -> tuple[dict, dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    demo_cfg = load_yaml(repo_root / "config/demo.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    return pipeline_cfg, demo_cfg, storage_cfg


def read_input(
    spark: SparkSession,
    *,
    bucket: str,
    normalized_base_path: str,
    normalized_filename: str,
    source_run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(
        bucket,
        build_run_path(normalized_base_path, source_run_id, normalized_filename),
    )
    return spark.read.json(input_uri)


def build_bronze_documents(
    df: DataFrame,
    *,
    run_id: str,
    default_lang: str,
) -> tuple[DataFrame, int]:
    metadata_json = F.to_json(F.col("metadata"))
    metadata_lang = F.get_json_object(metadata_json, "$.lang")
    resolved_lang = (
        F.when(F.col("lang").isNotNull() & (F.trim(F.col("lang")) != ""), F.col("lang"))
        .when(metadata_lang.isNotNull() & (F.trim(metadata_lang) != ""), metadata_lang)
        .otherwise(F.lit(default_lang))
    )

    missing_lang_count = (
        df.select(
            F.when(
                (F.col("lang").isNull() | (F.trim(F.col("lang")) == ""))
                & (metadata_lang.isNull() | (F.trim(metadata_lang) == "")),
                F.lit(1),
            ).otherwise(F.lit(0)).alias("needs_default_lang")
        )
        .agg(F.sum("needs_default_lang").alias("needs_default_lang"))
        .collect()[0]["needs_default_lang"]
        or 0
    )

    bronze = (
        df.select(
            F.col("doc_id").cast("string").alias("doc_id"),
            F.col("content").cast("string").alias("raw_text"),
            resolved_lang.cast("string").alias("lang"),
            metadata_json.cast("string").alias("metadata"),
            F.col("source_file").cast("string").alias("source_file"),
            F.current_timestamp().alias("ingest_ts"),
            F.lit(run_id).alias("run_id"),
        )
        .where(F.col("doc_id").isNotNull() & F.col("raw_text").isNotNull())
    )

    return bronze, missing_lang_count


def write_output(
    bronze_df: DataFrame,
    *,
    bucket: str,
    bronze_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(bronze_base_path, run_id))
    (
        bronze_df.write.mode("overwrite")
        .format("parquet")
        .save(output_uri)
    )
    return output_uri


def validate_row_count(input_df: DataFrame, bronze_df: DataFrame) -> None:
    input_count = input_df.count()
    output_count = bronze_df.count()
    if input_count != output_count:
        raise RuntimeError(
            f"Row count mismatch after ingest: input={input_count}, bronze={output_count}"
        )


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    pipeline_cfg, demo_cfg, storage_cfg = load_configs(repo_root)

    run_id = derive_run_id(args.run_id)
    default_lang = pipeline_cfg["runtime"]["default_lang"]
    bucket = storage_cfg["bucket"]
    normalized_base_path = storage_cfg["tables"]["raw.normalized_documents"]
    bronze_base_path = storage_cfg["tables"]["bronze.documents"]
    normalized_filename = demo_cfg["preprocess"]["normalized_filename"]

    spark = SparkSession.builder.appName("phase2-01-ingest-documents").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try:
        source_run_id = args.source_run_id or resolve_latest_run_id(
            spark, bucket, normalized_base_path
        )
        input_df = read_input(
            spark,
            bucket=bucket,
            normalized_base_path=normalized_base_path,
            normalized_filename=normalized_filename,
            source_run_id=source_run_id,
        )
        if args.limit is not None:
            input_df = input_df.orderBy("doc_id").limit(max(args.limit, 0))

        bronze_df, missing_lang_count = build_bronze_documents(
            input_df, run_id=run_id, default_lang=default_lang
        )
        validate_row_count(input_df, bronze_df)
        output_uri = write_output(
            bronze_df,
            bucket=bucket,
            bronze_base_path=bronze_base_path,
            run_id=run_id,
        )

        print(f"INGEST_RUN_ID={run_id}")
        print(f"SOURCE_RUN_ID={source_run_id}")
        print(f"LIMIT={args.limit if args.limit is not None else ''}")
        print(f"INPUT_RECORD_COUNT={input_df.count()}")
        print(f"BRONZE_RECORD_COUNT={bronze_df.count()}")
        print(f"LANG_FALLBACK_COUNT={missing_lang_count}")
        if missing_lang_count > 0:
            print(f"LANG_FALLBACK_DEFAULT={default_lang}")
        print(f"BRONZE_OUTPUT_PATH={output_uri}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
