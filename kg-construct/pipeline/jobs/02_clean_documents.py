#!/usr/bin/env python3
"""Clean and normalize bronze.documents into silver.documents_clean."""

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
    return parser.parse_args()


def derive_run_id(explicit_run_id: Optional[str]) -> str:
    if explicit_run_id:
        return explicit_run_id
    return datetime.now(timezone.utc).strftime("clean-%Y%m%d%H%M%S")


def load_configs(repo_root: Path) -> tuple[dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    return pipeline_cfg, storage_cfg


def read_input(
    spark: SparkSession,
    *,
    bucket: str,
    bronze_base_path: str,
    source_run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(bucket, build_run_path(bronze_base_path, source_run_id))
    return spark.read.parquet(input_uri)


def build_clean_documents(
    df: DataFrame,
    *,
    run_id: str,
    cleaning_cfg: dict,
) -> tuple[DataFrame, dict]:
    allowed_languages = [
        str(value).lower().replace("_", "-") for value in cleaning_cfg["allowed_languages"]
    ]
    min_text_length = int(cleaning_cfg["min_text_length"])

    working = df.withColumn("text", F.col("raw_text").cast("string"))

    if cleaning_cfg.get("remove_nul", True):
        working = working.withColumn("text", F.regexp_replace("text", "\u0000", " "))
    if cleaning_cfg.get("replace_broken_unicode", True):
        working = working.withColumn("text", F.regexp_replace("text", "�", " "))
    if cleaning_cfg.get("replace_html_entities", True):
        working = (
            working.withColumn("text", F.regexp_replace("text", "&nbsp;", " "))
            .withColumn("text", F.regexp_replace("text", "&#160;", " "))
            .withColumn("text", F.regexp_replace("text", "&amp;", "&"))
        )
    if cleaning_cfg.get("remove_html_tags", True):
        working = working.withColumn("text", F.regexp_replace("text", "<[^>]+>", " "))
    if cleaning_cfg.get("collapse_whitespace", True):
        working = working.withColumn("text", F.regexp_replace("text", r"\s+", " "))

    working = (
        working.withColumn("text", F.trim(F.col("text")))
        .withColumn("normalized_lang", F.lower(F.regexp_replace(F.col("lang"), "_", "-")))
        .withColumn(
            "is_empty_after_clean",
            F.col("text").isNull() | (F.col("text") == ""),
        )
        .withColumn(
            "is_allowed_lang",
            F.col("normalized_lang").isin(allowed_languages),
        )
        .withColumn(
            "is_too_short",
            F.length(F.col("text")) < F.lit(min_text_length),
        )
    )

    metrics_row = (
        working.agg(
            F.count("*").alias("input_count"),
            F.sum(F.when(F.col("is_empty_after_clean"), 1).otherwise(0)).alias(
                "removed_empty_after_clean"
            ),
            F.sum(F.when(~F.col("is_allowed_lang"), 1).otherwise(0)).alias(
                "removed_disallowed_lang"
            ),
            F.sum(
                F.when(
                    (~F.col("is_empty_after_clean")) & F.col("is_allowed_lang") & F.col("is_too_short"),
                    1,
                ).otherwise(0)
            ).alias("removed_too_short"),
        )
        .collect()[0]
        .asDict()
    )

    cleaned = (
        working.filter(~F.col("is_empty_after_clean"))
        .filter(F.col("is_allowed_lang"))
        .filter(~F.col("is_too_short"))
        .select(
            F.col("doc_id").cast("string").alias("doc_id"),
            F.col("text").cast("string").alias("text"),
            F.col("lang").cast("string").alias("lang"),
            F.col("metadata").cast("string").alias("metadata"),
            F.col("source_file").cast("string").alias("source_file"),
            F.sha2(F.col("text"), 256).alias("text_hash"),
            F.lit(run_id).alias("run_id"),
        )
    )

    metrics_row["output_count"] = cleaned.count()
    return cleaned, metrics_row


def write_output(
    clean_df: DataFrame,
    *,
    bucket: str,
    silver_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(silver_base_path, run_id))
    clean_df.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    pipeline_cfg, storage_cfg = load_configs(repo_root)
    run_id = derive_run_id(args.run_id)

    spark = SparkSession.builder.appName("phase2-02-clean-documents").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try:
        bucket = storage_cfg["bucket"]
        bronze_base_path = storage_cfg["tables"]["bronze.documents"]
        silver_base_path = storage_cfg["tables"]["silver.documents_clean"]
        source_run_id = args.source_run_id or resolve_latest_run_id(
            spark, bucket, bronze_base_path
        )

        input_df = read_input(
            spark,
            bucket=bucket,
            bronze_base_path=bronze_base_path,
            source_run_id=source_run_id,
        )
        clean_df, metrics = build_clean_documents(
            input_df,
            run_id=run_id,
            cleaning_cfg=pipeline_cfg["cleaning"],
        )
        output_uri = write_output(
            clean_df,
            bucket=bucket,
            silver_base_path=silver_base_path,
            run_id=run_id,
        )

        print(f"CLEAN_RUN_ID={run_id}")
        print(f"SOURCE_RUN_ID={source_run_id}")
        print(f"INPUT_RECORD_COUNT={metrics['input_count']}")
        print(f"OUTPUT_RECORD_COUNT={metrics['output_count']}")
        print(f"REMOVED_EMPTY_AFTER_CLEAN={metrics['removed_empty_after_clean']}")
        print(f"REMOVED_DISALLOWED_LANG={metrics['removed_disallowed_lang']}")
        print(f"REMOVED_TOO_SHORT={metrics['removed_too_short']}")
        print(f"CLEAN_OUTPUT_PATH={output_uri}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
