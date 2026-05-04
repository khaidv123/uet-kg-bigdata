#!/usr/bin/env python3
"""Chunk clean documents into chunk-level records."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pyspark.sql import DataFrame, SparkSession, functions as F, types as T

from pipeline.common.config_loader import load_yaml
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
    return datetime.now(timezone.utc).strftime("chunk-%Y%m%d%H%M%S")


def load_configs(repo_root: Path) -> tuple[dict, dict]:
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    storage_cfg = load_yaml(repo_root / "config/storage.yaml")
    return pipeline_cfg, storage_cfg


def split_text_to_chunks(
    text: Optional[str],
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_length: int,
    max_chunk_per_doc: int,
) -> List[str]:
    if text is None:
        return []

    normalized = " ".join(text.split())
    if not normalized:
        return []

    words = normalized.split(" ")
    chunks: List[str] = []
    current_words: List[str] = []
    current_length = 0

    def flush_chunk() -> None:
        nonlocal current_words, current_length, chunks
        if not current_words:
            return
        chunk_text = " ".join(current_words).strip()
        if chunk_text:
            chunks.append(chunk_text)

        overlap_words: List[str] = []
        overlap_length = 0
        if chunk_overlap > 0:
            for word in reversed(current_words):
                word_len = len(word) + (1 if overlap_words else 0)
                if overlap_length + word_len > chunk_overlap and overlap_words:
                    break
                if overlap_length + len(word) > chunk_overlap and not overlap_words:
                    break
                overlap_words.insert(0, word)
                overlap_length = len(" ".join(overlap_words))

        current_words = overlap_words
        current_length = len(" ".join(current_words)) if current_words else 0

    for word in words:
        if not word:
            continue

        if len(word) > chunk_size:
            if current_words:
                flush_chunk()
            slices = [word[i : i + chunk_size] for i in range(0, len(word), chunk_size)]
            for slice_idx, slice_text in enumerate(slices):
                if len(slice_text) >= min_chunk_length or len(slices) == 1:
                    chunks.append(slice_text)
            current_words = []
            current_length = 0
            continue

        proposed_length = len(word) if not current_words else current_length + 1 + len(word)
        if proposed_length > chunk_size and current_words:
            flush_chunk()
            proposed_length = len(word) if not current_words else current_length + 1 + len(word)

        current_words.append(word)
        current_length = proposed_length

    if current_words:
        chunk_text = " ".join(current_words).strip()
        if chunk_text:
            chunks.append(chunk_text)

    filtered = [chunk for chunk in chunks if len(chunk) >= min_chunk_length]
    if not filtered and chunks:
        filtered = [max(chunks, key=len)]
    return filtered[:max_chunk_per_doc]


def read_input(
    spark: SparkSession,
    *,
    bucket: str,
    clean_base_path: str,
    source_run_id: str,
) -> DataFrame:
    input_uri = build_s3a_uri(bucket, build_run_path(clean_base_path, source_run_id))
    return spark.read.parquet(input_uri)


def build_chunk_df(
    df: DataFrame,
    *,
    run_id: str,
    chunk_cfg: dict,
) -> tuple[DataFrame, dict]:
    split_udf = F.udf(
        lambda text: split_text_to_chunks(
            text=text,
            chunk_size=int(chunk_cfg["chunk_size"]),
            chunk_overlap=int(chunk_cfg["chunk_overlap"]),
            min_chunk_length=int(chunk_cfg["min_chunk_length"]),
            max_chunk_per_doc=int(chunk_cfg["max_chunk_per_doc"]),
        ),
        T.ArrayType(T.StringType()),
    )

    chunked = (
        df.withColumn("chunks", split_udf(F.col("text")))
        .select(
            F.col("doc_id"),
            F.col("lang"),
            F.col("metadata"),
            F.col("source_file"),
            F.posexplode("chunks").alias("chunk_id", "chunk_text"),
        )
        .withColumn("chunk_hash", F.sha2(F.col("chunk_text"), 256))
        .withColumn("run_id", F.lit(run_id))
    )

    per_doc_stats = chunked.groupBy("doc_id").agg(
        F.count("*").alias("chunks_per_doc"),
        F.avg(F.length("chunk_text")).alias("avg_chunk_length_per_doc"),
    )

    metrics_row = (
        per_doc_stats.agg(
            F.count("*").alias("input_docs_with_chunks"),
            F.sum("chunks_per_doc").alias("output_chunk_count"),
            F.avg("chunks_per_doc").alias("avg_chunks_per_doc"),
            F.max("chunks_per_doc").alias("max_chunks_per_doc"),
            F.avg("avg_chunk_length_per_doc").alias("avg_chunk_length"),
        )
        .collect()[0]
        .asDict()
    )

    metrics_row["input_document_count"] = df.count()
    docs_without_chunks = metrics_row["input_document_count"] - metrics_row["input_docs_with_chunks"]
    metrics_row["docs_without_chunks"] = docs_without_chunks
    return chunked, metrics_row


def write_output(
    chunk_df: DataFrame,
    *,
    bucket: str,
    chunk_base_path: str,
    run_id: str,
) -> str:
    output_uri = build_s3a_uri(bucket, build_run_path(chunk_base_path, run_id))
    chunk_df.write.mode("overwrite").format("parquet").save(output_uri)
    return output_uri


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    pipeline_cfg, storage_cfg = load_configs(repo_root)
    run_id = derive_run_id(args.run_id)

    spark = SparkSession.builder.appName("phase2-03-chunk-documents").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try:
        bucket = storage_cfg["bucket"]
        clean_base_path = storage_cfg["tables"]["silver.documents_clean"]
        chunk_base_path = storage_cfg["tables"]["silver.document_chunks"]
        source_run_id = args.source_run_id or resolve_latest_run_id(
            spark, bucket, clean_base_path
        )

        input_df = read_input(
            spark,
            bucket=bucket,
            clean_base_path=clean_base_path,
            source_run_id=source_run_id,
        )
        chunk_df, metrics = build_chunk_df(
            input_df,
            run_id=run_id,
            chunk_cfg=pipeline_cfg["chunking"],
        )
        output_uri = write_output(
            chunk_df,
            bucket=bucket,
            chunk_base_path=chunk_base_path,
            run_id=run_id,
        )

        print(f"CHUNK_RUN_ID={run_id}")
        print(f"SOURCE_RUN_ID={source_run_id}")
        print(f"INPUT_DOCUMENT_COUNT={metrics['input_document_count']}")
        print(f"OUTPUT_CHUNK_COUNT={metrics['output_chunk_count']}")
        print(f"DOCS_WITHOUT_CHUNKS={metrics['docs_without_chunks']}")
        print(f"AVG_CHUNKS_PER_DOC={metrics['avg_chunks_per_doc']}")
        print(f"MAX_CHUNKS_PER_DOC={metrics['max_chunks_per_doc']}")
        print(f"AVG_CHUNK_LENGTH={metrics['avg_chunk_length']}")
        print(f"CHUNK_OUTPUT_PATH={output_uri}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
