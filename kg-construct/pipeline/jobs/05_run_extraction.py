#!/usr/bin/env python3
"""Run extraction requests against the configured LLM API."""

from __future__ import annotations

import argparse
import asyncio
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional

from pyspark.sql import DataFrame, SparkSession, functions as F, types as T

from pipeline.common.config_loader import load_yaml
from pipeline.common.io import collect_runtime_env, json_dumps
from pipeline.common.llm_client import ChatRequest, OpenAICompatibleClient
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


OUTPUT_SCHEMA = T.StructType(
    [
        T.StructField("request_id", T.StringType(), False),
        T.StructField("doc_id", T.StringType(), False),
        T.StructField("chunk_id", T.IntegerType(), False),
        T.StructField("stage", T.StringType(), False),
        T.StructField("prompt_version", T.StringType(), False),
        T.StructField("model_name", T.StringType(), False),
        T.StructField("response_text", T.StringType(), True),
        T.StructField("usage_json", T.StringType(), True),
        T.StructField("status", T.StringType(), False),
        T.StructField("error_message", T.StringType(), True),
        T.StructField("created_ts", T.TimestampType(), False),
        T.StructField("run_id", T.StringType(), False),
    ]
)


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
    return datetime.now(timezone.utc).strftime("extractraw-%Y%m%d%H%M%S")


