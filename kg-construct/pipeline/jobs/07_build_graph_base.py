#!/usr/bin/env python3
"""Build graph base tables from validated extraction records."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pyspark.sql import DataFrame, SparkSession, functions as F

from pipeline.common.config_loader import load_yaml
from pipeline.common.io import json_dumps
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


EVENT_ENTITY_RELATION = "is participated by"
RELATION_EDGE_TYPE = "Relation"
SOURCE_EDGE_TYPE = "Source"


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
    return datetime.now(timezone.utc).strftime("graphbase-%Y%m%d%H%M%S")


def load_configs(repo_root: Path) -> tuple[dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    return pipeline_cfg, storage_cfg


def read_input(
    spark: SparkSession,
    *,
    bucket: str,
    extraction_structured_base_path: str,
    source_run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(
        bucket,
        build_run_path(extraction_structured_base_path, source_run_id),
    )
    return spark.read.parquet(input_uri)


def _non_empty(column_name: str) -> F.Column:
    return F.col(column_name).isNotNull() & (F.length(F.trim(F.col(column_name))) > 0)


def build_entity_relation_edges(
    structured_df: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    return (
        structured_df.select(
            F.col("doc_id").alias("source_doc_id"),
            F.col("chunk_id").cast("int").alias("source_chunk_id"),
            F.col("original_text"),
            F.explode_outer("entity_relation").alias("tr"),
        )
        .filter(F.col("tr").isNotNull())
        .select(
            F.trim(F.col("tr.Head")).alias("src"),
            F.trim(F.col("tr.Tail")).alias("dst"),
            F.trim(F.col("tr.Relation")).alias("relation"),
            F.lit(RELATION_EDGE_TYPE).alias("edge_type"),
            "source_doc_id",
            "source_chunk_id",
            "original_text",
        )
        .filter(_non_empty("src") & _non_empty("dst") & _non_empty("relation"))
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
    )


def build_event_relation_edges(
    structured_df: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    return (
        structured_df.select(
            F.col("doc_id").alias("source_doc_id"),
            F.col("chunk_id").cast("int").alias("source_chunk_id"),
            F.col("original_text"),
            F.explode_outer("event_relation").alias("tr"),
        )
        .filter(F.col("tr").isNotNull())
        .select(
            F.trim(F.col("tr.Head")).alias("src"),
            F.trim(F.col("tr.Tail")).alias("dst"),
            F.trim(F.col("tr.Relation")).alias("relation"),
            F.lit(RELATION_EDGE_TYPE).alias("edge_type"),
            "source_doc_id",
            "source_chunk_id",
            "original_text",
        )
        .filter(_non_empty("src") & _non_empty("dst") & _non_empty("relation"))
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
    )


def build_event_entity_edges(
    structured_df: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    return (
        structured_df.select(
            F.col("doc_id").alias("source_doc_id"),
            F.col("chunk_id").cast("int").alias("source_chunk_id"),
            F.col("original_text"),
            F.explode_outer("event_entity").alias("ev"),
        )
        .filter(F.col("ev").isNotNull())
        .select(
            "source_doc_id",
            "source_chunk_id",
            "original_text",
            F.trim(F.col("ev.Event")).alias("src"),
            F.explode_outer(F.col("ev.Entity")).alias("dst"),
        )
        .select(
            "source_doc_id",
            "source_chunk_id",
            "original_text",
            F.col("src"),
            F.trim(F.col("dst")).alias("dst"),
            F.lit(EVENT_ENTITY_RELATION).alias("relation"),
            F.lit(RELATION_EDGE_TYPE).alias("edge_type"),
        )
        .filter(_non_empty("src") & _non_empty("dst"))
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
    )


def build_all_edges(
    structured_df: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> tuple[DataFrame, DataFrame, DataFrame, DataFrame]:
    entity_edges = build_entity_relation_edges(
        structured_df,
        run_id=run_id,
        schema_version=schema_version,
    )
    event_relation_edges = build_event_relation_edges(
        structured_df,
        run_id=run_id,
        schema_version=schema_version,
    )
    event_entity_edges = build_event_entity_edges(
        structured_df,
        run_id=run_id,
        schema_version=schema_version,
    )
    all_edges = (
        entity_edges.unionByName(event_relation_edges)
        .unionByName(event_entity_edges)
        .dropDuplicates(
            [
                "src",
                "dst",
                "relation",
                "edge_type",
                "source_doc_id",
                "source_chunk_id",
            ]
        )
    )
    return entity_edges, event_relation_edges, event_entity_edges, all_edges


def build_triple_edges(all_edges: DataFrame) -> DataFrame:
    return all_edges.select(
        "src",
        "dst",
        "relation",
        "edge_type",
        "source_doc_id",
        "source_chunk_id",
        "run_id",
        "schema_version",
    )


def build_text_nodes(
    structured_df: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    return (
        structured_df.select(F.trim(F.col("original_text")).alias("original_text"))
        .filter(_non_empty("original_text"))
        .dropDuplicates(["original_text"])
        .withColumn("text_id", F.sha2(F.col("original_text"), 256))
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
        .select("text_id", "original_text", "run_id", "schema_version")
    )


def build_triple_nodes(
    entity_edges: DataFrame,
    event_relation_edges: DataFrame,
    event_entity_edges: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    entity_nodes = (
        entity_edges.select(F.col("src").alias("node_name"))
        .unionByName(entity_edges.select(F.col("dst").alias("node_name")))
        .unionByName(event_entity_edges.select(F.col("dst").alias("node_name")))
        .filter(_non_empty("node_name"))
        .dropDuplicates(["node_name"])
        .withColumn("node_type", F.lit("entity"))
    )

    event_nodes = (
        event_relation_edges.select(F.col("src").alias("node_name"))
        .unionByName(event_relation_edges.select(F.col("dst").alias("node_name")))
        .unionByName(event_entity_edges.select(F.col("src").alias("node_name")))
        .filter(_non_empty("node_name"))
        .dropDuplicates(["node_name"])
        .withColumn("node_type", F.lit("event"))
    )

    return (
        entity_nodes.unionByName(event_nodes)
        .dropDuplicates(["node_name", "node_type"])
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
        .select("node_name", "node_type", "run_id", "schema_version")
    )


def build_text_edges(
    all_edges: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    edges_with_text_id = all_edges.withColumn("text_id", F.sha2(F.col("original_text"), 256))
    return (
        edges_with_text_id.select(F.col("src").alias("node_name"), "text_id")
        .unionByName(edges_with_text_id.select(F.col("dst").alias("node_name"), "text_id"))
        .filter(_non_empty("node_name") & _non_empty("text_id"))
        .dropDuplicates(["node_name", "text_id"])
        .withColumn("edge_type", F.lit(SOURCE_EDGE_TYPE))
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
        .select("node_name", "text_id", "edge_type", "run_id", "schema_version")
    )


def build_missing_concepts(
    triple_nodes: DataFrame,
    all_edges: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> DataFrame:
    entities = (
        triple_nodes.filter(F.col("node_type") == "entity")
        .select(F.col("node_name").alias("name"))
        .withColumn("node_type", F.lit("entity"))
    )
    events = (
        triple_nodes.filter(F.col("node_type") == "event")
        .select(F.col("node_name").alias("name"))
        .withColumn("node_type", F.lit("event"))
    )
    relations = (
        all_edges.select(F.col("relation").alias("name"))
        .filter(_non_empty("name"))
        .dropDuplicates(["name"])
        .withColumn("node_type", F.lit("relation"))
    )

    return (
        entities.unionByName(events)
        .unionByName(relations)
        .dropDuplicates(["name", "node_type"])
        .withColumn("run_id", F.lit(run_id))
        .withColumn("schema_version", F.lit(schema_version))
        .select("name", "node_type", "run_id", "schema_version")
    )


def build_graph_base_tables(
    structured_df: DataFrame,
    *,
    run_id: str,
    schema_version: str,
) -> dict[str, DataFrame]:
    entity_edges, event_relation_edges, event_entity_edges, all_edges = build_all_edges(
        structured_df,
        run_id=run_id,
        schema_version=schema_version,
    )
    triple_edges = build_triple_edges(all_edges)
    triple_nodes = build_triple_nodes(
        entity_edges,
        event_relation_edges,
        event_entity_edges,
        run_id=run_id,
        schema_version=schema_version,
    )
    text_nodes = build_text_nodes(
        structured_df,
        run_id=run_id,
        schema_version=schema_version,
    )
    text_edges = build_text_edges(
        all_edges,
        run_id=run_id,
        schema_version=schema_version,
    )
    missing_concepts = build_missing_concepts(
        triple_nodes,
        all_edges,
        run_id=run_id,
        schema_version=schema_version,
    )

    return {
        "entity_edges": entity_edges,
        "event_relation_edges": event_relation_edges,
        "event_entity_edges": event_entity_edges,
        "triple_edges": triple_edges,
        "triple_nodes": triple_nodes,
        "text_nodes": text_nodes,
        "text_edges": text_edges,
        "missing_concepts": missing_concepts,
    }


def collect_metrics(structured_df: DataFrame, tables: dict[str, DataFrame]) -> dict[str, Any]:
    triple_nodes = tables["triple_nodes"]
    triple_edges = tables["triple_edges"]
    text_nodes = tables["text_nodes"]
    text_edges = tables["text_edges"]
    missing_concepts = tables["missing_concepts"]

    duplicate_node_names = (
        triple_nodes.groupBy("node_name")
        .agg(F.countDistinct("node_type").alias("type_count"))
        .filter(F.col("type_count") > 1)
        .count()
    )
    orphan_text_edges = text_edges.join(text_nodes.select("text_id"), on="text_id", how="left_anti").count()
    orphan_edge_src = triple_edges.join(
        triple_nodes.select(F.col("node_name").alias("src")),
        on="src",
        how="left_anti",
    ).count()
    orphan_edge_dst = triple_edges.join(
        triple_nodes.select(F.col("node_name").alias("dst")),
        on="dst",
        how="left_anti",
    ).count()

    return {
        "structured_record_count": structured_df.count(),
        "entity_relation_edge_count": tables["entity_edges"].count(),
        "event_relation_edge_count": tables["event_relation_edges"].count(),
        "event_entity_edge_count": tables["event_entity_edges"].count(),
        "triple_edge_count": triple_edges.count(),
        "triple_node_count": triple_nodes.count(),
        "text_node_count": text_nodes.count(),
        "text_edge_count": text_edges.count(),
        "missing_concept_count": missing_concepts.count(),
        "duplicate_node_name_with_multiple_types": duplicate_node_names,
        "orphan_text_edge_count": orphan_text_edges,
        "orphan_triple_edge_src_count": orphan_edge_src,
        "orphan_triple_edge_dst_count": orphan_edge_dst,
        "triple_node_type_counts": {
            row["node_type"]: row["count"]
            for row in triple_nodes.groupBy("node_type").count().collect()
        },
        "missing_concept_type_counts": {
            row["node_type"]: row["count"]
            for row in missing_concepts.groupBy("node_type").count().collect()
        },
        "triple_edge_relation_counts": {
            row["relation"]: row["count"]
            for row in triple_edges.groupBy("relation").count().orderBy(F.desc("count")).limit(20).collect()
        },
    }


def write_table(
    df: DataFrame,
    *,
    bucket: str,
    base_path: str,
    run_id: str,
) -> str:
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
    source_run_id: str,
) -> str:
    output_uri = build_s3a_uri(
        bucket,
        build_run_path(f"{reports_base_path}/graph_base", run_id),
    )
    payload = {
        "run_id": run_id,
        "source_run_id": source_run_id,
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

    spark = SparkSession.builder.appName("phase2-07-build-graph-base").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    cached_tables: list[DataFrame] = []
    try:
        bucket = storage_cfg["bucket"]
        table_paths = storage_cfg["tables"]
        source_base_path = table_paths["silver.extraction_structured"]
        source_run_id = args.source_run_id or resolve_latest_run_id(
            spark,
            bucket,
            source_base_path,
        )

        structured_df = read_input(
            spark,
            bucket=bucket,
            extraction_structured_base_path=source_base_path,
            source_run_id=source_run_id,
        ).cache()
        cached_tables.append(structured_df)

        tables = build_graph_base_tables(
            structured_df,
            run_id=run_id,
            schema_version=schema_version,
        )
        for table_name in [
            "triple_edges",
            "triple_nodes",
            "text_nodes",
            "text_edges",
            "missing_concepts",
        ]:
            tables[table_name] = tables[table_name].cache()
            cached_tables.append(tables[table_name])

        output_paths = {
            "triple_nodes": write_table(
                tables["triple_nodes"],
                bucket=bucket,
                base_path=table_paths["silver.triple_nodes"],
                run_id=run_id,
            ),
            "triple_edges": write_table(
                tables["triple_edges"],
                bucket=bucket,
                base_path=table_paths["silver.triple_edges"],
                run_id=run_id,
            ),
            "text_nodes": write_table(
                tables["text_nodes"],
                bucket=bucket,
                base_path=table_paths["silver.text_nodes"],
                run_id=run_id,
            ),
            "text_edges": write_table(
                tables["text_edges"],
                bucket=bucket,
                base_path=table_paths["silver.text_edges"],
                run_id=run_id,
            ),
            "missing_concepts": write_table(
                tables["missing_concepts"],
                bucket=bucket,
                base_path=table_paths["silver.missing_concepts"],
                run_id=run_id,
            ),
        }
        metrics = collect_metrics(structured_df, tables)
        report_uri = write_report(
            spark,
            metrics,
            bucket=bucket,
            reports_base_path=table_paths["meta.quality_reports"],
            run_id=run_id,
            source_run_id=source_run_id,
        )

        if metrics["orphan_text_edge_count"] > 0:
            raise RuntimeError(
                f"Found orphan text_edges: {metrics['orphan_text_edge_count']}"
            )
        if metrics["orphan_triple_edge_src_count"] > 0 or metrics["orphan_triple_edge_dst_count"] > 0:
            raise RuntimeError(
                "Found triple_edges with missing endpoint nodes: "
                f"src={metrics['orphan_triple_edge_src_count']}, "
                f"dst={metrics['orphan_triple_edge_dst_count']}"
            )

        print(f"GRAPH_BASE_RUN_ID={run_id}")
        print(f"SOURCE_RUN_ID={source_run_id}")
        print(f"STRUCTURED_RECORD_COUNT={metrics['structured_record_count']}")
        print(f"ENTITY_RELATION_EDGE_COUNT={metrics['entity_relation_edge_count']}")
        print(f"EVENT_RELATION_EDGE_COUNT={metrics['event_relation_edge_count']}")
        print(f"EVENT_ENTITY_EDGE_COUNT={metrics['event_entity_edge_count']}")
        print(f"TRIPLE_EDGE_COUNT={metrics['triple_edge_count']}")
        print(f"TRIPLE_NODE_COUNT={metrics['triple_node_count']}")
        print(f"TEXT_NODE_COUNT={metrics['text_node_count']}")
        print(f"TEXT_EDGE_COUNT={metrics['text_edge_count']}")
        print(f"MISSING_CONCEPT_COUNT={metrics['missing_concept_count']}")
        print(
            "DUPLICATE_NODE_NAME_WITH_MULTIPLE_TYPES="
            f"{metrics['duplicate_node_name_with_multiple_types']}"
        )
        print(f"ORPHAN_TEXT_EDGE_COUNT={metrics['orphan_text_edge_count']}")
        print(f"ORPHAN_TRIPLE_EDGE_SRC_COUNT={metrics['orphan_triple_edge_src_count']}")
        print(f"ORPHAN_TRIPLE_EDGE_DST_COUNT={metrics['orphan_triple_edge_dst_count']}")
        for node_type, count in sorted(metrics["triple_node_type_counts"].items()):
            print(f"TRIPLE_NODE_TYPE_{node_type.upper()}={count}")
        for node_type, count in sorted(metrics["missing_concept_type_counts"].items()):
            print(f"MISSING_CONCEPT_TYPE_{node_type.upper()}={count}")
        for name, output_path in sorted(output_paths.items()):
            print(f"{name.upper()}_OUTPUT_PATH={output_path}")
        print(f"GRAPH_BASE_REPORT_PATH={report_uri}")
    finally:
        for df in cached_tables:
            df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
