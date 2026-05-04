#!/usr/bin/env python3
"""Compute pilot embeddings for graph nodes, edges, and source text."""

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
from pipeline.common.llm_client import EmbeddingRequest, OpenAICompatibleClient
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


ITEM_TYPES = ["text_node", "triple_node", "triple_edge"]

OUTPUT_SCHEMA = T.StructType(
    [
        T.StructField("item_id", T.StringType(), False),
        T.StructField("item_type", T.StringType(), False),
        T.StructField("text_for_embedding", T.StringType(), False),
        T.StructField("embedding", T.ArrayType(T.FloatType()), True),
        T.StructField("model_name", T.StringType(), False),
        T.StructField("status", T.StringType(), False),
        T.StructField("usage_json", T.StringType(), True),
        T.StructField("error_message", T.StringType(), True),
        T.StructField("created_ts", T.TimestampType(), False),
        T.StructField("run_id", T.StringType(), False),
        T.StructField("schema_version", T.StringType(), False),
    ]
)

EMBEDDING_TABLE_COLUMNS = [
    "item_id",
    "item_type",
    "text_for_embedding",
    "embedding",
    "model_name",
    "status",
    "usage_json",
    "error_message",
    "run_id",
    "schema_version",
]


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(repo_root))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--graph-base-run-id", default=None)
    parser.add_argument("--node-context-run-id", default=None)
    parser.add_argument("--merge-run-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--remaining-only", action="store_true")
    parser.add_argument("--existing-embedding-run-ids", default=None)
    parser.add_argument("--node-quota", type=int, default=None)
    parser.add_argument("--edge-quota", type=int, default=None)
    parser.add_argument("--text-quota", type=int, default=None)
    return parser.parse_args()


def derive_run_id(explicit_run_id: Optional[str]) -> str:
    if explicit_run_id:
        return explicit_run_id
    return datetime.now(timezone.utc).strftime("embed-%Y%m%d%H%M%S")