def load_configs(repo_root: Path) -> tuple[dict, dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    spark_cfg = load_yaml(repo_root / "config/spark.yaml")
    return pipeline_cfg, storage_cfg, spark_cfg


def build_spark_session() -> SparkSession:
    task_cpus = max(int(os.environ.get("SPARK_EXECUTOR_CORES", "1")), 1)
    builder = (
        SparkSession.builder.appName("phase2-05-run-extraction")
        .config("spark.task.cpus", str(task_cpus))
    )
    return builder.getOrCreate()


def read_input(
    spark: SparkSession,
    *,
    bucket: str,
    extraction_request_base_path: str,
    source_run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(
        bucket,
        build_run_path(extraction_request_base_path, source_run_id),
    )
    return spark.read.parquet(input_uri)


def prepare_requests(
    df: DataFrame,
    *,
    spark_cfg: dict,
    limit: int | None,
) -> tuple[DataFrame, dict]:
    prepared = df.select(
        F.col("request_id").cast("string").alias("request_id"),
        F.col("doc_id").cast("string").alias("doc_id"),
        F.col("chunk_id").cast("int").alias("chunk_id"),
        F.col("stage").cast("string").alias("stage"),
        F.col("lang").cast("string").alias("lang"),
        F.col("system_prompt").cast("string").alias("system_prompt"),
        F.col("user_prompt").cast("string").alias("user_prompt"),
        F.col("prompt_version").cast("string").alias("prompt_version"),
        F.col("model_name").cast("string").alias("model_name"),
    )

    input_count = prepared.count()
    deduped = prepared.dropDuplicates(["request_id"])
    deduped_count = deduped.count()
    dedup_removed = input_count - deduped_count

    if limit is not None:
        deduped = deduped.orderBy("doc_id", "chunk_id", "stage").limit(limit)

    final_count = deduped.count()
    if final_count == 0:
        raise RuntimeError("No extraction requests available to run")

    worker_count = max(int(spark_cfg.get("worker_count", 1)), 1)
    target_per_partition = 50
    partition_count = max(
        1,
        min(worker_count, math.ceil(final_count / target_per_partition)),
    )

    repartitioned = (
        deduped.repartition(partition_count, "stage", "lang")
        .sortWithinPartitions("stage", "lang", "request_id")
    )

    per_stage_counts = {
        row["stage"]: row["count"]
        for row in deduped.groupBy("stage").count().collect()
    }
    metrics = {
        "input_request_count": input_count,
        "deduped_request_count": deduped_count,
        "dedup_removed_count": dedup_removed,
        "final_request_count": final_count,
        "partition_count": partition_count,
        "per_stage_counts": per_stage_counts,
    }
    return repartitioned, metrics


def _run_partition_async(
    partition_id: int,
    rows: list,
    repo_root: str,
    run_id: str,
) -> list[tuple]:
    if not rows:
        return []

    runtime_env = collect_runtime_env(repo_root)
    client = OpenAICompatibleClient.from_repo_root(repo_root, environ=runtime_env)
    requests = [
        ChatRequest(
            request_id=row["request_id"],
            system_prompt=row["system_prompt"],
            user_prompt=row["user_prompt"],
            model_name=row["model_name"],
            metadata={
                "doc_id": row["doc_id"],
                "chunk_id": row["chunk_id"],
                "stage": row["stage"],
                "prompt_version": row["prompt_version"],
                "lang": row["lang"],
            },
        )
        for row in rows
    ]
    results = asyncio.run(client.generate_text_batch(requests))

    output_rows: list[tuple] = []
    for source_row, result in zip(rows, results):
        output_rows.append(
            (
                source_row["request_id"],
                source_row["doc_id"],
                int(source_row["chunk_id"]),
                source_row["stage"],
                source_row["prompt_version"],
                source_row["model_name"],
                result.response_text,
                json_dumps(result.usage) if result.usage is not None else None,
                result.status,
                result.error_message,
                datetime.utcnow(),
                run_id,
            )
        )

    partition_metrics = client.metrics_snapshot()
    partition_metrics["partition_id"] = partition_id
    partition_metrics["request_count"] = len(rows)
    partition_metrics["run_id"] = run_id
    print("PARTITION_EXTRACTION_METRICS=" + json_dumps(partition_metrics))
    return output_rows


def execute_requests(
    spark: SparkSession,
    request_df: DataFrame,
    *,
    repo_root: Path,
    run_id: str,
) -> DataFrame:
    def process_partition(
        partition_id: int,
        rows: Iterable,
    ) -> Iterator[tuple]:
        row_list = list(rows)
        return iter(
            _run_partition_async(
                partition_id=partition_id,
                rows=row_list,
                repo_root=str(repo_root),
                run_id=run_id,
            )
        )

    result_rdd = request_df.rdd.mapPartitionsWithIndex(process_partition)
    return spark.createDataFrame(result_rdd, schema=OUTPUT_SCHEMA)


def write_output(
    result_df: DataFrame,
    *,
    bucket: str,
    extraction_raw_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(extraction_raw_base_path, run_id))
    result_df.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def validate_counts(input_count: int, result_df: DataFrame) -> dict:
    output_count = result_df.count()
    distinct_request_count = result_df.select("request_id").distinct().count()
    if output_count != input_count:
        raise RuntimeError(
            f"Extraction raw row count mismatch: input={input_count}, output={output_count}"
        )
    if distinct_request_count != input_count:
        raise RuntimeError(
            "Extraction raw request_id uniqueness mismatch: "
            f"input={input_count}, distinct_output={distinct_request_count}"
        )

    status_metrics = {
        row["status"]: row["count"] for row in result_df.groupBy("status").count().collect()
    }

    usage_metrics_row = (
        result_df.select(
            F.coalesce(
                F.get_json_object("usage_json", "$.prompt_tokens").cast("long"),
                F.lit(0),
            ).alias("prompt_tokens"),
            F.coalesce(
                F.get_json_object("usage_json", "$.completion_tokens").cast("long"),
                F.lit(0),
            ).alias("completion_tokens"),
            F.coalesce(
                F.get_json_object("usage_json", "$.total_tokens").cast("long"),
                F.lit(0),
            ).alias("total_tokens"),
        )
        .agg(
            F.sum("prompt_tokens").alias("sum_prompt_tokens"),
            F.sum("completion_tokens").alias("sum_completion_tokens"),
            F.sum("total_tokens").alias("sum_total_tokens"),
        )
        .collect()[0]
        .asDict()
    )

    status_metrics.update(
        {
            "output_count": output_count,
            "distinct_request_count": distinct_request_count,
            "sum_prompt_tokens": usage_metrics_row["sum_prompt_tokens"] or 0,
            "sum_completion_tokens": usage_metrics_row["sum_completion_tokens"] or 0,
            "sum_total_tokens": usage_metrics_row["sum_total_tokens"] or 0,
        }
    )
    return status_metrics


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    _, storage_cfg, spark_cfg = load_configs(repo_root)
    run_id = derive_run_id(args.run_id)

    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    result_df: Optional[DataFrame] = None
    try:
        bucket = storage_cfg["bucket"]
        extraction_request_base_path = storage_cfg["tables"]["silver.extraction_requests"]
        extraction_raw_base_path = storage_cfg["tables"]["bronze.extraction_raw"]
        source_run_id = args.source_run_id or resolve_latest_run_id(
            spark, bucket, extraction_request_base_path
        )

        input_df = read_input(
            spark,
            bucket=bucket,
            extraction_request_base_path=extraction_request_base_path,
            source_run_id=source_run_id,
        )
        prepared_df, prep_metrics = prepare_requests(
            input_df,
            spark_cfg=spark_cfg,
            limit=args.limit,
        )
        result_df = execute_requests(
            spark,
            prepared_df,
            repo_root=repo_root,
            run_id=run_id,
        ).cache()
        output_uri = write_output(
            result_df,
            bucket=bucket,
            extraction_raw_base_path=extraction_raw_base_path,
            run_id=run_id,
        )
        validation_metrics = validate_counts(prep_metrics["final_request_count"], result_df)

        print(f"EXTRACTION_RAW_RUN_ID={run_id}")
        print(f"SOURCE_RUN_ID={source_run_id}")
        print(f"INPUT_REQUEST_COUNT={prep_metrics['input_request_count']}")
        print(f"DEDUPED_REQUEST_COUNT={prep_metrics['deduped_request_count']}")
        print(f"DEDUP_REMOVED_COUNT={prep_metrics['dedup_removed_count']}")
        print(f"FINAL_REQUEST_COUNT={prep_metrics['final_request_count']}")
        print(f"PARTITION_COUNT={prep_metrics['partition_count']}")
        for stage_name, count in sorted(prep_metrics["per_stage_counts"].items()):
            print(f"INPUT_STAGE_{stage_name.upper()}={count}")
        print(f"OUTPUT_RECORD_COUNT={validation_metrics['output_count']}")
        print(f"DISTINCT_REQUEST_COUNT={validation_metrics['distinct_request_count']}")
        print(f"SUCCESS_COUNT={validation_metrics.get('SUCCESS', 0)}")
        print(f"FAILED_COUNT={validation_metrics.get('FAILED', 0)}")
        print(f"TIMEOUT_COUNT={validation_metrics.get('TIMEOUT', 0)}")
        print(f"RATE_LIMITED_COUNT={validation_metrics.get('RATE_LIMITED', 0)}")
        print(f"SUM_PROMPT_TOKENS={validation_metrics['sum_prompt_tokens']}")
        print(f"SUM_COMPLETION_TOKENS={validation_metrics['sum_completion_tokens']}")
        print(f"SUM_TOTAL_TOKENS={validation_metrics['sum_total_tokens']}")
        print(f"EXTRACTION_RAW_OUTPUT_PATH={output_uri}")
    finally:
        if result_df is not None:
            result_df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
