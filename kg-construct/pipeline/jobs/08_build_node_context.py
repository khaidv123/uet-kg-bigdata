#!/usr/bin/env python3
"""Build node context from global graph base tables."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pyspark.sql import DataFrame, SparkSession, Window, functions as F

from pipeline.common.config_loader import load_yaml
from pipeline.common.io import json_dumps
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
    return datetime.now(timezone.utc).strftime("nodectx-%Y%m%d%H%M%S")


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


def _non_empty(column_name: str) -> F.Column:
    return F.col(column_name).isNotNull() & (F.length(F.trim(F.col(column_name))) > 0)


def _context_limit(context_cfg: dict) -> int:
    context_top_k = int(context_cfg.get("context_top_k", 3))
    max_neighbors = int(context_cfg.get("max_neighbors_each_side", context_top_k))
    return max(1, min(context_top_k, max_neighbors))


def _rank_context_items(
    items: DataFrame,
    *,
    context_cfg: dict,
) -> DataFrame:
    seed = str(context_cfg.get("context_random_seed", 20260427))
    strategy = str(context_cfg.get("context_sampling_strategy", "deterministic_hash"))
    prefer_relation_diversity = bool(context_cfg.get("prefer_relation_diversity", True))
    limit = _context_limit(context_cfg)

    ranked = items.withColumn(
        "sort_key",
        F.sha2(
            F.concat_ws(
                "||",
                F.col("node_name"),
                F.col("relation"),
                F.col("neighbor_name"),
                F.col("direction"),
                F.lit(seed),
            ),
            256,
        ),
    )

    if strategy == "relation_frequency":
        relation_counts = ranked.groupBy("node_name", "relation").agg(
            F.count("*").alias("relation_count")
        )
        ranked = ranked.join(relation_counts, on=["node_name", "relation"], how="left")
        order_columns = [F.col("relation_count").asc(), F.col("sort_key").asc()]
    else:
        order_columns = [F.col("sort_key").asc()]

    if prefer_relation_diversity:
        relation_window = Window.partitionBy("node_name", "relation").orderBy(*order_columns)
        ranked = ranked.withColumn("relation_rank", F.row_number().over(relation_window))
        ranked = ranked.filter(F.col("relation_rank") == 1)

    node_window = Window.partitionBy("node_name").orderBy(*order_columns)
    return (
        ranked.withColumn("context_rank", F.row_number().over(node_window))
        .filter(F.col("context_rank") <= F.lit(limit))
        .select("node_name", "ctx", "context_rank")
    )


def _collect_context(ranked_items: DataFrame, output_column: str) -> DataFrame:
    return (
        ranked_items.groupBy("node_name")
        .agg(F.sort_array(F.collect_list(F.struct("context_rank", "ctx"))).alias("ctx_items"))
        .select(
            "node_name",
            F.concat_ws(" | ", F.expr("transform(ctx_items, x -> x.ctx)")).alias(output_column),
        )
    )


def build_predecessor_context(edges: DataFrame, *, context_cfg: dict) -> DataFrame:
    items = (
        edges.select(
            F.trim(F.col("dst")).alias("node_name"),
            F.trim(F.col("src")).alias("neighbor_name"),
            F.trim(F.col("relation")).alias("relation"),
        )
        .filter(_non_empty("node_name") & _non_empty("neighbor_name") & _non_empty("relation"))
        .withColumn("direction", F.lit("predecessor"))
        .withColumn(
            "ctx",
            F.concat_ws(
                " ",
                F.col("neighbor_name"),
                F.concat(F.lit("--"), F.col("relation"), F.lit("-->")),
                F.col("node_name"),
            ),
        )
        .dropDuplicates(["node_name", "neighbor_name", "relation", "direction"])
    )
    return _collect_context(
        _rank_context_items(items, context_cfg=context_cfg),
        "predecessor_context",
    )


def build_successor_context(edges: DataFrame, *, context_cfg: dict) -> DataFrame:
    items = (
        edges.select(
            F.trim(F.col("src")).alias("node_name"),
            F.trim(F.col("dst")).alias("neighbor_name"),
            F.trim(F.col("relation")).alias("relation"),
        )
        .filter(_non_empty("node_name") & _non_empty("neighbor_name") & _non_empty("relation"))
        .withColumn("direction", F.lit("successor"))
        .withColumn(
            "ctx",
            F.concat_ws(
                " ",
                F.col("node_name"),
                F.concat(F.lit("--"), F.col("relation"), F.lit("-->")),
                F.col("neighbor_name"),
            ),
        )
        .dropDuplicates(["node_name", "neighbor_name", "relation", "direction"])
    )
    return _collect_context(
        _rank_context_items(items, context_cfg=context_cfg),
        "successor_context",
    )


def build_node_context(
    nodes: DataFrame,
    edges: DataFrame,
    *,
    run_id: str,
    context_version: str,
    context_cfg: dict,
) -> DataFrame:
    predecessor = build_predecessor_context(edges, context_cfg=context_cfg)
    successor = build_successor_context(edges, context_cfg=context_cfg)
    max_context_chars = int(context_cfg.get("max_context_chars", 1200))

    return (
        nodes.select(
            F.trim(F.col("node_name")).alias("node_name"),
            F.col("node_type").cast("string").alias("node_type"),
        )
        .filter(_non_empty("node_name"))
        .dropDuplicates(["node_name", "node_type"])
        .join(predecessor, on="node_name", how="left")
        .join(successor, on="node_name", how="left")
        .withColumn(
            "context_text_full",
            F.concat_ws(
                " | ",
                F.when(_non_empty("predecessor_context"), F.col("predecessor_context")),
                F.when(_non_empty("successor_context"), F.col("successor_context")),
            ),
        )
        .withColumn("context_text", F.substring(F.col("context_text_full"), 1, max_context_chars))
        .withColumn("context_version", F.lit(context_version))
        .withColumn("run_id", F.lit(run_id))
        .select(
            "node_name",
            "node_type",
            "predecessor_context",
            "successor_context",
            "context_text",
            "context_version",
            "run_id",
        )
    )


def collect_metrics(node_context: DataFrame, nodes: DataFrame, edges: DataFrame) -> dict[str, Any]:
    total_nodes = nodes.count()
    output_nodes = node_context.count()
    context_nodes = node_context.filter(_non_empty("context_text")).count()
    missing_context_nodes = output_nodes - context_nodes
    orphan_context_nodes = node_context.join(
        nodes.select("node_name", "node_type"),
        on=["node_name", "node_type"],
        how="left_anti",
    ).count()

    return {
        "input_node_count": total_nodes,
        "input_edge_count": edges.count(),
        "output_node_context_count": output_nodes,
        "nodes_with_context_count": context_nodes,
        "nodes_without_context_count": missing_context_nodes,
        "orphan_context_node_count": orphan_context_nodes,
        "node_type_counts": {
            row["node_type"]: row["count"]
            for row in node_context.groupBy("node_type").count().collect()
        },
        "context_node_type_counts": {
            row["node_type"]: row["count"]
            for row in node_context.filter(_non_empty("context_text")).groupBy("node_type").count().collect()
        },
        "avg_context_length": (
            node_context.agg(F.avg(F.length("context_text")).alias("avg_context_length"))
            .collect()[0]["avg_context_length"]
            or 0.0
        ),
        "max_context_length": (
            node_context.agg(F.max(F.length("context_text")).alias("max_context_length"))
            .collect()[0]["max_context_length"]
            or 0
        ),
    }


def write_output(
    node_context: DataFrame,
    *,
    bucket: str,
    node_context_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(node_context_base_path, run_id))
    node_context.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def write_report(
    spark: SparkSession,
    metrics: dict[str, Any],
    *,
    bucket: str,
    reports_base_path: str,
    run_id: str,
    source_run_id: str,
    context_cfg: dict,
) -> str:
    output_uri = build_s3a_uri(
        bucket,
        build_run_path(f"{reports_base_path}/node_context", run_id),
    )
    payload = {
        "run_id": run_id,
        "source_run_id": source_run_id,
        "created_ts": datetime.now(timezone.utc).isoformat(),
        "context_config_json": json_dumps(context_cfg),
        "metrics_json": json_dumps(metrics),
    }
    spark.createDataFrame([payload]).coalesce(1).write.mode("overwrite").json(output_uri)
    return output_uri


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    pipeline_cfg, storage_cfg = load_configs(repo_root)
    run_id = derive_run_id(args.run_id)
    context_version = str(pipeline_cfg["runtime"]["context_version"])
    context_cfg = pipeline_cfg["node_context"]

    spark = SparkSession.builder.appName("phase2-08-build-node-context").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    cached: list[DataFrame] = []
    try:
        bucket = storage_cfg["bucket"]
        table_paths = storage_cfg["tables"]
        source_run_id = args.source_run_id or resolve_latest_run_id(
            spark,
            bucket,
            table_paths["silver.triple_nodes"],
        )

        nodes = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.triple_nodes"],
            run_id=source_run_id,
        ).cache()
        edges = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.triple_edges"],
            run_id=source_run_id,
        ).cache()
        cached.extend([nodes, edges])

        node_context = build_node_context(
            nodes,
            edges,
            run_id=run_id,
            context_version=context_version,
            context_cfg=context_cfg,
        ).cache()
        cached.append(node_context)

        output_uri = write_output(
            node_context,
            bucket=bucket,
            node_context_base_path=table_paths["silver.node_context"],
            run_id=run_id,
        )
        metrics = collect_metrics(node_context, nodes, edges)
        report_uri = write_report(
            spark,
            metrics,
            bucket=bucket,
            reports_base_path=table_paths["meta.quality_reports"],
            run_id=run_id,
            source_run_id=source_run_id,
            context_cfg=context_cfg,
        )

        if metrics["input_node_count"] != metrics["output_node_context_count"]:
            raise RuntimeError(
                "Node context row count mismatch: "
                f"input={metrics['input_node_count']}, "
                f"output={metrics['output_node_context_count']}"
            )
        if metrics["orphan_context_node_count"] > 0:
            raise RuntimeError(
                f"Found orphan node_context rows: {metrics['orphan_context_node_count']}"
            )

        print(f"NODE_CONTEXT_RUN_ID={run_id}")
        print(f"SOURCE_RUN_ID={source_run_id}")
        print(f"CONTEXT_VERSION={context_version}")
        print(f"CONTEXT_TOP_K={context_cfg.get('context_top_k')}")
        print(f"MAX_NEIGHBORS_EACH_SIDE={context_cfg.get('max_neighbors_each_side')}")
        print(f"CONTEXT_SAMPLING_STRATEGY={context_cfg.get('context_sampling_strategy')}")
        print(f"CONTEXT_RANDOM_SEED={context_cfg.get('context_random_seed')}")
        print(f"PREFER_RELATION_DIVERSITY={context_cfg.get('prefer_relation_diversity')}")
        print(f"INPUT_NODE_COUNT={metrics['input_node_count']}")
        print(f"INPUT_EDGE_COUNT={metrics['input_edge_count']}")
        print(f"OUTPUT_NODE_CONTEXT_COUNT={metrics['output_node_context_count']}")
        print(f"NODES_WITH_CONTEXT_COUNT={metrics['nodes_with_context_count']}")
        print(f"NODES_WITHOUT_CONTEXT_COUNT={metrics['nodes_without_context_count']}")
        print(f"ORPHAN_CONTEXT_NODE_COUNT={metrics['orphan_context_node_count']}")
        print(f"AVG_CONTEXT_LENGTH={metrics['avg_context_length']}")
        print(f"MAX_CONTEXT_LENGTH={metrics['max_context_length']}")
        for node_type, count in sorted(metrics["node_type_counts"].items()):
            print(f"NODE_TYPE_{node_type.upper()}={count}")
        for node_type, count in sorted(metrics["context_node_type_counts"].items()):
            print(f"CONTEXT_NODE_TYPE_{node_type.upper()}={count}")
        print(f"NODE_CONTEXT_OUTPUT_PATH={output_uri}")
        print(f"NODE_CONTEXT_REPORT_PATH={report_uri}")
    finally:
        for df in cached:
            df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
