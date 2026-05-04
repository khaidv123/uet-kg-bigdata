#!/usr/bin/env python3
"""Validate raw concept responses and build concept mapping/coverage tables."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from pyspark.sql import DataFrame, SparkSession, Window, functions as F, types as T

from pipeline.common.concept_validation import parse_concept_response
from pipeline.common.config_loader import load_yaml
from pipeline.common.io import json_dumps
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


EXPECTED_NODE_TYPES = ["entity", "event", "relation"]

PARSED_SCHEMA = T.StructType(
    [
        T.StructField("concept_request_id", T.StringType(), False),
        T.StructField("node_name", T.StringType(), False),
        T.StructField("node_type", T.StringType(), False),
        T.StructField("prompt_version", T.StringType(), False),
        T.StructField("context_version", T.StringType(), False),
        T.StructField("model_name", T.StringType(), False),
        T.StructField("source_status", T.StringType(), False),
        T.StructField("parse_status", T.StringType(), False),
        T.StructField("error_message", T.StringType(), True),
        T.StructField("parsed_concepts", T.ArrayType(T.StringType()), False),
        T.StructField("raw_response", T.StringType(), True),
        T.StructField("response_excerpt", T.StringType(), True),
        T.StructField("raw_run_id", T.StringType(), False),
        T.StructField("run_id", T.StringType(), False),
        T.StructField("created_ts", T.TimestampType(), False),
    ]
)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(repo_root))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--raw-run-ids", default=None)
    parser.add_argument("--concept-request-run-id", default=None)
    parser.add_argument("--missing-concepts-run-id", default=None)
    parser.add_argument("--graph-base-run-id", default=None)
    return parser.parse_args()


def derive_run_id(explicit_run_id: Optional[str]) -> str:
    if explicit_run_id:
        return explicit_run_id
    return datetime.now(timezone.utc).strftime("validconcept-%Y%m%d%H%M%S")


def load_configs(repo_root: Path) -> tuple[dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    return pipeline_cfg, storage_cfg


def read_table(
    spark: SparkSession,
    *,
    bucket: str,
    base_path: str,
    run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(bucket, build_run_path(base_path, run_id))
    return spark.read.parquet(input_uri)


def parse_raw_run_ids(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def read_raw_runs(
    spark: SparkSession,
    *,
    bucket: str,
    concept_raw_base_path: str,
    raw_run_ids: list[str],
) -> DataFrame:
    raw_frames = [
        read_table(
            spark,
            bucket=bucket,
            base_path=concept_raw_base_path,
            run_id=raw_run_id,
        )
        for raw_run_id in raw_run_ids
    ]
    if not raw_frames:
        raise ValueError("At least one concept raw run id is required")
    return reduce(lambda left, right: left.unionByName(right), raw_frames)


def _response_excerpt(response_text: str | None, max_length: int = 500) -> str | None:
    if response_text is None:
        return None
    compact = " ".join(response_text.split())
    return compact[:max_length]


def parse_raw_rows(rows: Iterable, *, run_id: str) -> Iterator[tuple]:
    for row in rows:
        source_status = str(row["status"] or "")
        now = datetime.utcnow()
        raw_response = row["response_text"]
        base_values = {
            "concept_request_id": row["concept_request_id"],
            "node_name": row["node_name"],
            "node_type": str(row["node_type"] or "").lower(),
            "prompt_version": row["prompt_version"],
            "context_version": row["context_version"],
            "model_name": row["model_name"],
            "source_status": source_status,
            "raw_response": raw_response,
            "response_excerpt": _response_excerpt(raw_response),
            "raw_run_id": row["raw_run_id"],
            "run_id": run_id,
            "created_ts": now,
        }

        if source_status != "SUCCESS":
            yield (
                base_values["concept_request_id"],
                base_values["node_name"],
                base_values["node_type"],
                base_values["prompt_version"],
                base_values["context_version"],
                base_values["model_name"],
                base_values["source_status"],
                "NOT_PARSED",
                row["error_message"] or f"source_status={source_status}",
                [],
                base_values["raw_response"],
                base_values["response_excerpt"],
                base_values["raw_run_id"],
                base_values["run_id"],
                base_values["created_ts"],
            )
            continue

        try:
            concepts = parse_concept_response(raw_response)
            parse_status = "VALID" if concepts else "EMPTY"
            yield (
                base_values["concept_request_id"],
                base_values["node_name"],
                base_values["node_type"],
                base_values["prompt_version"],
                base_values["context_version"],
                base_values["model_name"],
                base_values["source_status"],
                parse_status,
                None,
                concepts,
                base_values["raw_response"],
                base_values["response_excerpt"],
                base_values["raw_run_id"],
                base_values["run_id"],
                base_values["created_ts"],
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            yield (
                base_values["concept_request_id"],
                base_values["node_name"],
                base_values["node_type"],
                base_values["prompt_version"],
                base_values["context_version"],
                base_values["model_name"],
                base_values["source_status"],
                "INVALID",
                str(exc),
                [],
                base_values["raw_response"],
                base_values["response_excerpt"],
                base_values["raw_run_id"],
                base_values["run_id"],
                base_values["created_ts"],
            )


def dedupe_latest_raw(raw_df: DataFrame) -> DataFrame:
    selected = raw_df.select(
        F.col("concept_request_id").cast("string").alias("concept_request_id"),
        F.col("node_name").cast("string").alias("node_name"),
        F.lower(F.col("node_type")).cast("string").alias("node_type"),
        F.col("prompt_version").cast("string").alias("prompt_version"),
        F.col("context_version").cast("string").alias("context_version"),
        F.col("model_name").cast("string").alias("model_name"),
        F.col("response_text").cast("string").alias("response_text"),
        F.col("status").cast("string").alias("status"),
        F.col("error_message").cast("string").alias("error_message"),
        F.col("created_ts").cast("timestamp").alias("raw_created_ts"),
        F.col("run_id").cast("string").alias("raw_run_id"),
    )
    ranked = selected.withColumn(
        "raw_rank",
        F.row_number().over(
            Window.partitionBy("concept_request_id").orderBy(
                F.col("raw_created_ts").desc_nulls_last(),
                F.col("raw_run_id").desc(),
            )
        ),
    )
    return ranked.filter(F.col("raw_rank") == 1).drop("raw_rank")


def parse_responses(spark: SparkSession, raw_df: DataFrame, *, run_id: str) -> DataFrame:
    latest_raw = dedupe_latest_raw(raw_df)
    parsed_rdd = latest_raw.rdd.mapPartitions(lambda rows: parse_raw_rows(rows, run_id=run_id))
    return spark.createDataFrame(parsed_rdd, schema=PARSED_SCHEMA)


def build_concept_mappings(
    parsed_df: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    return (
        parsed_df.filter(F.col("parse_status") == "VALID")
        .select(
            "concept_request_id",
            "node_name",
            "node_type",
            F.explode("parsed_concepts").alias("concept_name"),
            "prompt_version",
            "context_version",
            "model_name",
            "raw_response",
            "raw_run_id",
        )
        .withColumn("concept_id", F.sha2(F.concat(F.col("concept_name"), F.lit("_concept")), 256))
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
        .select(
            "concept_request_id",
            "node_name",
            "node_type",
            "concept_name",
            "concept_id",
            "prompt_version",
            "context_version",
            "model_name",
            "raw_response",
            "raw_run_id",
            "run_id",
            "schema_version",
        )
    )


def build_concept_coverage(
    missing_concepts: DataFrame,
    concept_requests: DataFrame,
    parsed_df: DataFrame,
    concept_mappings: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    missing = (
        missing_concepts.select(
            F.trim(F.col("name")).alias("name"),
            F.lower(F.trim(F.col("node_type"))).alias("node_type"),
        )
        .filter((F.length("name") > 0) & F.col("node_type").isin(EXPECTED_NODE_TYPES))
        .dropDuplicates(["name", "node_type"])
    )
    requests = (
        concept_requests.select(
            F.trim(F.col("node_name")).alias("name"),
            F.lower(F.trim(F.col("node_type"))).alias("node_type"),
            F.col("concept_request_id").cast("string").alias("concept_request_id"),
            F.col("prompt_version").cast("string").alias("request_prompt_version"),
            F.col("context_version").cast("string").alias("request_context_version"),
            F.col("model_name").cast("string").alias("request_model_name"),
        )
        .dropDuplicates(["name", "node_type"])
    )
    parsed = parsed_df.select(
        "concept_request_id",
        F.col("source_status").alias("raw_source_status"),
        F.col("parse_status").alias("raw_parse_status"),
        F.col("prompt_version").alias("raw_prompt_version"),
        F.col("context_version").alias("raw_context_version"),
        F.col("model_name").alias("raw_model_name"),
        "raw_run_id",
    )
    mapping_counts = concept_mappings.groupBy("concept_request_id").agg(
        F.count("*").cast("int").alias("concept_count")
    )

    joined = (
        missing.join(requests, on=["name", "node_type"], how="left")
        .join(parsed, on="concept_request_id", how="left")
        .join(mapping_counts, on="concept_request_id", how="left")
        .withColumn("concept_count", F.coalesce(F.col("concept_count"), F.lit(0)).cast("int"))
        .withColumn(
            "request_status",
            F.when(F.col("concept_request_id").isNull(), F.lit("MISSING"))
            .when(F.col("raw_source_status").isNull(), F.lit("NOT_REQUESTED"))
            .otherwise(F.col("raw_source_status")),
        )
        .withColumn(
            "parse_status",
            F.when(F.col("concept_request_id").isNull(), F.lit("MISSING"))
            .when(F.col("raw_source_status").isNull(), F.lit("NOT_PARSED"))
            .otherwise(F.col("raw_parse_status")),
        )
        .withColumn(
            "mapping_status",
            F.when(F.col("concept_request_id").isNull(), F.lit("MISSING"))
            .when(F.col("raw_source_status").isNull(), F.lit("NOT_REQUESTED"))
            .when(F.col("raw_source_status") != "SUCCESS", F.col("raw_source_status"))
            .when(F.col("raw_parse_status") == "INVALID", F.lit("INVALID"))
            .when(F.col("raw_parse_status") == "EMPTY", F.lit("EMPTY"))
            .when(F.col("concept_count") > 0, F.lit("MAPPED"))
            .otherwise(F.lit("EMPTY")),
        )
        .withColumn("prompt_version", F.coalesce(F.col("raw_prompt_version"), F.col("request_prompt_version")))
        .withColumn("context_version", F.coalesce(F.col("raw_context_version"), F.col("request_context_version")))
        .withColumn("model_name", F.coalesce(F.col("raw_model_name"), F.col("request_model_name")))
        .withColumn("mapping_run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
    )

    return joined.select(
        "name",
        "node_type",
        "concept_request_id",
        "request_status",
        "parse_status",
        "mapping_status",
        "concept_count",
        "prompt_version",
        "context_version",
        "model_name",
        "raw_run_id",
        "mapping_run_id",
        "schema_version",
    )


def build_rejects(parsed_df: DataFrame) -> DataFrame:
    return parsed_df.filter(F.col("parse_status") != "VALID").select(
        "concept_request_id",
        "node_name",
        "node_type",
        "source_status",
        "parse_status",
        "error_message",
        "response_excerpt",
        "prompt_version",
        "context_version",
        "model_name",
        "raw_run_id",
        "run_id",
        "created_ts",
    )


def collect_metrics(
    raw_df: DataFrame,
    parsed_df: DataFrame,
    concept_mappings: DataFrame,
    concept_coverage: DataFrame,
) -> dict[str, Any]:
    raw_record_count = raw_df.count()
    latest_raw_count = parsed_df.count()
    mapping_count = concept_mappings.count()
    distinct_mapping_request_count = concept_mappings.select("concept_request_id").distinct().count()
    coverage_count = concept_coverage.count()

    return {
        "raw_record_count": raw_record_count,
        "latest_raw_request_count": latest_raw_count,
        "mapping_record_count": mapping_count,
        "distinct_mapping_request_count": distinct_mapping_request_count,
        "coverage_record_count": coverage_count,
        "source_status_counts": {
            row["source_status"]: row["count"]
            for row in parsed_df.groupBy("source_status").count().collect()
        },
        "parse_status_counts": {
            row["parse_status"]: row["count"]
            for row in parsed_df.groupBy("parse_status").count().collect()
        },
        "mapping_status_counts": {
            row["mapping_status"]: row["count"]
            for row in concept_coverage.groupBy("mapping_status").count().collect()
        },
        "coverage_by_type": {
            row["node_type"]: {
                "total": row["total"],
                "mapped": row["mapped"],
                "empty": row["empty"],
                "not_requested": row["not_requested"],
                "invalid": row["invalid"],
                "failed": row["failed"],
            }
            for row in concept_coverage.groupBy("node_type")
            .agg(
                F.count("*").alias("total"),
                F.sum(F.when(F.col("mapping_status") == "MAPPED", 1).otherwise(0)).alias("mapped"),
                F.sum(F.when(F.col("mapping_status") == "EMPTY", 1).otherwise(0)).alias("empty"),
                F.sum(F.when(F.col("mapping_status") == "NOT_REQUESTED", 1).otherwise(0)).alias("not_requested"),
                F.sum(F.when(F.col("mapping_status") == "INVALID", 1).otherwise(0)).alias("invalid"),
                F.sum(F.when(F.col("mapping_status").isin(["FAILED", "TIMEOUT", "RATE_LIMITED"]), 1).otherwise(0)).alias("failed"),
            )
            .collect()
        },
    }


def write_output(df: DataFrame, *, bucket: str, base_path: str, run_id: str) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(base_path, run_id))
    df.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def write_rejects(
    rejects_df: DataFrame,
    *,
    bucket: str,
    logs_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(
        bucket,
        build_run_path(f"{logs_base_path}/concept_validation_rejects", run_id),
    )
    rejects_df.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def write_report(
    spark: SparkSession,
    metrics: dict[str, Any],
    *,
    bucket: str,
    reports_base_path: str,
    run_id: str,
    raw_run_ids: list[str],
    concept_request_run_id: str,
    missing_concepts_run_id: str,
) -> str:
    output_uri = build_s3a_uri(
        bucket,
        build_run_path(f"{reports_base_path}/concept_validation", run_id),
    )
    payload = {
        "run_id": run_id,
        "raw_run_ids": ",".join(raw_run_ids),
        "concept_request_run_id": concept_request_run_id,
        "missing_concepts_run_id": missing_concepts_run_id,
        "created_ts": datetime.now(timezone.utc).isoformat(),
        "metrics_json": json_dumps(metrics),
    }
    spark.createDataFrame([payload]).coalesce(1).write.mode("overwrite").json(output_uri)
    return output_uri


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    pipeline_cfg, storage_cfg = load_configs(repo_root)
    run_id = derive_run_id(args.run_id)
    schema_version = str(pipeline_cfg["runtime"]["schema_version"])

    spark = SparkSession.builder.appName("phase2-11-validate-concepts").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    parsed_df: Optional[DataFrame] = None
    concept_mappings: Optional[DataFrame] = None
    concept_coverage: Optional[DataFrame] = None
    try:
        bucket = storage_cfg["bucket"]
        table_paths = storage_cfg["tables"]
        raw_run_ids = parse_raw_run_ids(args.raw_run_ids)
        if not raw_run_ids:
            raw_run_ids = [
                resolve_latest_run_id(
                    spark,
                    bucket,
                    table_paths["bronze.concept_raw"],
                )
            ]

        concept_request_run_id = args.concept_request_run_id or resolve_latest_run_id(
            spark,
            bucket,
            table_paths["silver.concept_requests"],
        )
        missing_concepts_run_id = (
            args.missing_concepts_run_id
            or args.graph_base_run_id
            or resolve_latest_run_id(spark, bucket, table_paths["silver.missing_concepts"])
        )

        raw_df = read_raw_runs(
            spark,
            bucket=bucket,
            concept_raw_base_path=table_paths["bronze.concept_raw"],
            raw_run_ids=raw_run_ids,
        ).cache()
        concept_requests = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.concept_requests"],
            run_id=concept_request_run_id,
        ).cache()
        missing_concepts = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.missing_concepts"],
            run_id=missing_concepts_run_id,
        ).cache()

        parsed_df = parse_responses(spark, raw_df, run_id=run_id).cache()
        concept_mappings = build_concept_mappings(
            parsed_df,
            run_id=run_id,
            schema_version=schema_version,
        ).cache()
        concept_coverage = build_concept_coverage(
            missing_concepts,
            concept_requests,
            parsed_df,
            concept_mappings,
            run_id=run_id,
            schema_version=schema_version,
        ).cache()
        rejects_df = build_rejects(parsed_df)

        mappings_uri = write_output(
            concept_mappings,
            bucket=bucket,
            base_path=table_paths["silver.concept_mappings"],
            run_id=run_id,
        )
        coverage_uri = write_output(
            concept_coverage,
            bucket=bucket,
            base_path=table_paths["silver.concept_coverage"],
            run_id=run_id,
        )
        reject_uri = write_rejects(
            rejects_df,
            bucket=bucket,
            logs_base_path=table_paths["meta.logs"],
            run_id=run_id,
        )
        metrics = collect_metrics(raw_df, parsed_df, concept_mappings, concept_coverage)
        report_uri = write_report(
            spark,
            metrics,
            bucket=bucket,
            reports_base_path=table_paths["meta.quality_reports"],
            run_id=run_id,
            raw_run_ids=raw_run_ids,
            concept_request_run_id=concept_request_run_id,
            missing_concepts_run_id=missing_concepts_run_id,
        )

        print(f"VALIDATE_CONCEPT_RUN_ID={run_id}")
        print(f"RAW_RUN_IDS={','.join(raw_run_ids)}")
        print(f"CONCEPT_REQUEST_RUN_ID={concept_request_run_id}")
        print(f"MISSING_CONCEPTS_RUN_ID={missing_concepts_run_id}")
        print(f"RAW_RECORD_COUNT={metrics['raw_record_count']}")
        print(f"LATEST_RAW_REQUEST_COUNT={metrics['latest_raw_request_count']}")
        print(f"MAPPING_RECORD_COUNT={metrics['mapping_record_count']}")
        print(f"DISTINCT_MAPPING_REQUEST_COUNT={metrics['distinct_mapping_request_count']}")
        print(f"COVERAGE_RECORD_COUNT={metrics['coverage_record_count']}")
        for status_name, count in sorted(metrics["source_status_counts"].items()):
            print(f"SOURCE_STATUS_{status_name.upper()}={count}")
        for parse_status, count in sorted(metrics["parse_status_counts"].items()):
            print(f"PARSE_STATUS_{parse_status.upper()}={count}")
        for mapping_status, count in sorted(metrics["mapping_status_counts"].items()):
            print(f"MAPPING_STATUS_{mapping_status.upper()}={count}")
        for node_type, type_metric in sorted(metrics["coverage_by_type"].items()):
            prefix = f"COVERAGE_TYPE_{node_type.upper()}"
            print(f"{prefix}_TOTAL={type_metric['total']}")
            print(f"{prefix}_MAPPED={type_metric['mapped']}")
            print(f"{prefix}_EMPTY={type_metric['empty']}")
            print(f"{prefix}_NOT_REQUESTED={type_metric['not_requested']}")
            print(f"{prefix}_INVALID={type_metric['invalid']}")
            print(f"{prefix}_FAILED={type_metric['failed']}")
        print(f"CONCEPT_MAPPINGS_OUTPUT_PATH={mappings_uri}")
        print(f"CONCEPT_COVERAGE_OUTPUT_PATH={coverage_uri}")
        print(f"CONCEPT_VALIDATION_REJECT_PATH={reject_uri}")
        print(f"CONCEPT_VALIDATION_REPORT_PATH={report_uri}")
    finally:
        for df in [parsed_df, concept_mappings, concept_coverage]:
            if df is not None:
                df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
