#!/usr/bin/env python3
"""Validate raw extraction responses and build chunk-level structured records."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from pyspark.sql import DataFrame, SparkSession, functions as F, types as T

from pipeline.common.config_loader import load_yaml
from pipeline.common.extraction_validation import parse_json_payload, validate_stage_payload
from pipeline.common.io import json_dumps
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


EXPECTED_STAGES = [
    "entity_relation",
    "event_entity",
    "event_relation",
]

TRIPLE_ITEM_SCHEMA = T.StructType(
    [
        T.StructField("Head", T.StringType(), False),
        T.StructField("Relation", T.StringType(), False),
        T.StructField("Tail", T.StringType(), False),
    ]
)

EVENT_ENTITY_ITEM_SCHEMA = T.StructType(
    [
        T.StructField("Event", T.StringType(), False),
        T.StructField("Entity", T.ArrayType(T.StringType()), False),
    ]
)

PARSED_SCHEMA = T.StructType(
    [
        T.StructField("request_id", T.StringType(), False),
        T.StructField("doc_id", T.StringType(), False),
        T.StructField("chunk_id", T.IntegerType(), False),
        T.StructField("stage", T.StringType(), False),
        T.StructField("prompt_version", T.StringType(), False),
        T.StructField("model_name", T.StringType(), False),
        T.StructField("source_status", T.StringType(), False),
        T.StructField("parse_status", T.StringType(), False),
        T.StructField("error_message", T.StringType(), True),
        T.StructField("parsed_json", T.StringType(), True),
        T.StructField("response_excerpt", T.StringType(), True),
        T.StructField("entity_relation", T.ArrayType(TRIPLE_ITEM_SCHEMA), True),
        T.StructField("event_entity", T.ArrayType(EVENT_ENTITY_ITEM_SCHEMA), True),
        T.StructField("event_relation", T.ArrayType(TRIPLE_ITEM_SCHEMA), True),
        T.StructField("run_id", T.StringType(), False),
        T.StructField("created_ts", T.TimestampType(), False),
    ]
)

REJECT_SCHEMA = T.StructType(
    [
        T.StructField("request_id", T.StringType(), False),
        T.StructField("doc_id", T.StringType(), False),
        T.StructField("chunk_id", T.IntegerType(), False),
        T.StructField("stage", T.StringType(), False),
        T.StructField("source_status", T.StringType(), False),
        T.StructField("parse_status", T.StringType(), False),
        T.StructField("error_message", T.StringType(), True),
        T.StructField("response_excerpt", T.StringType(), True),
        T.StructField("prompt_version", T.StringType(), False),
        T.StructField("model_name", T.StringType(), False),
        T.StructField("run_id", T.StringType(), False),
        T.StructField("created_ts", T.TimestampType(), False),
    ]
)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(repo_root))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument("--chunk-run-id", default=None)
    return parser.parse_args()


def derive_run_id(explicit_run_id: Optional[str]) -> str:
    if explicit_run_id:
        return explicit_run_id
    return datetime.now(timezone.utc).strftime("validextract-%Y%m%d%H%M%S")


def load_configs(repo_root: Path) -> tuple[dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    return pipeline_cfg, storage_cfg


def read_extraction_raw(
    spark: SparkSession,
    *,
    bucket: str,
    extraction_raw_base_path: str,
    source_run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(bucket, build_run_path(extraction_raw_base_path, source_run_id))
    return spark.read.parquet(input_uri)


def read_chunks(
    spark: SparkSession,
    *,
    bucket: str,
    chunk_base_path: str,
    chunk_run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(bucket, build_run_path(chunk_base_path, chunk_run_id))
    return spark.read.parquet(input_uri)


def _response_excerpt(response_text: str | None, max_length: int = 500) -> str | None:
    if response_text is None:
        return None
    compact = " ".join(response_text.split())
    return compact[:max_length]


def parse_raw_rows(rows: Iterable, *, run_id: str) -> Iterator[tuple]:
    for row in rows:
        source_status = str(row["status"] or "")
        stage = str(row["stage"] or "")
        now = datetime.utcnow()
        base_values = {
            "request_id": row["request_id"],
            "doc_id": row["doc_id"],
            "chunk_id": int(row["chunk_id"]),
            "stage": stage,
            "prompt_version": row["prompt_version"],
            "model_name": row["model_name"],
            "source_status": source_status,
            "response_excerpt": _response_excerpt(row["response_text"]),
            "run_id": run_id,
            "created_ts": now,
        }

        if source_status != "SUCCESS":
            yield (
                base_values["request_id"],
                base_values["doc_id"],
                base_values["chunk_id"],
                base_values["stage"],
                base_values["prompt_version"],
                base_values["model_name"],
                base_values["source_status"],
                "SKIPPED_NON_SUCCESS",
                row["error_message"] or f"source_status={source_status}",
                None,
                base_values["response_excerpt"],
                None,
                None,
                None,
                base_values["run_id"],
                base_values["created_ts"],
            )
            continue

        try:
            parsed_payload = parse_json_payload(row["response_text"])
            normalized_payload = validate_stage_payload(stage, parsed_payload)
            parsed_json = json_dumps(normalized_payload)
            entity_relation = normalized_payload if stage == "entity_relation" else None
            event_entity = normalized_payload if stage == "event_entity" else None
            event_relation = normalized_payload if stage == "event_relation" else None
            yield (
                base_values["request_id"],
                base_values["doc_id"],
                base_values["chunk_id"],
                base_values["stage"],
                base_values["prompt_version"],
                base_values["model_name"],
                base_values["source_status"],
                "VALID",
                None,
                parsed_json,
                base_values["response_excerpt"],
                entity_relation,
                event_entity,
                event_relation,
                base_values["run_id"],
                base_values["created_ts"],
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            yield (
                base_values["request_id"],
                base_values["doc_id"],
                base_values["chunk_id"],
                base_values["stage"],
                base_values["prompt_version"],
                base_values["model_name"],
                base_values["source_status"],
                "INVALID",
                str(exc),
                None,
                base_values["response_excerpt"],
                None,
                None,
                None,
                base_values["run_id"],
                base_values["created_ts"],
            )


def parse_responses(spark: SparkSession, raw_df: DataFrame, *, run_id: str) -> DataFrame:
    selected = raw_df.select(
        F.col("request_id").cast("string").alias("request_id"),
        F.col("doc_id").cast("string").alias("doc_id"),
        F.col("chunk_id").cast("int").alias("chunk_id"),
        F.col("stage").cast("string").alias("stage"),
        F.col("prompt_version").cast("string").alias("prompt_version"),
        F.col("model_name").cast("string").alias("model_name"),
        F.col("response_text").cast("string").alias("response_text"),
        F.col("status").cast("string").alias("status"),
        F.col("error_message").cast("string").alias("error_message"),
    )
    parsed_rdd = selected.rdd.mapPartitions(lambda rows: parse_raw_rows(rows, run_id=run_id))
    return spark.createDataFrame(parsed_rdd, schema=PARSED_SCHEMA)


def build_structured_extraction(
    parsed_df: DataFrame,
    chunk_df: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    valid_df = parsed_df.filter(F.col("parse_status") == "VALID")

    pivoted = valid_df.groupBy("doc_id", "chunk_id").agg(
        F.first(
            F.when(F.col("stage") == "entity_relation", F.col("entity_relation")),
            ignorenulls=True,
        ).alias("entity_relation"),
        F.first(
            F.when(F.col("stage") == "event_entity", F.col("event_entity")),
            ignorenulls=True,
        ).alias("event_entity"),
        F.first(
            F.when(F.col("stage") == "event_relation", F.col("event_relation")),
            ignorenulls=True,
        ).alias("event_relation"),
        F.countDistinct("stage").alias("valid_stage_count"),
    )

    empty_triples = F.array().cast(T.ArrayType(TRIPLE_ITEM_SCHEMA))
    empty_event_entities = F.array().cast(T.ArrayType(EVENT_ENTITY_ITEM_SCHEMA))

    chunks = chunk_df.select(
        F.col("doc_id").cast("string").alias("doc_id"),
        F.col("chunk_id").cast("int").alias("chunk_id"),
        F.col("chunk_text").cast("string").alias("original_text"),
        F.col("lang").cast("string").alias("lang"),
        F.col("metadata").cast("string").alias("metadata"),
    )

    return (
        chunks.join(pivoted, on=["doc_id", "chunk_id"], how="inner")
        .select(
            "doc_id",
            "chunk_id",
            "original_text",
            "lang",
            "metadata",
            F.coalesce(F.col("entity_relation"), empty_triples).alias("entity_relation"),
            F.coalesce(F.col("event_entity"), empty_event_entities).alias("event_entity"),
            F.coalesce(F.col("event_relation"), empty_triples).alias("event_relation"),
            F.lit(run_id).alias("run_id"),
            F.lit(schema_version).alias("schema_version"),
        )
    )


def build_rejects(parsed_df: DataFrame) -> DataFrame:
    return parsed_df.filter(F.col("parse_status") != "VALID").select(
        "request_id",
        "doc_id",
        "chunk_id",
        "stage",
        "source_status",
        "parse_status",
        "error_message",
        "response_excerpt",
        "prompt_version",
        "model_name",
        "run_id",
        "created_ts",
    )


def collect_metrics(
    parsed_df: DataFrame,
    structured_df: DataFrame,
    raw_df: DataFrame,
) -> dict[str, Any]:
    raw_count = raw_df.count()
    distinct_request_count = raw_df.select("request_id").distinct().count()
    if raw_count != distinct_request_count:
        raise RuntimeError(
            "Extraction raw request_id uniqueness mismatch: "
            f"raw_count={raw_count}, distinct_request_count={distinct_request_count}"
        )

    status_counts = {
        row["source_status"]: row["count"]
        for row in parsed_df.groupBy("source_status").count().collect()
    }
    parse_counts = {
        row["parse_status"]: row["count"]
        for row in parsed_df.groupBy("parse_status").count().collect()
    }
    stage_metrics = {
        row["stage"]: {
            "total": row["total"],
            "valid": row["valid"],
            "invalid": row["invalid"],
            "skipped_non_success": row["skipped_non_success"],
        }
        for row in parsed_df.groupBy("stage")
        .agg(
            F.count("*").alias("total"),
            F.sum(F.when(F.col("parse_status") == "VALID", 1).otherwise(0)).alias("valid"),
            F.sum(F.when(F.col("parse_status") == "INVALID", 1).otherwise(0)).alias("invalid"),
            F.sum(
                F.when(F.col("parse_status") == "SKIPPED_NON_SUCCESS", 1).otherwise(0)
            ).alias("skipped_non_success"),
        )
        .collect()
    }
    valid_stage_counts = (
        parsed_df.filter(F.col("parse_status") == "VALID")
        .groupBy("doc_id", "chunk_id")
        .agg(F.countDistinct("stage").alias("valid_stage_count"))
    )
    complete_chunk_count = valid_stage_counts.filter(F.col("valid_stage_count") == 3).count()
    incomplete_chunk_count = valid_stage_counts.filter(F.col("valid_stage_count") < 3).count()

    return {
        "raw_record_count": raw_count,
        "distinct_request_count": distinct_request_count,
        "source_status_counts": status_counts,
        "parse_status_counts": parse_counts,
        "stage_metrics": stage_metrics,
        "structured_record_count": structured_df.count(),
        "complete_chunk_count": complete_chunk_count,
        "incomplete_chunk_count": incomplete_chunk_count,
    }


def write_output(
    structured_df: DataFrame,
    *,
    bucket: str,
    structured_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(structured_base_path, run_id))
    structured_df.write.mode("overwrite").format("parquet").save(output_uri)
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
        build_run_path(f"{logs_base_path}/extraction_validation_rejects", run_id),
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
    source_run_id: str,
    chunk_run_id: str,
) -> str:
    output_uri = build_s3a_uri(
        bucket,
        build_run_path(f"{reports_base_path}/extraction_validation", run_id),
    )
    payload = {
        "run_id": run_id,
        "source_run_id": source_run_id,
        "chunk_run_id": chunk_run_id,
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

    spark = SparkSession.builder.appName("phase2-06-validate-extraction").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    parsed_df: Optional[DataFrame] = None
    structured_df: Optional[DataFrame] = None
    try:
        bucket = storage_cfg["bucket"]
        extraction_raw_base_path = storage_cfg["tables"]["bronze.extraction_raw"]
        chunk_base_path = storage_cfg["tables"]["silver.document_chunks"]
        structured_base_path = storage_cfg["tables"]["silver.extraction_structured"]
        logs_base_path = storage_cfg["tables"]["meta.logs"]
        reports_base_path = storage_cfg["tables"]["meta.quality_reports"]

        source_run_id = args.source_run_id or resolve_latest_run_id(
            spark,
            bucket,
            extraction_raw_base_path,
        )
        chunk_run_id = args.chunk_run_id or resolve_latest_run_id(
            spark,
            bucket,
            chunk_base_path,
        )

        raw_df = read_extraction_raw(
            spark,
            bucket=bucket,
            extraction_raw_base_path=extraction_raw_base_path,
            source_run_id=source_run_id,
        )
        chunk_df = read_chunks(
            spark,
            bucket=bucket,
            chunk_base_path=chunk_base_path,
            chunk_run_id=chunk_run_id,
        )

        parsed_df = parse_responses(spark, raw_df, run_id=run_id).cache()
        structured_df = build_structured_extraction(
            parsed_df,
            chunk_df,
            run_id=run_id,
            schema_version=schema_version,
        ).cache()
        rejects_df = build_rejects(parsed_df)

        output_uri = write_output(
            structured_df,
            bucket=bucket,
            structured_base_path=structured_base_path,
            run_id=run_id,
        )
        reject_uri = write_rejects(
            rejects_df,
            bucket=bucket,
            logs_base_path=logs_base_path,
            run_id=run_id,
        )
        metrics = collect_metrics(parsed_df, structured_df, raw_df)
        report_uri = write_report(
            spark,
            metrics,
            bucket=bucket,
            reports_base_path=reports_base_path,
            run_id=run_id,
            source_run_id=source_run_id,
            chunk_run_id=chunk_run_id,
        )

        print(f"VALIDATE_EXTRACTION_RUN_ID={run_id}")
        print(f"SOURCE_RUN_ID={source_run_id}")
        print(f"CHUNK_RUN_ID={chunk_run_id}")
        print(f"RAW_RECORD_COUNT={metrics['raw_record_count']}")
        print(f"DISTINCT_REQUEST_COUNT={metrics['distinct_request_count']}")
        for status_name, count in sorted(metrics["source_status_counts"].items()):
            print(f"SOURCE_STATUS_{status_name.upper()}={count}")
        for parse_status, count in sorted(metrics["parse_status_counts"].items()):
            print(f"PARSE_STATUS_{parse_status.upper()}={count}")
        for stage_name, stage_metric in sorted(metrics["stage_metrics"].items()):
            print(f"STAGE_{stage_name.upper()}_TOTAL={stage_metric['total']}")
            print(f"STAGE_{stage_name.upper()}_VALID={stage_metric['valid']}")
            print(f"STAGE_{stage_name.upper()}_INVALID={stage_metric['invalid']}")
            print(
                f"STAGE_{stage_name.upper()}_SKIPPED_NON_SUCCESS="
                f"{stage_metric['skipped_non_success']}"
            )
        print(f"STRUCTURED_RECORD_COUNT={metrics['structured_record_count']}")
        print(f"COMPLETE_CHUNK_COUNT={metrics['complete_chunk_count']}")
        print(f"INCOMPLETE_CHUNK_COUNT={metrics['incomplete_chunk_count']}")
        print(f"EXTRACTION_STRUCTURED_OUTPUT_PATH={output_uri}")
        print(f"EXTRACTION_VALIDATION_REJECT_PATH={reject_uri}")
        print(f"EXTRACTION_VALIDATION_REPORT_PATH={report_uri}")
    finally:
        if parsed_df is not None:
            parsed_df.unpersist()
        if structured_df is not None:
            structured_df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
