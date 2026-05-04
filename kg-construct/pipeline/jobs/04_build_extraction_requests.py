#!/usr/bin/env python3
"""Build stage-specific extraction requests from document chunks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pyspark.sql import DataFrame, SparkSession, functions as F

from pipeline.common.config_loader import load_yaml
from pipeline.common.pathing import build_run_path, build_s3a_uri, resolve_latest_run_id


EXPECTED_STAGES = [
    "entity_relation",
    "event_entity",
    "event_relation",
]


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
    return datetime.now(timezone.utc).strftime("extractreq-%Y%m%d%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Top-level JSON document must be an object: {path}")
    return data


def load_configs(repo_root: Path) -> tuple[dict, dict, dict, dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    llm_cfg = load_yaml(repo_root / "config/llm.yaml")
    prompt_registry = load_json(repo_root / "config/prompts/extraction_vi.json")
    extraction_schema = load_json(repo_root / "config/schema/extraction_schema.json")
    return pipeline_cfg, storage_cfg, llm_cfg, prompt_registry, extraction_schema


def validate_prompt_registry(
    *,
    repo_root: Path,
    pipeline_cfg: dict,
    prompt_registry: dict,
    extraction_schema: dict,
) -> tuple[str, list[dict[str, str]]]:
    metadata = prompt_registry.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Prompt registry must contain metadata object")

    prompt_version = str(metadata.get("prompt_version") or "").strip()
    if not prompt_version:
        raise ValueError("Prompt registry metadata.prompt_version is required")

    configured_prompt_version = str(pipeline_cfg["runtime"]["prompt_version"])
    if prompt_version != configured_prompt_version:
        raise ValueError(
            "Prompt registry version does not match pipeline config: "
            f"{prompt_version} != {configured_prompt_version}"
        )

    stage_order = metadata.get("stage_order") or EXPECTED_STAGES
    if list(stage_order) != EXPECTED_STAGES:
        raise ValueError(f"Unexpected extraction stage order: {stage_order}")

    registry_language = str(metadata.get("language") or "").strip()
    configured_language = str(pipeline_cfg["runtime"]["default_lang"])
    if registry_language != configured_language:
        raise ValueError(
            "Prompt registry language does not match pipeline default language: "
            f"{registry_language} != {configured_language}"
        )

    definitions = extraction_schema.get("definitions")
    if not isinstance(definitions, dict):
        raise ValueError("Extraction schema must contain definitions object")

    stage_specs: list[dict[str, str]] = []
    for stage in EXPECTED_STAGES:
        stage_cfg = prompt_registry.get(stage)
        if not isinstance(stage_cfg, dict):
            raise ValueError(f"Missing stage config for {stage}")

        system_prompt = str(stage_cfg.get("system_prompt") or "").strip()
        user_prompt_template = str(stage_cfg.get("user_prompt_template") or "").strip()
        validator_type = str(stage_cfg.get("validator_type") or "").strip()
        output_schema_ref = str(stage_cfg.get("output_schema_ref") or "").strip()

        if not system_prompt:
            raise ValueError(f"Stage {stage} is missing system_prompt")
        if not user_prompt_template:
            raise ValueError(f"Stage {stage} is missing user_prompt_template")
        if "{{chunk_text}}" not in user_prompt_template:
            raise ValueError(f"Stage {stage} user_prompt_template must contain {{chunk_text}}")
        if validator_type != "json_schema":
            raise ValueError(f"Stage {stage} must use validator_type=json_schema")
        if not output_schema_ref.startswith("config/schema/extraction_schema.json#/definitions/"):
            raise ValueError(f"Stage {stage} has unsupported output_schema_ref={output_schema_ref}")

        schema_path_part, definition_fragment = output_schema_ref.split("#", 1)
        schema_path = (repo_root / schema_path_part).resolve()
        expected_schema_path = (repo_root / "config/schema/extraction_schema.json").resolve()
        if schema_path != expected_schema_path:
            raise ValueError(f"Stage {stage} points to unexpected schema path: {schema_path_part}")
        if not definition_fragment.startswith("/definitions/"):
            raise ValueError(f"Stage {stage} has unsupported schema fragment: {definition_fragment}")
        definition_name = definition_fragment.split("/definitions/", 1)[1]
        if definition_name not in definitions:
            raise ValueError(f"Schema definition not found for stage {stage}: {definition_name}")

        stage_specs.append(
            {
                "stage": stage,
                "system_prompt": system_prompt,
                "user_prompt_template": user_prompt_template,
                "prompt_version": prompt_version,
                "validator_type": validator_type,
                "output_schema_ref": output_schema_ref,
            }
        )

    return prompt_version, stage_specs


def read_input(
    spark: SparkSession,
    *,
    bucket: str,
    chunk_base_path: str,
    source_run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(bucket, build_run_path(chunk_base_path, source_run_id))
    return spark.read.parquet(input_uri)


def build_requests(
    spark: SparkSession,
    chunk_df: DataFrame,
    *,
    run_id: str,
    stage_specs: list[dict[str, str]],
    model_name: str,
) -> tuple[DataFrame, dict[str, Any]]:
    stage_df = spark.createDataFrame(stage_specs)
    requests = (
        chunk_df.select(
            F.col("doc_id").cast("string").alias("doc_id"),
            F.col("chunk_id").cast("int").alias("chunk_id"),
            F.col("chunk_text").cast("string").alias("chunk_text"),
            F.col("lang").cast("string").alias("lang"),
        )
        .crossJoin(F.broadcast(stage_df))
        .withColumn(
            "user_prompt",
            F.expr("replace(user_prompt_template, '{{chunk_text}}', chunk_text)"),
        )
        .withColumn("model_name", F.lit(model_name))
        .withColumn(
            "request_id",
            F.sha2(
                F.concat_ws(
                    "||",
                    F.col("doc_id"),
                    F.col("chunk_id").cast("string"),
                    F.col("stage"),
                    F.col("prompt_version"),
                    F.col("model_name"),
                ),
                256,
            ),
        )
        .withColumn("run_id", F.lit(run_id))
        .select(
            "request_id",
            "doc_id",
            "chunk_id",
            "chunk_text",
            "lang",
            "stage",
            "system_prompt",
            "user_prompt",
            "prompt_version",
            "model_name",
            "run_id",
        )
    )
    requests = requests.cache()

    input_chunk_count = chunk_df.count()
    stage_count = len(stage_specs)
    output_request_count = requests.count()
    expected_request_count = input_chunk_count * stage_count
    if output_request_count != expected_request_count:
        raise RuntimeError(
            "Extraction request count mismatch: "
            f"expected={expected_request_count}, actual={output_request_count}"
        )

    distinct_request_count = requests.select("request_id").distinct().count()
    if distinct_request_count != output_request_count:
        raise RuntimeError(
            "Extraction request_id collision detected: "
            f"distinct={distinct_request_count}, total={output_request_count}"
        )

    stage_counts = {
        row["stage"]: row["count"]
        for row in requests.groupBy("stage").count().collect()
    }
    for stage in EXPECTED_STAGES:
        if stage_counts.get(stage) != input_chunk_count:
            raise RuntimeError(
                f"Stage {stage} request count mismatch: "
                f"expected={input_chunk_count}, actual={stage_counts.get(stage)}"
            )

    metrics = {
        "input_chunk_count": input_chunk_count,
        "stage_count": stage_count,
        "expected_request_count": expected_request_count,
        "output_request_count": output_request_count,
        "distinct_request_count": distinct_request_count,
        "stage_counts": stage_counts,
    }
    return requests, metrics


def write_output(
    request_df: DataFrame,
    *,
    bucket: str,
    extraction_request_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(
        bucket,
        build_run_path(extraction_request_base_path, run_id),
    )
    request_df.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    pipeline_cfg, storage_cfg, llm_cfg, prompt_registry, extraction_schema = load_configs(
        repo_root
    )
    run_id = derive_run_id(args.run_id)

    model_name = str(llm_cfg["generation"]["model"])
    prompt_version, stage_specs = validate_prompt_registry(
        repo_root=repo_root,
        pipeline_cfg=pipeline_cfg,
        prompt_registry=prompt_registry,
        extraction_schema=extraction_schema,
    )

    spark = SparkSession.builder.appName("phase2-04-build-extraction-requests").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    request_df: Optional[DataFrame] = None
    try:
        bucket = storage_cfg["bucket"]
        chunk_base_path = storage_cfg["tables"]["silver.document_chunks"]
        extraction_request_base_path = storage_cfg["tables"]["silver.extraction_requests"]
        source_run_id = args.source_run_id or resolve_latest_run_id(
            spark, bucket, chunk_base_path
        )

        chunk_df = read_input(
            spark,
            bucket=bucket,
            chunk_base_path=chunk_base_path,
            source_run_id=source_run_id,
        )
        request_df, metrics = build_requests(
            spark,
            chunk_df,
            run_id=run_id,
            stage_specs=stage_specs,
            model_name=model_name,
        )
        output_uri = write_output(
            request_df,
            bucket=bucket,
            extraction_request_base_path=extraction_request_base_path,
            run_id=run_id,
        )

        print(f"EXTRACTION_REQUEST_RUN_ID={run_id}")
        print(f"SOURCE_RUN_ID={source_run_id}")
        print(f"PROMPT_VERSION={prompt_version}")
        print(f"MODEL_NAME={model_name}")
        print(f"INPUT_CHUNK_COUNT={metrics['input_chunk_count']}")
        print(f"STAGE_COUNT={metrics['stage_count']}")
        print(f"EXPECTED_REQUEST_COUNT={metrics['expected_request_count']}")
        print(f"OUTPUT_REQUEST_COUNT={metrics['output_request_count']}")
        print(f"DISTINCT_REQUEST_COUNT={metrics['distinct_request_count']}")
        for stage in EXPECTED_STAGES:
            print(f"{stage.upper()}_REQUEST_COUNT={metrics['stage_counts'][stage]}")
        print(f"EXTRACTION_REQUEST_OUTPUT_PATH={output_uri}")
    finally:
        if request_df is not None:
            request_df.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