def load_configs(repo_root: Path) -> tuple[dict, dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    llm_cfg = load_yaml(repo_root / "config/llm.yaml")
    return pipeline_cfg, storage_cfg, llm_cfg


def build_spark_session() -> SparkSession:
    task_cpus = max(int(os.environ.get("SPARK_EXECUTOR_CORES", "1")), 1)
    return (
        SparkSession.builder.appName("phase2-14-compute-embeddings")
        .config("spark.task.cpus", str(task_cpus))
        .getOrCreate()
    )


def read_table(spark: SparkSession, *, bucket: str, base_path: str, run_id: str) -> DataFrame:
    return spark.read.parquet(build_s3a_uri(bucket, build_run_path(base_path, run_id)))


def parse_run_ids(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def safe_resolve_latest_run_id(spark: SparkSession, bucket: str, base_path: str) -> str | None:
    try:
        return resolve_latest_run_id(spark, bucket, base_path)
    except FileNotFoundError:
        return None


def _non_empty(column_name: str) -> F.Column:
    return F.col(column_name).isNotNull() & (F.length(F.trim(F.col(column_name))) > 0)


def truncate_col(column: F.Column, max_chars: int) -> F.Column:
    return F.when(F.length(column) > max_chars, F.substring(column, 1, max_chars)).otherwise(column)


def build_node_inputs(
    triple_nodes: DataFrame,
    node_context: DataFrame,
    *,
    source_run_id: str,
    model_name: str,
    embedding_cfg: dict,
) -> DataFrame:
    max_context_chars = int(embedding_cfg.get("node_context_max_chars", 1200))
    context = node_context.select(
        F.trim(F.col("node_name")).alias("node_name"),
        F.lower(F.trim(F.col("node_type"))).alias("node_type"),
        F.col("context_text").cast("string").alias("context_text"),
    ).dropDuplicates(["node_name", "node_type"])
    nodes = (
        triple_nodes.select(
            F.trim(F.col("node_name")).alias("node_name"),
            F.lower(F.trim(F.col("node_type"))).alias("node_type"),
        )
        .filter(_non_empty("node_name") & _non_empty("node_type"))
        .dropDuplicates(["node_name", "node_type"])
        .join(context, on=["node_name", "node_type"], how="left")
        .withColumn("context_text", F.coalesce(F.col("context_text"), F.lit("none")))
        .withColumn("context_text", truncate_col(F.col("context_text"), max_context_chars))
        .withColumn(
            "text_for_embedding",
            F.concat(
                F.lit("Node: "),
                F.col("node_name"),
                F.lit("\nNode type: "),
                F.col("node_type"),
                F.lit("\nContext: "),
                F.col("context_text"),
            ),
        )
        .withColumn(
            "item_id",
            F.sha2(F.concat_ws("||", F.lit("triple_node"), F.col("node_name"), F.col("node_type")), 256),
        )
        .withColumn("item_type", F.lit("triple_node"))
        .withColumn("source_run_id", F.lit(source_run_id))
        .withColumn("model_name", F.lit(model_name))
        .withColumn("type_priority", F.lit(1))
        .withColumn("sort_key", F.col("node_name"))
    )
    return nodes.select("item_id", "item_type", "text_for_embedding", "source_run_id", "model_name", "type_priority", "sort_key")


def build_edge_inputs(
    triple_edges_enriched: DataFrame,
    *,
    source_run_id: str,
    model_name: str,
    embedding_cfg: dict,
) -> DataFrame:
    max_chars = int(embedding_cfg.get("edge_text_max_chars", 2000))
    edges = (
        triple_edges_enriched.select(
            F.trim(F.col("src")).alias("src"),
            F.trim(F.col("relation")).alias("relation"),
            F.trim(F.col("dst")).alias("dst"),
            F.col("source_doc_id").cast("string").alias("source_doc_id"),
            F.col("source_chunk_id").cast("string").alias("source_chunk_id"),
        )
        .filter(_non_empty("src") & _non_empty("relation") & _non_empty("dst"))
        .withColumn(
            "text_for_embedding",
            F.concat(F.lit("Edge: "), F.col("src"), F.lit(" --"), F.col("relation"), F.lit("--> "), F.col("dst")),
        )
        .withColumn("text_for_embedding", truncate_col(F.col("text_for_embedding"), max_chars))
        .withColumn(
            "item_id",
            F.sha2(
                F.concat_ws(
                    "||",
                    F.lit("triple_edge"),
                    F.col("src"),
                    F.col("relation"),
                    F.col("dst"),
                    F.coalesce(F.col("source_doc_id"), F.lit("")),
                    F.coalesce(F.col("source_chunk_id"), F.lit("")),
                ),
                256,
            ),
        )
        .withColumn("item_type", F.lit("triple_edge"))
        .withColumn("source_run_id", F.lit(source_run_id))
        .withColumn("model_name", F.lit(model_name))
        .withColumn("type_priority", F.lit(2))
        .withColumn("sort_key", F.concat_ws("||", F.col("src"), F.col("relation"), F.col("dst")))
    )
    return edges.select("item_id", "item_type", "text_for_embedding", "source_run_id", "model_name", "type_priority", "sort_key")


def build_text_inputs(
    text_nodes: DataFrame,
    *,
    source_run_id: str,
    model_name: str,
    embedding_cfg: dict,
) -> DataFrame:
    max_chars = int(embedding_cfg.get("text_node_max_chars", 8000))
    texts = (
        text_nodes.select(
            F.col("text_id").cast("string").alias("item_id"),
            F.col("original_text").cast("string").alias("original_text"),
        )
        .filter(_non_empty("item_id") & _non_empty("original_text"))
        .withColumn("text_for_embedding", truncate_col(F.trim(F.col("original_text")), max_chars))
        .withColumn("item_type", F.lit("text_node"))
        .withColumn("source_run_id", F.lit(source_run_id))
        .withColumn("model_name", F.lit(model_name))
        .withColumn("type_priority", F.lit(0))
        .withColumn("sort_key", F.col("item_id"))
    )
    return texts.select("item_id", "item_type", "text_for_embedding", "source_run_id", "model_name", "type_priority", "sort_key")


def compute_quotas(limit: int, *, text_quota: int | None, node_quota: int | None, edge_quota: int | None) -> dict[str, int]:
    text = text_quota if text_quota is not None else min(250, limit)
    node = node_quota if node_quota is not None else min(500, max(limit - text, 0))
    edge = edge_quota if edge_quota is not None else max(limit - text - node, 0)
    quotas = {
        "text_node": max(text, 0),
        "triple_node": max(node, 0),
        "triple_edge": max(edge, 0),
    }
    overflow = sum(quotas.values()) - limit
    if overflow > 0:
        for item_type in ["text_node", "triple_node", "triple_edge"]:
            reduction = min(quotas[item_type], overflow)
            quotas[item_type] -= reduction
            overflow -= reduction
            if overflow == 0:
                break
    return quotas


def read_existing_coverage(
    spark: SparkSession,
    *,
    bucket: str,
    coverage_base_path: str,
    run_ids: list[str],
) -> DataFrame | None:
    if not run_ids:
        return None
    frames = [read_table(spark, bucket=bucket, base_path=coverage_base_path, run_id=run_id) for run_id in run_ids]
    return reduce(lambda left, right: left.unionByName(right), frames)


def select_embedding_inputs(
    spark: SparkSession,
    all_inputs: DataFrame,
    *,
    existing_coverage: DataFrame | None,
    remaining_only: bool,
    limit: int,
    quotas: dict[str, int],
    spark_cfg: dict,
) -> tuple[DataFrame, dict[str, Any]]:
    base = all_inputs.dropDuplicates(["item_id"]).filter(_non_empty("text_for_embedding")).cache()
    input_count = base.count()

    existing_success = None
    existing_success_count = 0
    if remaining_only and existing_coverage is not None:
        existing_success = (
            existing_coverage.filter(F.col("embedding_status") == "EMBEDDED")
            .select("item_id")
            .dropDuplicates(["item_id"])
        )
        existing_success_count = existing_success.count()
        remaining = base.join(existing_success, on="item_id", how="left_anti")
    else:
        remaining = base
    remaining = remaining.cache()
    remaining_count = remaining.count()

    ranked = remaining.withColumn(
        "type_rank",
        F.row_number().over(Window.partitionBy("item_type").orderBy("sort_key", "item_id")),
    )
    quota_df = spark.createDataFrame(
        [{"item_type": item_type, "quota": quota} for item_type, quota in quotas.items()]
    )
    quota_selected = (
        ranked.join(F.broadcast(quota_df), on="item_type", how="inner")
        .filter(F.col("type_rank") <= F.col("quota"))
        .drop("quota")
        .withColumn("selection_phase", F.lit(0))
    )
    quota_ids = quota_selected.select("item_id")
    filler = ranked.join(quota_ids, on="item_id", how="left_anti").withColumn("selection_phase", F.lit(1))
    selected = (
        quota_selected.unionByName(filler)
        .orderBy("selection_phase", "type_priority", "type_rank", "sort_key", "item_id")
        .limit(limit)
        .cache()
    )
    selected_count = selected.count()
    type_counts = {
        row["item_type"]: row["count"] for row in selected.groupBy("item_type").count().collect()
    }

    worker_count = max(int(spark_cfg.get("worker_count", 1)), 1)
    target_per_partition = 50
    partition_count = max(1, min(worker_count, math.ceil(max(selected_count, 1) / target_per_partition)))
    prepared = (
        selected.repartition(partition_count, "item_type")
        .sortWithinPartitions("type_priority", "type_rank", "item_id")
        .select("item_id", "item_type", "text_for_embedding", "model_name")
    )
    base.unpersist()
    remaining.unpersist()

    return prepared, {
        "input_count": input_count,
        "existing_success_count": existing_success_count,
        "remaining_count": remaining_count,
        "selected_count": selected_count,
        "partition_count": partition_count,
        "type_counts": type_counts,
        "quotas": quotas,
    }


def _run_partition_async(partition_id: int, rows: list, repo_root: str, run_id: str, schema_version: str) -> list[tuple]:
    if not rows:
        return []
    runtime_env = collect_runtime_env(repo_root)
    client = OpenAICompatibleClient.from_repo_root(repo_root, environ=runtime_env)
    requests = [
        EmbeddingRequest(
            request_id=row["item_id"],
            text=row["text_for_embedding"],
            model_name=row["model_name"],
            metadata={"item_type": row["item_type"]},
        )
        for row in rows
    ]
    results = asyncio.run(client.embed_text_batch(requests))
    output_rows: list[tuple] = []
    for source_row, result in zip(rows, results):
        output_rows.append(
            (
                source_row["item_id"],
                source_row["item_type"],
                source_row["text_for_embedding"],
                result.embedding,
                result.model_name,
                result.status,
                json_dumps(result.usage) if result.usage is not None else None,
                result.error_message,
                datetime.utcnow(),
                run_id,
                schema_version,
            )
        )
    partition_metrics = client.metrics_snapshot()
    partition_metrics["partition_id"] = partition_id
    partition_metrics["request_count"] = len(rows)
    partition_metrics["run_id"] = run_id
    print("PARTITION_EMBEDDING_METRICS=" + json_dumps(partition_metrics))
    return output_rows


def execute_embeddings(
    spark: SparkSession,
    request_df: DataFrame,
    *,
    repo_root: Path,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    def process_partition(partition_id: int, rows: Iterable) -> Iterator[tuple]:
        return iter(
            _run_partition_async(
                partition_id,
                list(rows),
                str(repo_root),
                run_id,
                schema_version,
            )
        )

    return spark.createDataFrame(request_df.rdd.mapPartitionsWithIndex(process_partition), schema=OUTPUT_SCHEMA)


def build_coverage(
    all_inputs: DataFrame,
    result_df: DataFrame,
    existing_coverage: DataFrame | None,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    existing_success = None
    if existing_coverage is not None:
        existing_success = (
            existing_coverage.filter(F.col("embedding_status") == "EMBEDDED")
            .select(
                "item_id",
                F.col("item_type").alias("existing_item_type"),
                F.col("model_name").alias("existing_model_name"),
                F.col("embedding_run_id").alias("existing_embedding_run_id"),
            )
            .dropDuplicates(["item_id"])
        )
    else:
        existing_success = all_inputs.sparkSession.createDataFrame(
            [],
            T.StructType(
                [
                    T.StructField("item_id", T.StringType(), True),
                    T.StructField("existing_item_type", T.StringType(), True),
                    T.StructField("existing_model_name", T.StringType(), True),
                    T.StructField("existing_embedding_run_id", T.StringType(), True),
                ]
            ),
        )

    current = result_df.select(
        "item_id",
        F.col("status").alias("current_status"),
        F.col("model_name").alias("current_model_name"),
        F.col("run_id").alias("current_embedding_run_id"),
    )
    base = all_inputs.select("item_id", "item_type", "source_run_id").dropDuplicates(["item_id"])
    return (
        base.join(current, on="item_id", how="left")
        .join(existing_success, on="item_id", how="left")
        .withColumn(
            "embedding_status",
            F.when(F.col("current_status") == "SUCCESS", F.lit("EMBEDDED"))
            .when(F.col("current_status").isNotNull(), F.col("current_status"))
            .when(F.col("existing_embedding_run_id").isNotNull(), F.lit("EMBEDDED"))
            .otherwise(F.lit("NOT_REQUESTED")),
        )
        .withColumn("model_name", F.coalesce(F.col("current_model_name"), F.col("existing_model_name")))
        .withColumn(
            "embedding_run_id",
            F.coalesce(F.col("current_embedding_run_id"), F.col("existing_embedding_run_id")),
        )
        .withColumn("schema_version", F.lit(schema_version))
        .select(
            "item_id",
            "item_type",
            "embedding_status",
            "model_name",
            "embedding_run_id",
            "source_run_id",
            "schema_version",
        )
    )


def read_existing_embedding_tables(
    spark: SparkSession,
    *,
    bucket: str,
    table_paths: dict,
    run_ids: list[str],
) -> dict[str, DataFrame]:
    if not run_ids:
        return {}
    mapping = {
        "triple_node": "gold.embeddings.triple_nodes",
        "triple_edge": "gold.embeddings.triple_edges",
        "text_node": "gold.embeddings.text_nodes",
    }
    existing: dict[str, DataFrame] = {}
    for item_type, table_name in mapping.items():
        frames = []
        for run_id in run_ids:
            try:
                frames.append(
                    read_table(
                        spark,
                        bucket=bucket,
                        base_path=table_paths[table_name],
                        run_id=run_id,
                    ).select(*EMBEDDING_TABLE_COLUMNS)
                )
            except Exception:
                continue
        if frames:
            existing[item_type] = reduce(lambda left, right: left.unionByName(right), frames)
    return existing


def write_embedding_tables(
    result_df: DataFrame,
    *,
    bucket: str,
    table_paths: dict,
    run_id: str,
    existing_embeddings: dict[str, DataFrame] | None = None,
) -> dict[str, str]:
    success = result_df.filter(F.col("status") == "SUCCESS").select(*EMBEDDING_TABLE_COLUMNS)
    outputs = {}
    mapping = {
        "triple_node": "gold.embeddings.triple_nodes",
        "triple_edge": "gold.embeddings.triple_edges",
        "text_node": "gold.embeddings.text_nodes",
    }
    for item_type, table_name in mapping.items():
        output_uri = build_s3a_uri(bucket, build_run_path(table_paths[table_name], run_id))
        current_type = success.filter(F.col("item_type") == item_type).withColumn("source_priority", F.lit(0))
        existing_type = None
        if existing_embeddings and item_type in existing_embeddings:
            existing_type = existing_embeddings[item_type].select(*EMBEDDING_TABLE_COLUMNS).withColumn(
                "source_priority",
                F.lit(1),
            )
        table_df = current_type if existing_type is None else current_type.unionByName(existing_type)
        table_df = (
            table_df.withColumn(
                "row_rank",
                F.row_number().over(Window.partitionBy("item_id").orderBy("source_priority", F.col("run_id").desc())),
            )
            .filter(F.col("row_rank") == 1)
            .drop("source_priority", "row_rank")
        )
        table_df.write.mode("overwrite").format("parquet").save(output_uri)
        outputs[table_name] = output_uri
    return outputs


def write_coverage(coverage_df: DataFrame, *, bucket: str, table_paths: dict, run_id: str) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(table_paths["gold.embeddings.coverage"], run_id))
    coverage_df.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def collect_metrics(all_inputs: DataFrame, result_df: DataFrame, coverage_df: DataFrame, embedding_dimension: int) -> dict[str, Any]:
    success = result_df.filter(F.col("status") == "SUCCESS")
    bad_dimension_count = success.filter(F.size("embedding") != embedding_dimension).count()
    return {
        "input_item_count": all_inputs.select("item_id").dropDuplicates().count(),
        "selected_item_count": result_df.count(),
        "success_count": success.count(),
        "failed_count": result_df.filter(F.col("status") == "FAILED").count(),
        "timeout_count": result_df.filter(F.col("status") == "TIMEOUT").count(),
        "rate_limited_count": result_df.filter(F.col("status") == "RATE_LIMITED").count(),
        "bad_dimension_count": bad_dimension_count,
        "result_type_counts": {
            row["item_type"]: row["count"] for row in result_df.groupBy("item_type").count().collect()
        },
        "coverage_status_counts": {
            row["embedding_status"]: row["count"] for row in coverage_df.groupBy("embedding_status").count().collect()
        },
        "coverage_type_counts": {
            row["item_type"]: {
                "total": row["total"],
                "embedded": row["embedded"],
                "not_requested": row["not_requested"],
                "failed": row["failed"],
            }
            for row in coverage_df.groupBy("item_type")
            .agg(
                F.count("*").alias("total"),
                F.sum(F.when(F.col("embedding_status") == "EMBEDDED", 1).otherwise(0)).alias("embedded"),
                F.sum(F.when(F.col("embedding_status") == "NOT_REQUESTED", 1).otherwise(0)).alias("not_requested"),
                F.sum(F.when(F.col("embedding_status").isin(["FAILED", "TIMEOUT", "RATE_LIMITED"]), 1).otherwise(0)).alias("failed"),
            )
            .collect()
        },
        "usage_totals": (
            result_df.select(
                F.coalesce(F.get_json_object("usage_json", "$.prompt_tokens").cast("long"), F.lit(0)).alias("prompt_tokens"),
                F.coalesce(F.get_json_object("usage_json", "$.total_tokens").cast("long"), F.lit(0)).alias("total_tokens"),
            )
            .agg(F.sum("prompt_tokens").alias("prompt_tokens"), F.sum("total_tokens").alias("total_tokens"))
            .collect()[0]
            .asDict()
        ),
    }


def write_report(
    spark: SparkSession,
    metrics: dict[str, Any],
    *,
    bucket: str,
    reports_base_path: str,
    run_id: str,
    graph_base_run_id: str,
    node_context_run_id: str,
    merge_run_id: str,
    limit: int,
    quotas: dict[str, int],
) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(f"{reports_base_path}/embeddings", run_id))
    payload = {
        "run_id": run_id,
        "graph_base_run_id": graph_base_run_id,
        "node_context_run_id": node_context_run_id,
        "merge_run_id": merge_run_id,
        "limit": limit,
        "quotas_json": json_dumps(quotas),
        "created_ts": datetime.now(timezone.utc).isoformat(),
        "metrics_json": json_dumps(metrics),
    }
    spark.createDataFrame([payload]).coalesce(1).write.mode("overwrite").json(output_uri)
    return output_uri


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    pipeline_cfg, storage_cfg, llm_cfg = load_configs(repo_root)
    run_id = derive_run_id(args.run_id)
    schema_version = str(pipeline_cfg["runtime"]["schema_version"])
    embedding_cfg = pipeline_cfg.get("embedding", {})
    limit = max(int(args.limit or embedding_cfg.get("default_limit", 1000)), 1)
    model_name = str(llm_cfg["embedding"]["model"])
    embedding_dimension = int(llm_cfg["embedding"]["dimension"])
    quotas = compute_quotas(
        limit,
        text_quota=args.text_quota,
        node_quota=args.node_quota,
        edge_quota=args.edge_quota,
    )

    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    cached: list[DataFrame] = []
    wall_started = time.monotonic()
    try:
        bucket = storage_cfg["bucket"]
        table_paths = storage_cfg["tables"]
        graph_base_run_id = args.graph_base_run_id or resolve_latest_run_id(
            spark, bucket, table_paths["silver.triple_nodes"]
        )
        node_context_run_id = args.node_context_run_id or resolve_latest_run_id(
            spark, bucket, table_paths["silver.node_context"]
        )
        merge_run_id = args.merge_run_id or resolve_latest_run_id(
            spark, bucket, table_paths["gold.triple_edges_enriched"]
        )

        triple_nodes = read_table(spark, bucket=bucket, base_path=table_paths["silver.triple_nodes"], run_id=graph_base_run_id)
        node_context = read_table(spark, bucket=bucket, base_path=table_paths["silver.node_context"], run_id=node_context_run_id)
        text_nodes = read_table(spark, bucket=bucket, base_path=table_paths["silver.text_nodes"], run_id=graph_base_run_id)
        triple_edges_enriched = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["gold.triple_edges_enriched"],
            run_id=merge_run_id,
        )

        node_inputs = build_node_inputs(
            triple_nodes,
            node_context,
            source_run_id=graph_base_run_id,
            model_name=model_name,
            embedding_cfg=embedding_cfg,
        )
        edge_inputs = build_edge_inputs(
            triple_edges_enriched,
            source_run_id=merge_run_id,
            model_name=model_name,
            embedding_cfg=embedding_cfg,
        )
        text_inputs = build_text_inputs(
            text_nodes,
            source_run_id=graph_base_run_id,
            model_name=model_name,
            embedding_cfg=embedding_cfg,
        )
        all_inputs = node_inputs.unionByName(edge_inputs).unionByName(text_inputs).cache()
        cached.append(all_inputs)

        existing_run_ids = parse_run_ids(args.existing_embedding_run_ids)
        if args.remaining_only and not existing_run_ids:
            latest_coverage = safe_resolve_latest_run_id(
                spark,
                bucket,
                table_paths["gold.embeddings.coverage"],
            )
            if latest_coverage:
                existing_run_ids.append(latest_coverage)
        existing_coverage = read_existing_coverage(
            spark,
            bucket=bucket,
            coverage_base_path=table_paths["gold.embeddings.coverage"],
            run_ids=existing_run_ids,
        )
        if existing_coverage is not None:
            existing_coverage = existing_coverage.cache()
            cached.append(existing_coverage)

        prepared, prep_metrics = select_embedding_inputs(
            spark,
            all_inputs,
            existing_coverage=existing_coverage,
            remaining_only=args.remaining_only,
            limit=limit,
            quotas=quotas,
            spark_cfg=load_yaml(repo_root / "config/spark.yaml"),
        )
        result_df = execute_embeddings(
            spark,
            prepared,
            repo_root=repo_root,
            run_id=run_id,
            schema_version=schema_version,
        ).cache()
        cached.append(result_df)

        coverage_df = build_coverage(
            all_inputs,
            result_df,
            existing_coverage,
            run_id=run_id,
            schema_version=schema_version,
        ).cache()
        cached.append(coverage_df)

        existing_embeddings = read_existing_embedding_tables(
            spark,
            bucket=bucket,
            table_paths=table_paths,
            run_ids=existing_run_ids,
        )
        output_paths = write_embedding_tables(
            result_df,
            bucket=bucket,
            table_paths=table_paths,
            run_id=run_id,
            existing_embeddings=existing_embeddings,
        )
        coverage_uri = write_coverage(coverage_df, bucket=bucket, table_paths=table_paths, run_id=run_id)
        metrics = collect_metrics(all_inputs, result_df, coverage_df, embedding_dimension)
        wall_seconds = time.monotonic() - wall_started
        metrics["wall_seconds"] = wall_seconds
        metrics["prep_metrics"] = prep_metrics

        if metrics["bad_dimension_count"] > 0:
            raise RuntimeError(f"Found embeddings with wrong dimension: {metrics['bad_dimension_count']}")

        report_uri = write_report(
            spark,
            metrics,
            bucket=bucket,
            reports_base_path=table_paths["meta.quality_reports"],
            run_id=run_id,
            graph_base_run_id=graph_base_run_id,
            node_context_run_id=node_context_run_id,
            merge_run_id=merge_run_id,
            limit=limit,
            quotas=quotas,
        )

        print(f"EMBEDDING_RUN_ID={run_id}")
        print(f"GRAPH_BASE_RUN_ID={graph_base_run_id}")
        print(f"NODE_CONTEXT_RUN_ID={node_context_run_id}")
        print(f"MERGE_RUN_ID={merge_run_id}")
        print(f"MODEL_NAME={model_name}")
        print(f"EMBEDDING_DIMENSION={embedding_dimension}")
        print(f"LIMIT={limit}")
        print(f"REMAINING_ONLY={args.remaining_only}")
        print(f"EXISTING_EMBEDDING_RUN_IDS={','.join(existing_run_ids)}")
        print(f"INPUT_ITEM_COUNT={metrics['input_item_count']}")
        print(f"EXISTING_SUCCESS_COUNT={prep_metrics['existing_success_count']}")
        print(f"REMAINING_ITEM_COUNT={prep_metrics['remaining_count']}")
        print(f"SELECTED_ITEM_COUNT={prep_metrics['selected_count']}")
        print(f"PARTITION_COUNT={prep_metrics['partition_count']}")
        for item_type, quota in sorted(quotas.items()):
            print(f"QUOTA_{item_type.upper()}={quota}")
        for item_type, count in sorted(prep_metrics["type_counts"].items()):
            print(f"SELECTED_TYPE_{item_type.upper()}={count}")
        print(f"SUCCESS_COUNT={metrics['success_count']}")
        print(f"FAILED_COUNT={metrics['failed_count']}")
        print(f"TIMEOUT_COUNT={metrics['timeout_count']}")
        print(f"RATE_LIMITED_COUNT={metrics['rate_limited_count']}")
        print(f"BAD_DIMENSION_COUNT={metrics['bad_dimension_count']}")
        for status, count in sorted(metrics["coverage_status_counts"].items()):
            print(f"COVERAGE_STATUS_{status.upper()}={count}")
        for item_type, counts in sorted(metrics["coverage_type_counts"].items()):
            prefix = f"COVERAGE_TYPE_{item_type.upper()}"
            print(f"{prefix}_TOTAL={counts['total']}")
            print(f"{prefix}_EMBEDDED={counts['embedded']}")
            print(f"{prefix}_NOT_REQUESTED={counts['not_requested']}")
            print(f"{prefix}_FAILED={counts['failed']}")
        print(f"SUM_PROMPT_TOKENS={metrics['usage_totals'].get('prompt_tokens') or 0}")
        print(f"SUM_TOTAL_TOKENS={metrics['usage_totals'].get('total_tokens') or 0}")
        print(f"WALL_SECONDS={wall_seconds}")
        for table_name, output_uri in sorted(output_paths.items()):
            print(f"{table_name.upper().replace('.', '_')}_OUTPUT_PATH={output_uri}")
        print(f"EMBEDDING_COVERAGE_OUTPUT_PATH={coverage_uri}")
        print(f"EMBEDDING_REPORT_PATH={report_uri}")
    finally:
        for df in cached:
            df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
