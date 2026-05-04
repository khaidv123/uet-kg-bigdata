#!/usr/bin/env python3
"""Analyze Phase 2 graph tables.

Default mode analyzes the global materialization currently present in MinIO:
all discovered graph/concept run_ids are unioned and deduplicated by logical keys.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession, functions as F

from pipeline.common.config_loader import load_yaml
from pipeline.common.pathing import build_run_path, build_s3a_uri


STATUS_PRIORITY = {
    "MAPPED": 60,
    "VALID": 55,
    "SUCCESS": 50,
    "EMPTY": 40,
    "INVALID": 30,
    "FAILED": 20,
    "TIMEOUT": 20,
    "RATE_LIMITED": 20,
    "NOT_REQUESTED": 10,
    "MISSING": 0,
}


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(repo_root))
    parser.add_argument("--scope", choices=["global", "run"], default="global")
    parser.add_argument(
        "--orchestration-report",
        default=str(repo_root / "logs" / "phase2-default-20260427132044.json"),
        help="Used only when --scope run.",
    )
    parser.add_argument(
        "--output-md",
        default=str(repo_root / "docs" / "phase2_graph_analysis.md"),
    )
    parser.add_argument(
        "--output-json",
        default=str(repo_root / "logs" / "phase2_graph_analysis_metrics.json"),
    )
    parser.add_argument("--top-n", type=int, default=15)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [str(cell).replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def fmt_float(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def list_run_ids(spark: SparkSession, *, bucket: str, base_path: str) -> list[str]:
    jvm = spark.sparkContext._jvm
    hadoop_conf = spark.sparkContext._jsc.hadoopConfiguration()
    qualified = jvm.org.apache.hadoop.fs.Path(build_s3a_uri(bucket, base_path))
    fs = qualified.getFileSystem(hadoop_conf)
    if not fs.exists(qualified):
        return []
    run_ids: list[str] = []
    for status in fs.listStatus(qualified):
        if not status.isDirectory():
            continue
        name = status.getPath().getName()
        if name.startswith("run_id="):
            run_ids.append(name.split("=", 1)[1])
    return sorted(set(run_ids))


def read_table(
    spark: SparkSession,
    *,
    bucket: str,
    base_path: str,
    run_id: str,
) -> DataFrame:
    uri = build_s3a_uri(bucket, build_run_path(base_path, run_id))
    return spark.read.parquet(uri)


def read_many_tables(
    spark: SparkSession,
    *,
    bucket: str,
    base_path: str,
    run_ids: list[str],
) -> DataFrame:
    if not run_ids:
        raise FileNotFoundError(f"No run_id directories found for {base_path}")
    uris = [build_s3a_uri(bucket, build_run_path(base_path, run_id)) for run_id in run_ids]
    return spark.read.parquet(*uris)


def collect_kv(df: DataFrame, key_col: str, value_col: str = "count") -> dict[str, Any]:
    return {str(row[key_col]): row[value_col] for row in df.collect()}


def status_rank(column_name: str) -> F.Column:
    expr = F.lit(0)
    for status, rank in STATUS_PRIORITY.items():
        expr = F.when(F.upper(F.col(column_name)) == status, F.lit(rank)).otherwise(expr)
    return expr


def best_status_expr(rank_col: str) -> F.Column:
    expr = F.lit("MISSING")
    for status, rank in STATUS_PRIORITY.items():
        expr = F.when(F.col(rank_col) == rank, F.lit(status)).otherwise(expr)
    return expr


def dedup_global_concept_coverage(concept_coverage: DataFrame) -> DataFrame:
    base = (
        concept_coverage.select(
            F.trim(F.col("name")).alias("name"),
            F.lower(F.trim(F.col("node_type"))).alias("node_type"),
            F.upper(F.trim(F.col("mapping_status"))).alias("mapping_status"),
            F.col("concept_count").cast("int").alias("concept_count"),
        )
        .filter(F.col("name").isNotNull() & (F.length(F.col("name")) > 0))
        .withColumn("mapping_status_rank", status_rank("mapping_status"))
    )
    return (
        base.groupBy("name", "node_type")
        .agg(
            F.max("mapping_status_rank").alias("mapping_status_rank"),
            F.max("concept_count").alias("concept_count"),
        )
        .withColumn("mapping_status", best_status_expr("mapping_status_rank"))
        .select("name", "node_type", "mapping_status", "concept_count")
    )


def dedup_global_enriched_edges(enriched_edges: DataFrame) -> DataFrame:
    key_cols = ["src", "dst", "relation", "edge_type", "source_doc_id", "source_chunk_id"]
    base = enriched_edges.select(
        *[F.col(col).cast("string").alias(col) for col in ["src", "dst", "relation", "edge_type", "source_doc_id"]],
        F.col("source_chunk_id").cast("int").alias("source_chunk_id"),
        F.upper(F.trim(F.col("src_concept_status"))).alias("src_concept_status"),
        F.upper(F.trim(F.col("dst_concept_status"))).alias("dst_concept_status"),
        F.upper(F.trim(F.col("relation_concept_status"))).alias("relation_concept_status"),
        F.col("src_concept_count").cast("int").alias("src_concept_count"),
        F.col("dst_concept_count").cast("int").alias("dst_concept_count"),
        F.col("relation_concept_count").cast("int").alias("relation_concept_count"),
    )
    ranked = (
        base.withColumn("src_rank", status_rank("src_concept_status"))
        .withColumn("dst_rank", status_rank("dst_concept_status"))
        .withColumn("relation_rank", status_rank("relation_concept_status"))
    )
    return (
        ranked.groupBy(*key_cols)
        .agg(
            F.max("src_rank").alias("src_rank"),
            F.max("dst_rank").alias("dst_rank"),
            F.max("relation_rank").alias("relation_rank"),
            F.max("src_concept_count").alias("src_concept_count"),
            F.max("dst_concept_count").alias("dst_concept_count"),
            F.max("relation_concept_count").alias("relation_concept_count"),
        )
        .withColumn("src_concept_status", best_status_expr("src_rank"))
        .withColumn("dst_concept_status", best_status_expr("dst_rank"))
        .withColumn("relation_concept_status", best_status_expr("relation_rank"))
        .select(
            *key_cols,
            "src_concept_status",
            "dst_concept_status",
            "relation_concept_status",
            "src_concept_count",
            "dst_concept_count",
            "relation_concept_count",
        )
    )


def compute_components(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, Any]:
    parent = {node: node for node in nodes}
    rank = {node: 0 for node in nodes}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if rank[left_root] < rank[right_root]:
            parent[left_root] = right_root
        elif rank[left_root] > rank[right_root]:
            parent[right_root] = left_root
        else:
            parent[right_root] = left_root
            rank[left_root] += 1

    for src, dst in edges:
        if src in parent and dst in parent:
            union(src, dst)

    sizes: Counter[str] = Counter(find(node) for node in nodes)
    ordered_sizes = sorted(sizes.values(), reverse=True)
    largest = ordered_sizes[0] if ordered_sizes else 0
    return {
        "weak_component_count": len(ordered_sizes),
        "largest_weak_component_size": largest,
        "largest_weak_component_ratio": largest / len(nodes) if nodes else 0.0,
        "top_weak_component_sizes": ordered_sizes[:10],
    }


def load_scope_tables(
    spark: SparkSession,
    repo_root: Path,
    *,
    scope: str,
    orchestration_report: Path,
) -> tuple[dict[str, DataFrame], dict[str, Any]]:
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    bucket = storage_cfg["bucket"]
    paths = storage_cfg["tables"]

    if scope == "run":
        report = read_json(orchestration_report)
        state = report["final_state"]
        graph_run_ids = [state["GRAPH_BASE_RUN_ID"]]
        concept_validation_run_ids = [state["VALIDATE_CONCEPT_RUN_ID"]]
        merge_run_ids = [state["MERGE_CONCEPT_RUN_ID"]]
        source_label = report["run_label"]
        source_run_id = report["steps"][0]["metrics"].get("SOURCE_RUN_ID")
    else:
        graph_run_ids = list_run_ids(spark, bucket=bucket, base_path=paths["silver.triple_nodes"])
        concept_validation_run_ids = list_run_ids(spark, bucket=bucket, base_path=paths["silver.concept_coverage"])
        merge_run_ids = list_run_ids(spark, bucket=bucket, base_path=paths["gold.triple_edges_enriched"])
        source_label = "global-minio"
        source_run_id = "all discovered run_ids"

    tables = {
        "triple_nodes": read_many_tables(
            spark, bucket=bucket, base_path=paths["silver.triple_nodes"], run_ids=graph_run_ids
        )
        .select("node_name", "node_type")
        .dropDuplicates(["node_name", "node_type"])
        .cache(),
        "triple_edges": read_many_tables(
            spark, bucket=bucket, base_path=paths["silver.triple_edges"], run_ids=graph_run_ids
        )
        .select("src", "dst", "relation", "edge_type", "source_doc_id", "source_chunk_id")
        .dropDuplicates(["src", "dst", "relation", "edge_type", "source_doc_id", "source_chunk_id"])
        .cache(),
        "text_nodes": read_many_tables(
            spark, bucket=bucket, base_path=paths["silver.text_nodes"], run_ids=graph_run_ids
        )
        .select("text_id", "original_text")
        .dropDuplicates(["text_id"])
        .cache(),
        "text_edges": read_many_tables(
            spark, bucket=bucket, base_path=paths["silver.text_edges"], run_ids=graph_run_ids
        )
        .select("node_name", "text_id", "edge_type")
        .dropDuplicates(["node_name", "text_id", "edge_type"])
        .cache(),
        "concept_nodes": read_many_tables(
            spark, bucket=bucket, base_path=paths["gold.concept_nodes"], run_ids=merge_run_ids
        )
        .select("concept_id", "name")
        .dropDuplicates(["concept_id"])
        .cache(),
        "concept_edges": read_many_tables(
            spark, bucket=bucket, base_path=paths["gold.concept_edges"], run_ids=merge_run_ids
        )
        .select("src", "dst", "relation", "edge_type")
        .dropDuplicates(["src", "dst", "relation", "edge_type"])
        .cache(),
        "concept_coverage": dedup_global_concept_coverage(
            read_many_tables(
                spark,
                bucket=bucket,
                base_path=paths["silver.concept_coverage"],
                run_ids=concept_validation_run_ids,
            )
        ).cache(),
        "enriched_edges": dedup_global_enriched_edges(
            read_many_tables(
                spark,
                bucket=bucket,
                base_path=paths["gold.triple_edges_enriched"],
                run_ids=merge_run_ids,
            )
        ).cache(),
    }

    lineage = {
        "scope": scope,
        "source_label": source_label,
        "source_run_id": source_run_id,
        "graph_run_ids": graph_run_ids,
        "concept_validation_run_ids": concept_validation_run_ids,
        "merge_run_ids": merge_run_ids,
        "bucket": bucket,
    }
    return tables, lineage


def analyze_tables(tables: dict[str, DataFrame], lineage: dict[str, Any], top_n: int) -> dict[str, Any]:
    triple_nodes = tables["triple_nodes"]
    triple_edges = tables["triple_edges"]
    text_nodes = tables["text_nodes"]
    text_edges = tables["text_edges"]
    concept_nodes = tables["concept_nodes"]
    concept_edges = tables["concept_edges"]
    concept_coverage = tables["concept_coverage"]
    enriched_edges = tables["enriched_edges"]

    node_count = triple_nodes.count()
    edge_count = triple_edges.count()
    distinct_triple_count = triple_edges.dropDuplicates(["src", "relation", "dst", "edge_type"]).count()
    directed_pair_count = triple_edges.dropDuplicates(["src", "dst"]).count()
    relation_count = triple_edges.select("relation").dropDuplicates(["relation"]).count()
    reciprocal_pair_count = (
        triple_edges.select(F.col("src").alias("a"), F.col("dst").alias("b"))
        .dropDuplicates(["a", "b"])
        .join(
            triple_edges.select(F.col("src").alias("b"), F.col("dst").alias("a")).dropDuplicates(["a", "b"]),
            on=["a", "b"],
            how="inner",
        )
        .filter(F.col("a") != F.col("b"))
        .count()
        // 2
    )

    max_directed_edges = node_count * (node_count - 1)
    density_by_rows = edge_count / max_directed_edges if max_directed_edges else 0.0
    density_by_pairs = directed_pair_count / max_directed_edges if max_directed_edges else 0.0

    in_degrees = triple_edges.groupBy(F.col("dst").alias("node_name")).agg(F.count("*").alias("in_degree"))
    out_degrees = triple_edges.groupBy(F.col("src").alias("node_name")).agg(F.count("*").alias("out_degree"))
    degrees = (
        triple_nodes.select("node_name", "node_type")
        .join(in_degrees, on="node_name", how="left")
        .join(out_degrees, on="node_name", how="left")
        .fillna({"in_degree": 0, "out_degree": 0})
        .withColumn("degree", F.col("in_degree") + F.col("out_degree"))
        .cache()
    )

    source_per_node = text_edges.groupBy("node_name").agg(F.countDistinct("text_id").alias("source_text_count"))
    nodes_with_sources = source_per_node.count()
    text_nodes_with_edges = text_edges.select("text_id").dropDuplicates(["text_id"]).count()
    source_stats = source_per_node.agg(
        F.avg("source_text_count").alias("avg_source_texts_per_node"),
        F.max("source_text_count").alias("max_source_texts_per_node"),
    ).collect()[0]
    nodes_per_text_stats = text_edges.groupBy("text_id").agg(F.countDistinct("node_name").alias("node_count")).agg(
        F.avg("node_count").alias("avg_nodes_per_text"),
        F.max("node_count").alias("max_nodes_per_text"),
    ).collect()[0]

    mapped_items_by_type = collect_kv(
        concept_coverage.groupBy("node_type", "mapping_status")
        .count()
        .withColumn("key", F.concat_ws("/", F.col("node_type"), F.col("mapping_status"))),
        "key",
    )
    enriched_status_by_column = {}
    for column in ["src_concept_status", "dst_concept_status", "relation_concept_status"]:
        enriched_status_by_column[column] = collect_kv(enriched_edges.groupBy(column).count(), column)

    top_relations = [
        {"relation": row["relation"], "count": row["count"]}
        for row in triple_edges.groupBy("relation").count().orderBy(F.desc("count"), F.asc("relation")).limit(top_n).collect()
    ]
    top_nodes = [
        {
            "node_name": row["node_name"],
            "node_type": row["node_type"],
            "degree": row["degree"],
            "in_degree": row["in_degree"],
            "out_degree": row["out_degree"],
        }
        for row in degrees.orderBy(F.desc("degree"), F.asc("node_name")).limit(top_n).collect()
    ]
    top_source_nodes = [
        {"node_name": row["node_name"], "source_text_count": row["source_text_count"]}
        for row in source_per_node.orderBy(F.desc("source_text_count"), F.asc("node_name")).limit(top_n).collect()
    ]

    component_nodes = [row["node_name"] for row in triple_nodes.select("node_name").collect()]
    component_edges = [(row["src"], row["dst"]) for row in triple_edges.select("src", "dst").dropDuplicates(["src", "dst"]).collect()]
    components = compute_components(component_nodes, component_edges)

    orphan_text_edges = text_edges.join(text_nodes.select("text_id"), on="text_id", how="left_anti").count()
    orphan_enriched_src = enriched_edges.join(
        triple_nodes.select(F.col("node_name").alias("src")).dropDuplicates(["src"]),
        on="src",
        how="left_anti",
    ).count()
    orphan_enriched_dst = enriched_edges.join(
        triple_nodes.select(F.col("node_name").alias("dst")).dropDuplicates(["dst"]),
        on="dst",
        how="left_anti",
    ).count()
    orphan_concept_edges = concept_edges.join(
        concept_nodes.select(F.col("concept_id").alias("dst")).dropDuplicates(["dst"]),
        on="dst",
        how="left_anti",
    ).count()

    return {
        "scope": lineage["scope"],
        "source_label": lineage["source_label"],
        "source_run_id": lineage["source_run_id"],
        "run_ids": {
            "graph_base": lineage["graph_run_ids"],
            "concept_validation": lineage["concept_validation_run_ids"],
            "merge_concepts": lineage["merge_run_ids"],
        },
        "counts": {
            "triple_nodes": node_count,
            "triple_edges": edge_count,
            "distinct_semantic_triples": distinct_triple_count,
            "distinct_directed_pairs": directed_pair_count,
            "relations": relation_count,
            "text_nodes": text_nodes.count(),
            "text_edges": text_edges.count(),
            "concept_nodes": concept_nodes.count(),
            "concept_edges": concept_edges.count(),
            "triple_edges_enriched": enriched_edges.count(),
            "reciprocal_directed_pairs": reciprocal_pair_count,
        },
        "node_type_counts": collect_kv(triple_nodes.groupBy("node_type").count(), "node_type"),
        "edge_type_counts": collect_kv(triple_edges.groupBy("edge_type").count(), "edge_type"),
        "density": {
            "directed_density_by_rows": density_by_rows,
            "directed_density_by_distinct_pairs": density_by_pairs,
            "avg_degree_by_rows": (2 * edge_count / node_count) if node_count else 0.0,
            "avg_degree_by_distinct_pairs": (2 * directed_pair_count / node_count) if node_count else 0.0,
        },
        "degree": {
            "zero_degree_nodes": degrees.filter(F.col("degree") == 0).count(),
            "avg_degree": degrees.agg(F.avg("degree").alias("value")).collect()[0]["value"],
            "max_degree": degrees.agg(F.max("degree").alias("value")).collect()[0]["value"],
            "p50_degree": degrees.approxQuantile("degree", [0.5], 0.01)[0],
            "p90_degree": degrees.approxQuantile("degree", [0.9], 0.01)[0],
            "p99_degree": degrees.approxQuantile("degree", [0.99], 0.01)[0],
        },
        "components": components,
        "provenance": {
            "nodes_with_source_text": nodes_with_sources,
            "text_nodes_with_edges": text_nodes_with_edges,
            "orphan_text_edges": orphan_text_edges,
            "avg_source_texts_per_node": source_stats["avg_source_texts_per_node"],
            "max_source_texts_per_node": source_stats["max_source_texts_per_node"],
            "avg_nodes_per_text": nodes_per_text_stats["avg_nodes_per_text"],
            "max_nodes_per_text": nodes_per_text_stats["max_nodes_per_text"],
        },
        "concept": {
            "coverage_by_type_status": mapped_items_by_type,
            "enriched_status_by_column": enriched_status_by_column,
            "orphan_concept_edges": orphan_concept_edges,
        },
        "quality": {
            "orphan_enriched_src": orphan_enriched_src,
            "orphan_enriched_dst": orphan_enriched_dst,
            "enriched_delta_vs_triple_edges": enriched_edges.count() - edge_count,
        },
        "top_relations": top_relations,
        "top_nodes": top_nodes,
        "top_source_nodes": top_source_nodes,
    }


def render_run_ids(run_ids: list[str]) -> str:
    return ", ".join(f"`{run_id}`" for run_id in run_ids)


def render_markdown(metrics: dict[str, Any]) -> str:
    counts = metrics["counts"]
    density = metrics["density"]
    degree = metrics["degree"]
    provenance = metrics["provenance"]
    components = metrics["components"]
    concept = metrics["concept"]
    quality = metrics["quality"]
    node_type_counts = metrics["node_type_counts"]
    entity_count = node_type_counts.get("entity", 0)
    event_count = node_type_counts.get("event", 0)

    lines: list[str] = []
    title_scope = "Global MinIO Graph" if metrics["scope"] == "global" else "Single Run Graph"
    lines.append(f"# Phase 2 Graph Analysis - {title_scope}")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("")
    lines.append(f"- Scope: `{metrics['scope']}`")
    lines.append(f"- Source label: `{metrics['source_label']}`")
    lines.append(f"- Raw/source note: `{metrics['source_run_id']}`")
    lines.append(f"- Metrics JSON: `logs/phase2_graph_analysis_metrics.json`")
    lines.append("")
    lines.append("Các bảng được union/dedup theo khóa logic từ các `run_id` sau:")
    lines.append("")
    lines.append(markdown_table(
        ["Layer", "Table", "Run ids"],
        [
            ["Silver graph", "`silver.triple_nodes`", render_run_ids(metrics["run_ids"]["graph_base"])],
            ["Silver graph", "`silver.triple_edges`", render_run_ids(metrics["run_ids"]["graph_base"])],
            ["Silver provenance", "`silver.text_nodes`", render_run_ids(metrics["run_ids"]["graph_base"])],
            ["Silver provenance", "`silver.text_edges`", render_run_ids(metrics["run_ids"]["graph_base"])],
            ["Silver concept status", "`silver.concept_coverage`", render_run_ids(metrics["run_ids"]["concept_validation"])],
            ["Gold concept", "`gold.concept_nodes`", render_run_ids(metrics["run_ids"]["merge_concepts"])],
            ["Gold concept", "`gold.concept_edges`", render_run_ids(metrics["run_ids"]["merge_concepts"])],
            ["Gold graph", "`gold.triple_edges_enriched`", render_run_ids(metrics["run_ids"]["merge_concepts"])],
        ],
    ))
    lines.append("")
    lines.append("Dedup rules dùng trong report:")
    lines.append("")
    lines.append("- `triple_nodes`: dedup theo `node_name + node_type`.")
    lines.append("- `triple_edges`: dedup theo `src + relation + dst + edge_type + source_doc_id + source_chunk_id` để giữ provenance nhưng tránh trùng cross-run.")
    lines.append("- `text_nodes`: dedup theo `text_id`; `text_edges`: dedup theo `node_name + text_id + edge_type`.")
    lines.append("- `concept_nodes`: dedup theo `concept_id`; `concept_edges`: dedup theo `src + dst + relation + edge_type`.")
    lines.append("- `concept_coverage` và `triple_edges_enriched`: nếu cùng item xuất hiện ở nhiều run, lấy trạng thái tốt nhất theo thứ tự `MAPPED > EMPTY > INVALID/FAILED/TIMEOUT/RATE_LIMITED > NOT_REQUESTED > MISSING`.")
    lines.append("")
    lines.append("## 2. Tổng Quan Graph")
    lines.append("")
    lines.append(markdown_table(
        ["Metric", "Value", "Ý nghĩa"],
        [
            ["Triple nodes", fmt_int(counts["triple_nodes"]), "Node tri thức gốc, gồm entity và event."],
            ["Entity nodes", fmt_int(entity_count), "Thực thể được trích xuất."],
            ["Event nodes", fmt_int(event_count), "Sự kiện được trích xuất."],
            ["Triple edge rows", fmt_int(counts["triple_edges"]), "Cạnh tri thức có provenance theo doc/chunk."],
            ["Distinct semantic triples", fmt_int(counts["distinct_semantic_triples"]), "Dedup theo `src + relation + dst + edge_type`."],
            ["Distinct directed pairs", fmt_int(counts["distinct_directed_pairs"]), "Dedup theo `src + dst`, dùng để đo density topology."],
            ["Distinct relations", fmt_int(counts["relations"]), "Số relation string riêng biệt."],
            ["Text nodes", fmt_int(counts["text_nodes"]), "Chunk nguồn dùng làm provenance."],
            ["Text edges", fmt_int(counts["text_edges"]), "Liên kết node tri thức với chunk nguồn."],
            ["Concept nodes", fmt_int(counts["concept_nodes"]), "Concept đã sinh từ các concept runs hiện có."],
            ["Concept edges", fmt_int(counts["concept_edges"]), "Liên kết item gốc sang concept."],
            ["Enriched edges", fmt_int(counts["triple_edges_enriched"]), "Cạnh gốc đã được merge concept status."],
        ],
    ))
    lines.append("")
    lines.append(
        f"Graph global hiện nghiêng về `entity`: `{fmt_int(entity_count)}` entity so với `{fmt_int(event_count)}` event, "
        f"entity nhiều hơn khoảng `{entity_count / max(event_count, 1):.2f}x`."
    )
    lines.append("")
    lines.append("## 3. Độ Dày / Độ Thưa")
    lines.append("")
    lines.append(markdown_table(
        ["Metric", "Value"],
        [
            ["Directed density, theo edge rows", fmt_float(density["directed_density_by_rows"], 6)],
            ["Directed density, theo distinct src-dst pairs", fmt_float(density["directed_density_by_distinct_pairs"], 6)],
            ["Average degree, theo edge rows", fmt_float(density["avg_degree_by_rows"], 2)],
            ["Average degree, theo distinct src-dst pairs", fmt_float(density["avg_degree_by_distinct_pairs"], 2)],
            ["Reciprocal directed pairs", fmt_int(counts["reciprocal_directed_pairs"])],
        ],
    ))
    lines.append("")
    lines.append(
        f"Với `{fmt_int(counts['triple_nodes'])}` node, directed density theo distinct pair là "
        f"`{fmt_float(density['directed_density_by_distinct_pairs'] * 100, 4)}%`. "
        "Đây là **graph rất thưa**, đúng tính chất của knowledge graph trích xuất từ văn bản: "
        "nhiều node, mỗi node chỉ có một số ít quan hệ trực tiếp."
    )
    lines.append("")
    lines.append("## 4. Degree Và Hub")
    lines.append("")
    lines.append(markdown_table(
        ["Metric", "Value"],
        [
            ["Zero-degree nodes", fmt_int(degree["zero_degree_nodes"])],
            ["Average degree", fmt_float(float(degree["avg_degree"]), 2)],
            ["Median degree, approx", fmt_float(float(degree["p50_degree"]), 2)],
            ["P90 degree, approx", fmt_float(float(degree["p90_degree"]), 2)],
            ["P99 degree, approx", fmt_float(float(degree["p99_degree"]), 2)],
            ["Max degree", fmt_int(degree["max_degree"])],
        ],
    ))
    lines.append("")
    lines.append("Top node theo degree:")
    lines.append("")
    lines.append(markdown_table(
        ["Node", "Type", "Degree", "In", "Out"],
        [
            [row["node_name"], row["node_type"], fmt_int(row["degree"]), fmt_int(row["in_degree"]), fmt_int(row["out_degree"])]
            for row in metrics["top_nodes"]
        ],
    ))
    lines.append("")
    lines.append("Không có isolated node vì `triple_nodes` được materialize từ endpoint của edge. Hub lớn thường là entity/event xuất hiện xuyên nhiều chunk hoặc alias chưa được chuẩn hóa.")
    lines.append("")
    lines.append("## 5. Connected Components")
    lines.append("")
    lines.append(markdown_table(
        ["Metric", "Value"],
        [
            ["Weak components", fmt_int(components["weak_component_count"])],
            ["Largest weak component size", fmt_int(components["largest_weak_component_size"])],
            ["Largest weak component ratio", fmt_float(components["largest_weak_component_ratio"] * 100, 2) + "%"],
            ["Top component sizes", ", ".join(fmt_int(value) for value in components["top_weak_component_sizes"])],
        ],
    ))
    lines.append("")
    lines.append("Một giant component lớn là tín hiệu tốt cho traversal/search, còn các component nhỏ thường là cụm riêng theo document hoặc chủ đề hẹp.")
    lines.append("")
    lines.append("## 6. Relation Và Edge Type")
    lines.append("")
    lines.append("Edge type count:")
    lines.append("")
    lines.append(markdown_table(
        ["Edge type", "Count"],
        [[key, fmt_int(value)] for key, value in sorted(metrics["edge_type_counts"].items())],
    ))
    lines.append("")
    lines.append("Top relation:")
    lines.append("")
    lines.append(markdown_table(
        ["Relation", "Count"],
        [[row["relation"], fmt_int(row["count"])] for row in metrics["top_relations"]],
    ))
    lines.append("")
    lines.append("`is participated by` thường chiếm tỷ trọng lớn vì đây là relation chuẩn hóa cho event-entity edge. Các relation còn lại vẫn là relation string thô, nên bước ontology/concept hóa relation sẽ rất quan trọng.")
    lines.append("")
    lines.append("## 7. Provenance Qua Text Nodes")
    lines.append("")
    lines.append(markdown_table(
        ["Metric", "Value"],
        [
            ["Text nodes", fmt_int(counts["text_nodes"])],
            ["Text edges", fmt_int(counts["text_edges"])],
            ["Nodes with source text", fmt_int(provenance["nodes_with_source_text"])],
            ["Text nodes with edges", fmt_int(provenance["text_nodes_with_edges"])],
            ["Orphan text edges", fmt_int(provenance["orphan_text_edges"])],
            ["Avg source texts per node", fmt_float(float(provenance["avg_source_texts_per_node"]), 2)],
            ["Max source texts per node", fmt_int(provenance["max_source_texts_per_node"])],
            ["Avg nodes per text", fmt_float(float(provenance["avg_nodes_per_text"]), 2)],
            ["Max nodes per text", fmt_int(provenance["max_nodes_per_text"])],
        ],
    ))
    lines.append("")
    lines.append("Top node xuất hiện ở nhiều text chunk nhất:")
    lines.append("")
    lines.append(markdown_table(
        ["Node", "Source text count"],
        [[row["node_name"], fmt_int(row["source_text_count"])] for row in metrics["top_source_nodes"]],
    ))
    lines.append("")
    lines.append("Provenance dùng được cho trace-back: mỗi node có thể nối ngược về chunk nguồn qua `text_edges -> text_nodes`.")
    lines.append("")
    lines.append("## 8. Concept Coverage Trên Graph")
    lines.append("")
    coverage_rows = []
    for key, value in sorted(concept["coverage_by_type_status"].items()):
        node_type, status = key.split("/", 1)
        coverage_rows.append([node_type, status, fmt_int(value)])
    lines.append(markdown_table(["Type", "Mapping status", "Count"], coverage_rows))
    lines.append("")
    lines.append("Concept status trên enriched edge rows:")
    lines.append("")
    status_rows = []
    for column, status_counts in concept["enriched_status_by_column"].items():
        for status, count in sorted(status_counts.items()):
            status_rows.append([column, status, fmt_int(count)])
    lines.append(markdown_table(["Column", "Status", "Edge rows"], status_rows))
    lines.append("")
    lines.append("Coverage concept hiện là hợp nhất của các pilot concept runs đã có trong MinIO. Nó chưa phải full coverage nếu còn nhiều `NOT_REQUESTED`, nhưng đã đánh dấu rõ phần nào đã `MAPPED` để tránh gọi API lặp.")
    lines.append("")
    lines.append("## 9. Quality Check")
    lines.append("")
    lines.append(markdown_table(
        ["Check", "Value", "Kết luận"],
        [
            ["Enriched delta vs triple_edges", fmt_int(quality["enriched_delta_vs_triple_edges"]), "0 nghĩa là enriched global giữ cùng số edge provenance với graph base global."],
            ["Orphan enriched src", fmt_int(quality["orphan_enriched_src"]), "0 nghĩa là mọi `src` có trong `triple_nodes`."],
            ["Orphan enriched dst", fmt_int(quality["orphan_enriched_dst"]), "0 nghĩa là mọi `dst` có trong `triple_nodes`."],
            ["Orphan concept edges", fmt_int(concept["orphan_concept_edges"]), "0 nghĩa là mọi concept edge trỏ tới concept node hợp lệ."],
            ["Orphan text edges", fmt_int(provenance["orphan_text_edges"]), "0 nghĩa là mọi text edge trỏ tới text node hợp lệ."],
        ],
    ))
    lines.append("")
    lines.append("## 10. Kết Luận")
    lines.append("")
    lines.append("- Đây là phân tích global trên toàn bộ run graph hiện có trong MinIO, không chỉ một orchestration run nhỏ.")
    lines.append("- Graph vẫn rất thưa theo density, đúng với KG; nên dùng traversal theo neighborhood, provenance và concept status.")
    lines.append("- Concept coverage hiện phản ánh các pilot concept runs đã chạy; để full graph hoàn chỉnh cần tiếp tục concept hóa phần `NOT_REQUESTED` và recompute enriched graph global.")
    lines.append("- Có thể dùng report này làm baseline trước khi xây job global merge/materialization chính thức.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_md = Path(args.output_md).resolve()
    output_json = Path(args.output_json).resolve()

    spark = SparkSession.builder.appName("phase2-graph-analysis").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    try:
        tables, lineage = load_scope_tables(
            spark,
            repo_root,
            scope=args.scope,
            orchestration_report=Path(args.orchestration_report).resolve(),
        )
        metrics = analyze_tables(tables, lineage, args.top_n)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(metrics), encoding="utf-8")
        print(f"GRAPH_ANALYSIS_SCOPE={args.scope}")
        print(f"GRAPH_ANALYSIS_REPORT_PATH={output_md}")
        print(f"GRAPH_ANALYSIS_METRICS_PATH={output_json}")
        print(f"GRAPH_BASE_RUN_IDS={','.join(metrics['run_ids']['graph_base'])}")
        print(f"MERGE_RUN_IDS={','.join(metrics['run_ids']['merge_concepts'])}")
        print(f"GRAPH_NODE_COUNT={metrics['counts']['triple_nodes']}")
        print(f"GRAPH_EDGE_COUNT={metrics['counts']['triple_edges']}")
        print(f"GRAPH_DENSITY={metrics['density']['directed_density_by_distinct_pairs']}")
        print(f"GRAPH_WEAK_COMPONENT_COUNT={metrics['components']['weak_component_count']}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
