#!/usr/bin/env python3
"""Merge validated concepts into graph gold tables."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pyspark.sql import DataFrame, SparkSession, Window, functions as F

from pipeline.common.config_loader import load_yaml
from pipeline.common.io import json_dumps
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


CONCEPT_EDGE_RELATION = "has_concept"
CONCEPT_EDGE_TYPE = "Concept"
EXPECTED_NODE_TYPES = ["entity", "event", "relation"]


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(repo_root))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--graph-base-run-id", default=None)
    parser.add_argument("--concept-run-id", default=None)
    parser.add_argument("--concept-mapping-run-id", default=None)
    parser.add_argument("--concept-coverage-run-id", default=None)
    return parser.parse_args()


def derive_run_id(explicit_run_id: Optional[str]) -> str:
    if explicit_run_id:
        return explicit_run_id
    return datetime.now(timezone.utc).strftime("mergeconcept-%Y%m%d%H%M%S")


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


def normalize_mapped_concepts(concept_mappings: DataFrame, concept_coverage: DataFrame) -> DataFrame:
    mapped_coverage = concept_coverage.filter(F.col("mapping_status") == "MAPPED").select(
        "concept_request_id"
    )
    return (
        concept_mappings.join(mapped_coverage, on="concept_request_id", how="inner")
        .select(
            F.col("concept_request_id").cast("string").alias("concept_request_id"),
            F.trim(F.col("node_name")).alias("node_name"),
            F.lower(F.trim(F.col("node_type"))).alias("node_type"),
            F.trim(F.col("concept_name")).alias("concept_name"),
            F.col("concept_id").cast("string").alias("concept_id"),
        )
        .filter(
            _non_empty("node_name")
            & F.col("node_type").isin(EXPECTED_NODE_TYPES)
            & _non_empty("concept_name")
            & _non_empty("concept_id")
        )
        .dropDuplicates(["node_name", "node_type", "concept_id"])
    )


def build_concept_nodes(
    mapped_concepts: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    return (
        mapped_concepts.select("concept_id", F.col("concept_name").alias("name"))
        .dropDuplicates(["concept_id"])
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
        .select("concept_id", "name", "run_id", "schema_version")
    )


def build_concept_edges(
    mapped_concepts: DataFrame,
    concept_nodes: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    valid_concepts = concept_nodes.select("concept_id").dropDuplicates(["concept_id"])
    return (
        mapped_concepts.join(valid_concepts, on="concept_id", how="inner")
        .select(
            F.col("node_name").alias("src"),
            F.col("concept_id").alias("dst"),
            F.lit(CONCEPT_EDGE_RELATION).alias("relation"),
            F.lit(CONCEPT_EDGE_TYPE).alias("edge_type"),
        )
        .dropDuplicates(["src", "dst", "relation", "edge_type"])
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
        .select("src", "dst", "relation", "edge_type", "run_id", "schema_version")
    )


def build_primary_concepts(mapped_concepts: DataFrame) -> DataFrame:
    ranked = mapped_concepts.withColumn(
        "concept_rank",
        F.row_number().over(
            Window.partitionBy("node_name", "node_type").orderBy(
                F.col("concept_name").asc(),
                F.col("concept_id").asc(),
            )
        ),
    )
    return ranked.filter(F.col("concept_rank") == 1).select(
        "node_name",
        "node_type",
        F.col("concept_id").alias("primary_concept_id"),
    )


def build_endpoint_nodes(triple_nodes: DataFrame) -> DataFrame:
    return (
        triple_nodes.select(
            F.trim(F.col("node_name")).alias("node_name"),
            F.lower(F.trim(F.col("node_type"))).alias("node_type"),
        )
        .filter(_non_empty("node_name") & F.col("node_type").isin(["entity", "event"]))
        .dropDuplicates(["node_name", "node_type"])
    )


def build_coverage_lookup(concept_coverage: DataFrame) -> DataFrame:
    return (
        concept_coverage.select(
            F.trim(F.col("name")).alias("name"),
            F.lower(F.trim(F.col("node_type"))).alias("node_type"),
            F.col("mapping_status").cast("string").alias("mapping_status"),
            F.col("concept_count").cast("int").alias("concept_count"),
        )
        .filter(_non_empty("name") & F.col("node_type").isin(EXPECTED_NODE_TYPES))
        .dropDuplicates(["name", "node_type"])
    )


def build_triple_edges_enriched(
    triple_edges: DataFrame,
    triple_nodes: DataFrame,
    concept_coverage: DataFrame,
    primary_concepts: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    endpoint_nodes = build_endpoint_nodes(triple_nodes)
    coverage = build_coverage_lookup(concept_coverage)

    src_nodes = endpoint_nodes.select(
        F.col("node_name").alias("src"),
        F.col("node_type").alias("src_type"),
    )
    dst_nodes = endpoint_nodes.select(
        F.col("node_name").alias("dst"),
        F.col("node_type").alias("dst_type"),
    )

    src_coverage = coverage.select(
        F.col("name").alias("src"),
        F.col("node_type").alias("src_type"),
        F.col("mapping_status").alias("src_concept_status"),
        F.col("concept_count").alias("src_concept_count"),
    )
    dst_coverage = coverage.select(
        F.col("name").alias("dst"),
        F.col("node_type").alias("dst_type"),
        F.col("mapping_status").alias("dst_concept_status"),
        F.col("concept_count").alias("dst_concept_count"),
    )
    relation_coverage = coverage.filter(F.col("node_type") == "relation").select(
        F.col("name").alias("relation"),
        F.col("mapping_status").alias("relation_concept_status"),
        F.col("concept_count").alias("relation_concept_count"),
    )

    src_primary = primary_concepts.select(
        F.col("node_name").alias("src"),
        F.col("node_type").alias("src_type"),
        F.col("primary_concept_id").alias("src_concept_id"),
    )
    dst_primary = primary_concepts.select(
        F.col("node_name").alias("dst"),
        F.col("node_type").alias("dst_type"),
        F.col("primary_concept_id").alias("dst_concept_id"),
    )
    relation_primary = primary_concepts.filter(F.col("node_type") == "relation").select(
        F.col("node_name").alias("relation"),
        F.col("primary_concept_id").alias("relation_concept_id"),
    )

    base_edges = triple_edges.select(
        F.trim(F.col("src")).alias("src"),
        F.trim(F.col("dst")).alias("dst"),
        F.trim(F.col("relation")).alias("relation"),
        F.col("edge_type").cast("string").alias("edge_type"),
        F.col("source_doc_id").cast("string").alias("source_doc_id"),
        F.col("source_chunk_id").cast("int").alias("source_chunk_id"),
    )

    return (
        base_edges.join(src_nodes, on="src", how="left")
        .join(dst_nodes, on="dst", how="left")
        .join(src_coverage, on=["src", "src_type"], how="left")
        .join(dst_coverage, on=["dst", "dst_type"], how="left")
        .join(relation_coverage, on="relation", how="left")
        .join(src_primary, on=["src", "src_type"], how="left")
        .join(dst_primary, on=["dst", "dst_type"], how="left")
        .join(relation_primary, on="relation", how="left")
        .withColumn("src_concept_status", F.coalesce(F.col("src_concept_status"), F.lit("MISSING")))
        .withColumn("dst_concept_status", F.coalesce(F.col("dst_concept_status"), F.lit("MISSING")))
        .withColumn(
            "relation_concept_status",
            F.coalesce(F.col("relation_concept_status"), F.lit("MISSING")),
        )
        .withColumn("src_concept_count", F.coalesce(F.col("src_concept_count"), F.lit(0)).cast("int"))
        .withColumn("dst_concept_count", F.coalesce(F.col("dst_concept_count"), F.lit(0)).cast("int"))
        .withColumn(
            "relation_concept_count",
            F.coalesce(F.col("relation_concept_count"), F.lit(0)).cast("int"),
        )
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
        .select(
            "src",
            "dst",
            "relation",
            "edge_type",
            "source_doc_id",
            "source_chunk_id",
            "src_type",
            "dst_type",
            "src_concept_id",
            "dst_concept_id",
            "relation_concept_id",
            "src_concept_status",
            "dst_concept_status",
            "relation_concept_status",
            "src_concept_count",
            "dst_concept_count",
            "relation_concept_count",
            "run_id",
            "schema_version",
        )
        .dropDuplicates(
            [
                "src",
                "dst",
                "relation",
                "edge_type",
                "source_doc_id",
                "source_chunk_id",
                "src_type",
                "dst_type",
            ]
        )
    )


def collect_metrics(
    triple_edges: DataFrame,
    triple_nodes: DataFrame,
    concept_coverage: DataFrame,
    concept_nodes: DataFrame,
    concept_edges: DataFrame,
    triple_edges_enriched: DataFrame,
) -> dict[str, Any]:
    triple_edge_count = triple_edges.count()
    enriched_edge_count = triple_edges_enriched.count()
    orphan_concept_edge_count = concept_edges.join(
        concept_nodes.select(F.col("concept_id").alias("dst")),
        on="dst",
        how="left_anti",
    ).count()
    duplicate_node_type_names = (
        triple_nodes.groupBy("node_name")
        .agg(F.countDistinct("node_type").alias("type_count"))
        .filter(F.col("type_count") > 1)
        .count()
    )

    status_columns = [
        "src_concept_status",
        "dst_concept_status",
        "relation_concept_status",
    ]
    enriched_status_counts = {}
    for column_name in status_columns:
        enriched_status_counts[column_name] = {
            row[column_name]: row["count"]
            for row in triple_edges_enriched.groupBy(column_name).count().collect()
        }

    return {
        "triple_node_count": triple_nodes.count(),
        "triple_edge_count": triple_edge_count,
        "concept_coverage_count": concept_coverage.count(),
        "concept_node_count": concept_nodes.count(),
        "concept_edge_count": concept_edges.count(),
        "triple_edges_enriched_count": enriched_edge_count,
        "triple_edges_enriched_delta": enriched_edge_count - triple_edge_count,
        "orphan_concept_edge_count": orphan_concept_edge_count,
        "duplicate_node_name_with_multiple_types": duplicate_node_type_names,
        "coverage_mapping_status_counts": {
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
        "enriched_status_counts": enriched_status_counts,
    }


def write_table(df: DataFrame, *, bucket: str, base_path: str, run_id: str) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(base_path, run_id))
    df.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def write_report(
    spark: SparkSession,
    metrics: dict[str, Any],
    *,
    bucket: str,
    reports_base_path: str,
    run_id: str,
    graph_base_run_id: str,
    concept_mapping_run_id: str,
    concept_coverage_run_id: str,
) -> str:
    output_uri = build_s3a_uri(
        bucket,
        build_run_path(f"{reports_base_path}/merge_concepts", run_id),
    )
    payload = {
        "run_id": run_id,
        "graph_base_run_id": graph_base_run_id,
        "concept_mapping_run_id": concept_mapping_run_id,
        "concept_coverage_run_id": concept_coverage_run_id,
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

    spark = SparkSession.builder.appName("phase2-12-merge-concepts").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    cached: list[DataFrame] = []
    try:
        bucket = storage_cfg["bucket"]
        table_paths = storage_cfg["tables"]
        graph_base_run_id = args.graph_base_run_id or resolve_latest_run_id(
            spark,
            bucket,
            table_paths["silver.triple_edges"],
        )
        concept_mapping_run_id = (
            args.concept_mapping_run_id
            or args.concept_run_id
            or resolve_latest_run_id(spark, bucket, table_paths["silver.concept_mappings"])
        )
        concept_coverage_run_id = (
            args.concept_coverage_run_id
            or args.concept_run_id
            or resolve_latest_run_id(spark, bucket, table_paths["silver.concept_coverage"])
        )

        triple_nodes = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.triple_nodes"],
            run_id=graph_base_run_id,
        ).cache()
        triple_edges = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.triple_edges"],
            run_id=graph_base_run_id,
        ).cache()
        concept_mappings = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.concept_mappings"],
            run_id=concept_mapping_run_id,
        ).cache()
        concept_coverage = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.concept_coverage"],
            run_id=concept_coverage_run_id,
        ).cache()
        cached.extend([triple_nodes, triple_edges, concept_mappings, concept_coverage])

        mapped_concepts = normalize_mapped_concepts(concept_mappings, concept_coverage).cache()
        concept_nodes = build_concept_nodes(
            mapped_concepts,
            run_id=run_id,
            schema_version=schema_version,
        ).cache()
        concept_edges = build_concept_edges(
            mapped_concepts,
            concept_nodes,
            run_id=run_id,
            schema_version=schema_version,
        ).cache()
        primary_concepts = build_primary_concepts(mapped_concepts).cache()
        triple_edges_enriched = build_triple_edges_enriched(
            triple_edges,
            triple_nodes,
            concept_coverage,
            primary_concepts,
            run_id=run_id,
            schema_version=schema_version,
        ).cache()
        cached.extend([mapped_concepts, concept_nodes, concept_edges, primary_concepts, triple_edges_enriched])

        concept_nodes_uri = write_table(
            concept_nodes,
            bucket=bucket,
            base_path=table_paths["gold.concept_nodes"],
            run_id=run_id,
        )
        concept_edges_uri = write_table(
            concept_edges,
            bucket=bucket,
            base_path=table_paths["gold.concept_edges"],
            run_id=run_id,
        )
        enriched_uri = write_table(
            triple_edges_enriched,
            bucket=bucket,
            base_path=table_paths["gold.triple_edges_enriched"],
            run_id=run_id,
        )

        metrics = collect_metrics(
            triple_edges,
            triple_nodes,
            concept_coverage,
            concept_nodes,
            concept_edges,
            triple_edges_enriched,
        )
        report_uri = write_report(
            spark,
            metrics,
            bucket=bucket,
            reports_base_path=table_paths["meta.quality_reports"],
            run_id=run_id,
            graph_base_run_id=graph_base_run_id,
            concept_mapping_run_id=concept_mapping_run_id,
            concept_coverage_run_id=concept_coverage_run_id,
        )

        if metrics["triple_edges_enriched_delta"] != 0:
            raise RuntimeError(
                "Enriched edge count changed from triple_edges: "
                f"delta={metrics['triple_edges_enriched_delta']}"
            )
        if metrics["orphan_concept_edge_count"] > 0:
            raise RuntimeError(
                f"Found concept_edges with missing concept node: {metrics['orphan_concept_edge_count']}"
            )

        print(f"MERGE_CONCEPT_RUN_ID={run_id}")
        print(f"GRAPH_BASE_RUN_ID={graph_base_run_id}")
        print(f"CONCEPT_MAPPING_RUN_ID={concept_mapping_run_id}")
        print(f"CONCEPT_COVERAGE_RUN_ID={concept_coverage_run_id}")
        print(f"TRIPLE_NODE_COUNT={metrics['triple_node_count']}")
        print(f"TRIPLE_EDGE_COUNT={metrics['triple_edge_count']}")
        print(f"CONCEPT_COVERAGE_COUNT={metrics['concept_coverage_count']}")
        print(f"CONCEPT_NODE_COUNT={metrics['concept_node_count']}")
        print(f"CONCEPT_EDGE_COUNT={metrics['concept_edge_count']}")
        print(f"TRIPLE_EDGES_ENRICHED_COUNT={metrics['triple_edges_enriched_count']}")
        print(f"TRIPLE_EDGES_ENRICHED_DELTA={metrics['triple_edges_enriched_delta']}")
        print(f"ORPHAN_CONCEPT_EDGE_COUNT={metrics['orphan_concept_edge_count']}")
        print(
            "DUPLICATE_NODE_NAME_WITH_MULTIPLE_TYPES="
            f"{metrics['duplicate_node_name_with_multiple_types']}"
        )
        for status, count in sorted(metrics["coverage_mapping_status_counts"].items()):
            print(f"COVERAGE_MAPPING_STATUS_{status.upper()}={count}")
        for node_type, type_metric in sorted(metrics["coverage_by_type"].items()):
            prefix = f"COVERAGE_TYPE_{node_type.upper()}"
            print(f"{prefix}_TOTAL={type_metric['total']}")
            print(f"{prefix}_MAPPED={type_metric['mapped']}")
            print(f"{prefix}_EMPTY={type_metric['empty']}")
            print(f"{prefix}_NOT_REQUESTED={type_metric['not_requested']}")
            print(f"{prefix}_INVALID={type_metric['invalid']}")
            print(f"{prefix}_FAILED={type_metric['failed']}")
        for column_name, status_counts in sorted(metrics["enriched_status_counts"].items()):
            for status, count in sorted(status_counts.items()):
                print(f"ENRICHED_{column_name.upper()}_{status.upper()}={count}")
        print(f"CONCEPT_NODES_OUTPUT_PATH={concept_nodes_uri}")
        print(f"CONCEPT_EDGES_OUTPUT_PATH={concept_edges_uri}")
        print(f"TRIPLE_EDGES_ENRICHED_OUTPUT_PATH={enriched_uri}")
        print(f"MERGE_CONCEPTS_REPORT_PATH={report_uri}")
    finally:
        for df in cached:
            df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
