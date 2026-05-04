#!/usr/bin/env python3
"""Run concept generation requests against the configured LLM API."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from pyspark.sql import DataFrame, SparkSession, Window, functions as F, types as T

from pipeline.common.config_loader import load_yaml
from pipeline.common.io import collect_runtime_env, json_dumps
from pipeline.common.llm_client import ChatRequest, OpenAICompatibleClient
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


EXPECTED_NODE_TYPES = ["entity", "event", "relation"]

OUTPUT_SCHEMA = T.StructType(
    [
        T.StructField("concept_request_id", T.StringType(), False),
        T.StructField("node_name", T.StringType(), False),
        T.StructField("node_type", T.StringType(), False),
        T.StructField("prompt_version", T.StringType(), False),
        T.StructField("context_version", T.StringType(), False),
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
    parser.add_argument("--graph-base-run-id", default=None)
    parser.add_argument("--existing-raw-run-id", default=None)
    parser.add_argument("--existing-raw-run-ids", default=None)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--selection-strategy", choices=["priority", "sequential"], default="priority")
    parser.add_argument("--remaining-only", action="store_true")
    parser.add_argument("--entity-quota", type=int, default=None)
    parser.add_argument("--event-quota", type=int, default=None)
    parser.add_argument("--relation-quota", type=int, default=None)
    return parser.parse_args()


def derive_run_id(explicit_run_id: Optional[str]) -> str:
    if explicit_run_id:
        return explicit_run_id
    return datetime.now(timezone.utc).strftime("conceptraw-%Y%m%d%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Top-level JSON document must be an object: {path}")
    return data


def load_configs(repo_root: Path) -> tuple[dict, dict, dict, dict]:
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    spark_cfg = load_yaml(repo_root / "config/spark.yaml")
    llm_cfg = load_yaml(repo_root / "config/llm.yaml")
    prompt_registry = load_json(repo_root / "config/prompts/concept_vi.json")
    return storage_cfg, spark_cfg, llm_cfg, prompt_registry


def build_spark_session() -> SparkSession:
    task_cpus = max(int(os.environ.get("SPARK_EXECUTOR_CORES", "1")), 1)
    return (
        SparkSession.builder.appName("phase2-10-run-concept-generation")
        .config("spark.task.cpus", str(task_cpus))
        .getOrCreate()
    )


def read_table(
    spark: SparkSession,
    *,
    bucket: str,
    base_path: str,
    run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(bucket, build_run_path(base_path, run_id))
    return spark.read.parquet(input_uri)


def safe_resolve_latest_run_id(spark: SparkSession, bucket: str, base_path: str) -> str | None:
    try:
        return resolve_latest_run_id(spark, bucket, base_path)
    except FileNotFoundError:
        return None


def parse_run_ids(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def read_raw_runs(
    spark: SparkSession,
    *,
    bucket: str,
    base_path: str,
    run_ids: list[str],
) -> DataFrame | None:
    if not run_ids:
        return None
    frames = [read_table(spark, bucket=bucket, base_path=base_path, run_id=run_id) for run_id in run_ids]
    return reduce(lambda left, right: left.unionByName(right), frames)


def compute_type_quotas(
    *,
    limit: int,
    entity_quota: int | None,
    event_quota: int | None,
    relation_quota: int | None,
) -> dict[str, int]:
    relation = relation_quota if relation_quota is not None else int(limit * 0.2)
    entity = entity_quota if entity_quota is not None else int(limit * 0.5)
    event = event_quota if event_quota is not None else limit - entity - relation

    quotas = {
        "entity": max(entity, 0),
        "event": max(event, 0),
        "relation": max(relation, 0),
    }
    overflow = sum(quotas.values()) - limit
    if overflow > 0:
        for node_type in ["relation", "event", "entity"]:
            reduction = min(quotas[node_type], overflow)
            quotas[node_type] -= reduction
            overflow -= reduction
            if overflow == 0:
                break
    underflow = limit - sum(quotas.values())
    if underflow > 0:
        quotas["entity"] += underflow
    return quotas


def build_priority_scores(concept_requests: DataFrame, triple_edges: DataFrame) -> DataFrame:
    node_degree = (
        triple_edges.select(F.col("src").alias("node_name"))
        .unionByName(triple_edges.select(F.col("dst").alias("node_name")))
        .groupBy("node_name")
        .count()
        .withColumnRenamed("count", "node_degree")
    )
    relation_frequency = (
        triple_edges.groupBy(F.col("relation").alias("node_name"))
        .count()
        .withColumnRenamed("count", "relation_frequency")
    )
    return (
        concept_requests.join(node_degree, on="node_name", how="left")
        .join(relation_frequency, on="node_name", how="left")
        .withColumn(
            "priority_score",
            F.when(F.col("node_type") == "relation", F.coalesce(F.col("relation_frequency"), F.lit(0)))
            .otherwise(F.coalesce(F.col("node_degree"), F.lit(0)))
            .cast("long"),
        )
        .drop("node_degree", "relation_frequency")
    )


def exclude_already_run(concept_requests: DataFrame, existing_raw: DataFrame | None) -> DataFrame:
    if existing_raw is None:
        return concept_requests
    already_seen = existing_raw.select("concept_request_id").dropDuplicates(["concept_request_id"])
    return concept_requests.join(already_seen, on="concept_request_id", how="left_anti")


def prepare_requests(
    spark: SparkSession,
    concept_requests: DataFrame,
    *,
    triple_edges: DataFrame | None,
    existing_raw: DataFrame | None,
    prompt_registry: dict,
    limit: int,
    selection_strategy: str,
    quotas: dict[str, int],
    spark_cfg: dict,
) -> tuple[DataFrame, dict[str, Any]]:
    prompt_rows = [
        {
            "node_type": node_type,
            "system_prompt": str(prompt_registry[node_type]["system_prompt"]),
        }
        for node_type in EXPECTED_NODE_TYPES
    ]
    system_prompt_df = spark.createDataFrame(prompt_rows)

    base = (
        concept_requests.select(
            F.col("concept_request_id").cast("string").alias("concept_request_id"),
            F.col("node_name").cast("string").alias("node_name"),
            F.lower(F.col("node_type")).cast("string").alias("node_type"),
            F.col("context_text").cast("string").alias("context_text"),
            F.col("prompt_text").cast("string").alias("prompt_text"),
            F.col("prompt_version").cast("string").alias("prompt_version"),
            F.col("context_version").cast("string").alias("context_version"),
            F.col("model_name").cast("string").alias("model_name"),
        )
        .filter(F.col("node_type").isin(EXPECTED_NODE_TYPES))
        .dropDuplicates(["concept_request_id"])
    )
    input_count = base.count()
    remaining = exclude_already_run(base, existing_raw)
    remaining_count = remaining.count()

    with_system = remaining.join(F.broadcast(system_prompt_df), on="node_type", how="inner")
    if selection_strategy == "priority":
        if triple_edges is None:
            raise RuntimeError("Priority selection requires silver.triple_edges")
        scored = build_priority_scores(with_system, triple_edges)
        ranked = scored.withColumn(
            "type_rank",
            F.row_number().over(
                Window.partitionBy("node_type").orderBy(
                    F.col("priority_score").desc(),
                    F.col("node_name").asc(),
                    F.col("concept_request_id").asc(),
                )
            ),
        )
        quota_df = spark.createDataFrame(
            [{"node_type": node_type, "quota": quota} for node_type, quota in quotas.items()]
        )
        selected = ranked.join(F.broadcast(quota_df), on="node_type", how="inner").filter(
            F.col("type_rank") <= F.col("quota")
        )
    else:
        selected = (
            with_system.withColumn("priority_score", F.lit(0).cast("long"))
            .orderBy("node_type", "node_name", "concept_request_id")
            .limit(limit)
        )

    selected = selected.orderBy(
        F.col("node_type").asc(),
        F.col("priority_score").desc(),
        F.col("node_name").asc(),
    ).limit(limit)
    final_count = selected.count()
    if final_count == 0:
        raise RuntimeError("No concept requests selected to run")

    worker_count = max(int(spark_cfg.get("worker_count", 1)), 1)
    target_per_partition = 50
    partition_count = max(1, min(worker_count, math.ceil(final_count / target_per_partition)))
    prepared = (
        selected.repartition(partition_count, "node_type")
        .sortWithinPartitions("node_type", F.col("priority_score").desc(), "concept_request_id")
        .select(
            "concept_request_id",
            "node_name",
            "node_type",
            "system_prompt",
            "prompt_text",
            "prompt_version",
            "context_version",
            "model_name",
        )
    )
    type_counts = {
        row["node_type"]: row["count"] for row in selected.groupBy("node_type").count().collect()
    }
    metrics = {
        "input_request_count": input_count,
        "remaining_request_count": remaining_count,
        "final_request_count": final_count,
        "partition_count": partition_count,
        "selection_strategy": selection_strategy,
        "quotas": dict(quotas),
        "type_counts": type_counts,
    }
    return prepared, metrics


def _run_partition_async(partition_id: int, rows: list, repo_root: str, run_id: str) -> list[tuple]:
    if not rows:
        return []

    runtime_env = collect_runtime_env(repo_root)
    client = OpenAICompatibleClient.from_repo_root(repo_root, environ=runtime_env)
    requests = [
        ChatRequest(
            request_id=row["concept_request_id"],
            system_prompt=row["system_prompt"],
            user_prompt=row["prompt_text"],
            model_name=row["model_name"],
            metadata={
                "node_name": row["node_name"],
                "node_type": row["node_type"],
                "prompt_version": row["prompt_version"],
                "context_version": row["context_version"],
            },
        )
        for row in rows
    ]
    results = asyncio.run(client.generate_text_batch(requests))

    output_rows: list[tuple] = []
    for source_row, result in zip(rows, results):
        output_rows.append(
            (
                source_row["concept_request_id"],
                source_row["node_name"],
                source_row["node_type"],
                source_row["prompt_version"],
                source_row["context_version"],
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
    print("PARTITION_CONCEPT_GENERATION_METRICS=" + json_dumps(partition_metrics))
    return output_rows


def execute_requests(
    spark: SparkSession,
    request_df: DataFrame,
    *,
    repo_root: Path,
    run_id: str,
) -> DataFrame:
    def process_partition(partition_id: int, rows: Iterable) -> Iterator[tuple]:
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
    concept_raw_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(concept_raw_base_path, run_id))
    result_df.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def validate_counts(input_count: int, result_df: DataFrame) -> dict[str, Any]:
    output_count = result_df.count()
    distinct_request_count = result_df.select("concept_request_id").distinct().count()
    if output_count != input_count:
        raise RuntimeError(
            f"Concept raw row count mismatch: input={input_count}, output={output_count}"
        )
    if distinct_request_count != input_count:
        raise RuntimeError(
            "Concept raw request_id uniqueness mismatch: "
            f"input={input_count}, distinct_output={distinct_request_count}"
        )

    status_metrics = {
        row["status"]: row["count"] for row in result_df.groupBy("status").count().collect()
    }
    type_metrics = {
        row["node_type"]: row["count"] for row in result_df.groupBy("node_type").count().collect()
    }
    usage_metrics_row = (
        result_df.select(
            F.coalesce(F.get_json_object("usage_json", "$.prompt_tokens").cast("long"), F.lit(0)).alias("prompt_tokens"),
            F.coalesce(F.get_json_object("usage_json", "$.completion_tokens").cast("long"), F.lit(0)).alias("completion_tokens"),
            F.coalesce(F.get_json_object("usage_json", "$.total_tokens").cast("long"), F.lit(0)).alias("total_tokens"),
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
            "type_counts": type_metrics,
            "sum_prompt_tokens": usage_metrics_row["sum_prompt_tokens"] or 0,
            "sum_completion_tokens": usage_metrics_row["sum_completion_tokens"] or 0,
            "sum_total_tokens": usage_metrics_row["sum_total_tokens"] or 0,
        }
    )
    return status_metrics


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    storage_cfg, spark_cfg, _, prompt_registry = load_configs(repo_root)
    run_id = derive_run_id(args.run_id)
    limit = max(int(args.limit), 1)
    quotas = compute_type_quotas(
        limit=limit,
        entity_quota=args.entity_quota,
        event_quota=args.event_quota,
        relation_quota=args.relation_quota,
    )

    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    result_df: Optional[DataFrame] = None
    cached: list[DataFrame] = []
    wall_started = time.monotonic()
    try:
        bucket = storage_cfg["bucket"]
        table_paths = storage_cfg["tables"]
        source_run_id = args.source_run_id or resolve_latest_run_id(
            spark,
            bucket,
            table_paths["silver.concept_requests"],
        )
        graph_base_run_id = args.graph_base_run_id or safe_resolve_latest_run_id(
            spark,
            bucket,
            table_paths["silver.triple_edges"],
        )

        concept_requests = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.concept_requests"],
            run_id=source_run_id,
        ).cache()
        cached.append(concept_requests)

        triple_edges = None
        if args.selection_strategy == "priority":
            if graph_base_run_id is None:
                raise RuntimeError("No graph base run available for priority selection")
            triple_edges = read_table(
                spark,
                bucket=bucket,
                base_path=table_paths["silver.triple_edges"],
                run_id=graph_base_run_id,
            ).cache()
            cached.append(triple_edges)

        existing_raw = None
        existing_raw_run_ids = parse_run_ids(args.existing_raw_run_ids)
        if args.existing_raw_run_id:
            existing_raw_run_ids.append(args.existing_raw_run_id)
        if args.remaining_only:
            if not existing_raw_run_ids:
                latest_raw_run_id = safe_resolve_latest_run_id(
                    spark,
                    bucket=bucket,
                    base_path=table_paths["bronze.concept_raw"],
                )
                if latest_raw_run_id:
                    existing_raw_run_ids.append(latest_raw_run_id)
            existing_raw_run_ids = sorted(set(existing_raw_run_ids))
            existing_raw = read_raw_runs(
                spark,
                bucket=bucket,
                base_path=table_paths["bronze.concept_raw"],
                run_ids=existing_raw_run_ids,
            )
            if existing_raw is not None:
                existing_raw = existing_raw.cache()
                cached.append(existing_raw)

        prepared_df, prep_metrics = prepare_requests(
            spark,
            concept_requests,
            triple_edges=triple_edges,
            existing_raw=existing_raw,
            prompt_registry=prompt_registry,
            limit=limit,
            selection_strategy=args.selection_strategy,
            quotas=quotas,
            spark_cfg=spark_cfg,
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
            concept_raw_base_path=table_paths["bronze.concept_raw"],
            run_id=run_id,
        )
        validation_metrics = validate_counts(prep_metrics["final_request_count"], result_df)
        wall_seconds = time.monotonic() - wall_started

        print(f"CONCEPT_RAW_RUN_ID={run_id}")
        print(f"SOURCE_RUN_ID={source_run_id}")
        print(f"GRAPH_BASE_RUN_ID={graph_base_run_id or ''}")
        print(f"EXISTING_RAW_RUN_IDS={','.join(existing_raw_run_ids)}")
        print(f"LIMIT={limit}")
        print(f"SELECTION_STRATEGY={prep_metrics['selection_strategy']}")
        print(f"REMAINING_ONLY={args.remaining_only}")
        print(f"QUOTA_ENTITY={prep_metrics['quotas']['entity']}")
        print(f"QUOTA_EVENT={prep_metrics['quotas']['event']}")
        print(f"QUOTA_RELATION={prep_metrics['quotas']['relation']}")
        print(f"INPUT_REQUEST_COUNT={prep_metrics['input_request_count']}")
        print(f"REMAINING_REQUEST_COUNT={prep_metrics['remaining_request_count']}")
        print(f"FINAL_REQUEST_COUNT={prep_metrics['final_request_count']}")
        print(f"PARTITION_COUNT={prep_metrics['partition_count']}")
        for node_type, count in sorted(prep_metrics["type_counts"].items()):
            print(f"SELECTED_TYPE_{node_type.upper()}={count}")
        print(f"OUTPUT_RECORD_COUNT={validation_metrics['output_count']}")
        print(f"DISTINCT_REQUEST_COUNT={validation_metrics['distinct_request_count']}")
        print(f"SUCCESS_COUNT={validation_metrics.get('SUCCESS', 0)}")
        print(f"FAILED_COUNT={validation_metrics.get('FAILED', 0)}")
        print(f"TIMEOUT_COUNT={validation_metrics.get('TIMEOUT', 0)}")
        print(f"RATE_LIMITED_COUNT={validation_metrics.get('RATE_LIMITED', 0)}")
        for node_type, count in sorted(validation_metrics["type_counts"].items()):
            print(f"OUTPUT_TYPE_{node_type.upper()}={count}")
        print(f"SUM_PROMPT_TOKENS={validation_metrics['sum_prompt_tokens']}")
        print(f"SUM_COMPLETION_TOKENS={validation_metrics['sum_completion_tokens']}")
        print(f"SUM_TOTAL_TOKENS={validation_metrics['sum_total_tokens']}")
        print(f"WALL_SECONDS={wall_seconds}")
        print(f"CONCEPT_RAW_OUTPUT_PATH={output_uri}")
    finally:
        if result_df is not None:
            result_df.unpersist()
        for df in cached:
            df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
