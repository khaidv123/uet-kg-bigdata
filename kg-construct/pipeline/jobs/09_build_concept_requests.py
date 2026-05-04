#!/usr/bin/env python3
"""Build conceptualization requests from missing concepts and node context."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pyspark.sql import DataFrame, SparkSession, functions as F

from pipeline.common.config_loader import load_yaml
from pipeline.common.io import json_dumps
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


EXPECTED_NODE_TYPES = ["entity", "event", "relation"]


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(repo_root))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument("--graph-base-run-id", default=None)
    parser.add_argument("--node-context-run-id", default=None)
    return parser.parse_args()


def derive_run_id(explicit_run_id: Optional[str]) -> str:
    if explicit_run_id:
        return explicit_run_id
    return datetime.now(timezone.utc).strftime("conceptreq-%Y%m%d%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Top-level JSON document must be an object: {path}")
    return data


def load_configs(repo_root: Path) -> tuple[dict, dict, dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    llm_cfg = load_yaml(repo_root / "config/llm.yaml")
    prompt_registry = load_json(repo_root / "config/prompts/concept_vi.json")
    return pipeline_cfg, storage_cfg, llm_cfg, prompt_registry


def validate_prompt_registry(
    *,
    pipeline_cfg: dict,
    prompt_registry: dict,
) -> tuple[str, list[dict[str, str]]]:
    metadata = prompt_registry.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Concept prompt registry must contain metadata object")

    prompt_version = str(metadata.get("prompt_version") or "").strip()
    configured_prompt_version = str(pipeline_cfg["runtime"]["prompt_version"])
    if prompt_version != configured_prompt_version:
        raise ValueError(
            "Concept prompt version does not match pipeline config: "
            f"{prompt_version} != {configured_prompt_version}"
        )

    language = str(metadata.get("language") or "").strip()
    configured_language = str(pipeline_cfg["runtime"]["default_lang"])
    if language != configured_language:
        raise ValueError(
            "Concept prompt language does not match pipeline default language: "
            f"{language} != {configured_language}"
        )

    output_format = str(metadata.get("output_format") or "").strip()
    if output_format != "json_array":
        raise ValueError(f"Concept prompt output_format must be json_array, got {output_format}")

    stage_specs: list[dict[str, str]] = []
    for node_type in EXPECTED_NODE_TYPES:
        node_cfg = prompt_registry.get(node_type)
        if not isinstance(node_cfg, dict):
            raise ValueError(f"Missing concept prompt config for {node_type}")

        system_prompt = str(node_cfg.get("system_prompt") or "").strip()
        user_prompt_template = str(node_cfg.get("user_prompt_template") or "").strip()
        if not system_prompt:
            raise ValueError(f"Concept prompt {node_type} missing system_prompt")
        if not user_prompt_template:
            raise ValueError(f"Concept prompt {node_type} missing user_prompt_template")
        if "{{node_name}}" not in user_prompt_template:
            raise ValueError(f"Concept prompt {node_type} must contain {{node_name}}")
        if node_type == "entity" and "{{context_text}}" not in user_prompt_template:
            raise ValueError("Concept prompt entity must contain {{context_text}}")

        stage_specs.append(
            {
                "node_type": node_type,
                "system_prompt": system_prompt,
                "user_prompt_template": user_prompt_template,
                "prompt_version": prompt_version,
            }
        )

    return prompt_version, stage_specs


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


def build_concept_requests(
    spark: SparkSession,
    missing_concepts: DataFrame,
    node_context: DataFrame,
    *,
    run_id: str,
    stage_specs: list[dict[str, str]],
    model_name: str,
    context_version: str,
) -> DataFrame:
    prompt_df = spark.createDataFrame(stage_specs)
    missing = (
        missing_concepts.select(
            F.trim(F.col("name")).alias("node_name"),
            F.lower(F.trim(F.col("node_type"))).alias("node_type"),
        )
        .filter(_non_empty("node_name") & F.col("node_type").isin(EXPECTED_NODE_TYPES))
        .dropDuplicates(["node_name", "node_type"])
    )
    context = node_context.select(
        F.trim(F.col("node_name")).alias("node_name"),
        F.lower(F.trim(F.col("node_type"))).alias("node_type"),
        F.col("context_text").cast("string").alias("context_text"),
    ).dropDuplicates(["node_name", "node_type"])

    with_prompt = (
        missing.join(F.broadcast(prompt_df), on="node_type", how="inner")
        .join(context, on=["node_name", "node_type"], how="left")
        .withColumn(
            "context_text",
            F.when(F.col("node_type") == "relation", F.lit(None).cast("string")).otherwise(
                F.coalesce(F.col("context_text"), F.lit(""))
            ),
        )
        .withColumn(
            "prompt_text",
            F.replace(
                F.replace(
                    F.col("user_prompt_template"),
                    F.lit("{{node_name}}"),
                    F.col("node_name"),
                ),
                F.lit("{{context_text}}"),
                F.coalesce(F.col("context_text"), F.lit("")),
            ),
        )
        .withColumn("context_version", F.lit(context_version))
        .withColumn("model_name", F.lit(model_name))
        .withColumn(
            "concept_request_id",
            F.sha2(
                F.concat_ws(
                    "||",
                    F.col("node_name"),
                    F.col("node_type"),
                    F.col("prompt_version"),
                    F.col("model_name"),
                    F.col("context_version"),
                ),
                256,
            ),
        )
        .withColumn("run_id", F.lit(run_id))
    )

    return with_prompt.select(
        "concept_request_id",
        "node_name",
        "node_type",
        "context_text",
        "prompt_text",
        "prompt_version",
        "context_version",
        "model_name",
        "run_id",
    )


def collect_metrics(
    missing_concepts: DataFrame,
    node_context: DataFrame,
    concept_requests: DataFrame,
) -> dict[str, Any]:
    input_missing_count = missing_concepts.select("name", "node_type").dropDuplicates().count()
    output_count = concept_requests.count()
    distinct_request_count = concept_requests.select("concept_request_id").distinct().count()
    duplicate_request_count = output_count - distinct_request_count
    entity_event_requests = concept_requests.filter(F.col("node_type").isin(["entity", "event"]))
    entity_event_without_context = entity_event_requests.filter(~_non_empty("context_text")).count()
    relation_with_context = concept_requests.filter(
        (F.col("node_type") == "relation") & _non_empty("context_text")
    ).count()

    return {
        "input_missing_concept_count": input_missing_count,
        "input_node_context_count": node_context.count(),
        "output_concept_request_count": output_count,
        "distinct_concept_request_count": distinct_request_count,
        "duplicate_concept_request_count": duplicate_request_count,
        "entity_event_without_context_count": entity_event_without_context,
        "relation_with_context_count": relation_with_context,
        "request_type_counts": {
            row["node_type"]: row["count"]
            for row in concept_requests.groupBy("node_type").count().collect()
        },
        "avg_prompt_length": (
            concept_requests.agg(F.avg(F.length("prompt_text")).alias("avg_prompt_length"))
            .collect()[0]["avg_prompt_length"]
            or 0.0
        ),
        "max_prompt_length": (
            concept_requests.agg(F.max(F.length("prompt_text")).alias("max_prompt_length"))
            .collect()[0]["max_prompt_length"]
            or 0
        ),
    }


def write_output(
    concept_requests: DataFrame,
    *,
    bucket: str,
    concept_requests_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(concept_requests_base_path, run_id))
    concept_requests.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def write_report(
    spark: SparkSession,
    metrics: dict[str, Any],
    *,
    bucket: str,
    reports_base_path: str,
    run_id: str,
    graph_base_run_id: str,
    node_context_run_id: str,
    prompt_version: str,
    model_name: str,
    context_version: str,
) -> str:
    output_uri = build_s3a_uri(
        bucket,
        build_run_path(f"{reports_base_path}/concept_requests", run_id),
    )
    payload = {
        "run_id": run_id,
        "graph_base_run_id": graph_base_run_id,
        "node_context_run_id": node_context_run_id,
        "prompt_version": prompt_version,
        "model_name": model_name,
        "context_version": context_version,
        "created_ts": datetime.now(timezone.utc).isoformat(),
        "metrics_json": json_dumps(metrics),
    }
    spark.createDataFrame([payload]).coalesce(1).write.mode("overwrite").json(output_uri)
    return output_uri


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    pipeline_cfg, storage_cfg, llm_cfg, prompt_registry = load_configs(repo_root)
    run_id = derive_run_id(args.run_id)
    context_version = str(pipeline_cfg["runtime"]["context_version"])
    model_name = str(llm_cfg["generation"]["model"])
    prompt_version, stage_specs = validate_prompt_registry(
        pipeline_cfg=pipeline_cfg,
        prompt_registry=prompt_registry,
    )

    spark = SparkSession.builder.appName("phase2-09-build-concept-requests").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    cached: list[DataFrame] = []
    try:
        bucket = storage_cfg["bucket"]
        table_paths = storage_cfg["tables"]
        graph_base_run_id = (
            args.graph_base_run_id
            or args.source_run_id
            or resolve_latest_run_id(spark, bucket, table_paths["silver.missing_concepts"])
        )
        node_context_run_id = args.node_context_run_id or resolve_latest_run_id(
            spark,
            bucket,
            table_paths["silver.node_context"],
        )

        missing_concepts = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.missing_concepts"],
            run_id=graph_base_run_id,
        ).cache()
        node_context = read_table(
            spark,
            bucket=bucket,
            base_path=table_paths["silver.node_context"],
            run_id=node_context_run_id,
        ).cache()
        cached.extend([missing_concepts, node_context])

        concept_requests = build_concept_requests(
            spark,
            missing_concepts,
            node_context,
            run_id=run_id,
            stage_specs=stage_specs,
            model_name=model_name,
            context_version=context_version,
        ).cache()
        cached.append(concept_requests)

        output_uri = write_output(
            concept_requests,
            bucket=bucket,
            concept_requests_base_path=table_paths["silver.concept_requests"],
            run_id=run_id,
        )
        metrics = collect_metrics(missing_concepts, node_context, concept_requests)
        report_uri = write_report(
            spark,
            metrics,
            bucket=bucket,
            reports_base_path=table_paths["meta.quality_reports"],
            run_id=run_id,
            graph_base_run_id=graph_base_run_id,
            node_context_run_id=node_context_run_id,
            prompt_version=prompt_version,
            model_name=model_name,
            context_version=context_version,
        )

        if metrics["duplicate_concept_request_count"] != 0:
            raise RuntimeError(
                "Duplicate concept_request_id detected: "
                f"{metrics['duplicate_concept_request_count']}"
            )
        if metrics["relation_with_context_count"] != 0:
            raise RuntimeError(
                "Relation concept requests should not carry context_text: "
                f"{metrics['relation_with_context_count']}"
            )

        print(f"CONCEPT_REQUEST_RUN_ID={run_id}")
        print(f"GRAPH_BASE_RUN_ID={graph_base_run_id}")
        print(f"NODE_CONTEXT_RUN_ID={node_context_run_id}")
        print(f"PROMPT_VERSION={prompt_version}")
        print(f"MODEL_NAME={model_name}")
        print(f"CONTEXT_VERSION={context_version}")
        print(f"INPUT_MISSING_CONCEPT_COUNT={metrics['input_missing_concept_count']}")
        print(f"INPUT_NODE_CONTEXT_COUNT={metrics['input_node_context_count']}")
        print(f"OUTPUT_CONCEPT_REQUEST_COUNT={metrics['output_concept_request_count']}")
        print(f"DISTINCT_CONCEPT_REQUEST_COUNT={metrics['distinct_concept_request_count']}")
        print(f"DUPLICATE_CONCEPT_REQUEST_COUNT={metrics['duplicate_concept_request_count']}")
        print(f"ENTITY_EVENT_WITHOUT_CONTEXT_COUNT={metrics['entity_event_without_context_count']}")
        print(f"RELATION_WITH_CONTEXT_COUNT={metrics['relation_with_context_count']}")
        print(f"AVG_PROMPT_LENGTH={metrics['avg_prompt_length']}")
        print(f"MAX_PROMPT_LENGTH={metrics['max_prompt_length']}")
        for node_type, count in sorted(metrics["request_type_counts"].items()):
            print(f"REQUEST_TYPE_{node_type.upper()}={count}")
        print(f"CONCEPT_REQUEST_OUTPUT_PATH={output_uri}")
        print(f"CONCEPT_REQUEST_REPORT_PATH={report_uri}")
    finally:
        for df in cached:
            df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
