#!/usr/bin/env python3
"""Import LightRAG chunk/entity embeddings into Elasticsearch vector indexes."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import zlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


SEP = "<SEP>"
DEFAULT_CHUNKS_INDEX = "uet_kg_chunks"
DEFAULT_ENTITIES_INDEX = "uet_kg_entities"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def split_sep(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [part for part in str(value).split(SEP) if part]


def decode_vector(value: str) -> list[float]:
    raw = zlib.decompress(base64.b64decode(value))
    return np.frombuffer(raw, dtype=np.float16).astype(np.float32).tolist()


def clean_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in doc.items() if value is not None}


def get_client(args: argparse.Namespace) -> Elasticsearch:
    es_url = args.es_url or os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    kwargs: dict[str, Any] = {}
    api_key = args.es_api_key or os.getenv("ELASTICSEARCH_API_KEY")
    user = args.es_user or os.getenv("ELASTICSEARCH_USER")
    password = args.es_password or os.getenv("ELASTICSEARCH_PASSWORD")
    ca_certs = args.es_ca_certs or os.getenv("ELASTICSEARCH_CA_CERTS")
    if api_key:
        kwargs["api_key"] = api_key
    elif user and password:
        kwargs["basic_auth"] = (user, password)
    if ca_certs:
        kwargs["ca_certs"] = ca_certs
    return Elasticsearch(es_url, **kwargs)


def vector_mapping(vector_dim: int, text_field: str) -> dict[str, Any]:
    return {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            "storage_layer": {"type": "keyword"},
            "record_type": {"type": "keyword"},
            "file_path": {"type": "keyword"},
            "file_paths": {"type": "keyword"},
            "full_doc_id": {"type": "keyword"},
            text_field: {"type": "text"},
            "embedding": {
                "type": "dense_vector",
                "dims": vector_dim,
                "index": True,
                "similarity": "cosine",
            },
        },
    }


def ensure_index(es: Elasticsearch, index: str, mapping: dict[str, Any], reset: bool) -> None:
    exists = bool(es.indices.exists(index=index))
    if reset and exists:
        es.indices.delete(index=index)
        exists = False
    if not exists:
        es.indices.create(
            index=index,
            settings={"number_of_shards": 1, "number_of_replicas": 0},
            mappings=mapping,
        )


def chunk_actions(data_dir: Path, index: str) -> Iterator[dict[str, Any]]:
    chunks = load_json(data_dir / "kv_store_text_chunks.json")
    vdb_chunks = load_json(data_dir / "vdb_chunks.json")
    for record in vdb_chunks.get("data", []):
        chunk_id = record.get("__id__")
        if not chunk_id or not record.get("vector"):
            continue
        chunk = chunks.get(chunk_id, {})
        source = clean_doc(
            {
                "id": chunk_id,
                "storage_layer": "vector_db",
                "record_type": "chunk",
                "content": chunk.get("content") or record.get("content"),
                "tokens": chunk.get("tokens"),
                "chunk_order_index": chunk.get("chunk_order_index"),
                "full_doc_id": chunk.get("full_doc_id"),
                "file_path": chunk.get("file_path"),
                "created_at": chunk.get("create_time") or record.get("__created_at__"),
                "updated_at": chunk.get("update_time"),
                "embedding": decode_vector(record["vector"]),
            }
        )
        yield {"_index": index, "_id": chunk_id, "_source": source}


def entity_actions(data_dir: Path, index: str) -> Iterator[dict[str, Any]]:
    vdb_entities = load_json(data_dir / "vdb_entities.json")
    for record in vdb_entities.get("data", []):
        entity_id = record.get("entity_name") or record.get("__id__")
        if not entity_id or not record.get("vector"):
            continue
        source = clean_doc(
            {
                "id": entity_id,
                "storage_layer": "vector_db",
                "record_type": "entity",
                "name": entity_id,
                "description": record.get("content"),
                "source_ids": split_sep(record.get("source_id")),
                "file_paths": split_sep(record.get("file_path")),
                "created_at": record.get("__created_at__"),
                "embedding": decode_vector(record["vector"]),
            }
        )
        yield {"_index": index, "_id": entity_id, "_source": source}


def index_actions(es: Elasticsearch, actions: Iterator[dict[str, Any]], batch_size: int) -> tuple[int, int]:
    success, errors = bulk(es, actions, chunk_size=batch_size, stats_only=True, request_timeout=120)
    return int(success), int(errors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="output_verson1_uet_kg_bigdata/rag_storage")
    parser.add_argument("--es-url", default=None)
    parser.add_argument("--es-user", default=None)
    parser.add_argument("--es-password", default=None)
    parser.add_argument("--es-api-key", default=None)
    parser.add_argument("--es-ca-certs", default=None)
    parser.add_argument("--chunks-index", default=os.getenv("ES_CHUNKS_INDEX", DEFAULT_CHUNKS_INDEX))
    parser.add_argument("--entities-index", default=os.getenv("ES_ENTITIES_INDEX", DEFAULT_ENTITIES_INDEX))
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--reset", action="store_true", help="Delete and recreate target indexes first.")
    parser.add_argument("--skip-entities", action="store_true", help="Only index chunk vectors.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize without writing Elasticsearch.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"Data dir not found: {data_dir}")

    vdb_chunks = load_json(data_dir / "vdb_chunks.json")
    vdb_entities = load_json(data_dir / "vdb_entities.json")
    chunk_dim = int(vdb_chunks.get("embedding_dim") or 0)
    entity_dim = int(vdb_entities.get("embedding_dim") or chunk_dim)
    print("Elasticsearch vector import summary")
    print(f"- chunks: {len(vdb_chunks.get('data', []))}, dim={chunk_dim}, index={args.chunks_index}")
    print(f"- entities: {len(vdb_entities.get('data', []))}, dim={entity_dim}, index={args.entities_index}")
    if args.dry_run:
        return 0

    es = get_client(args)
    es.info()
    ensure_index(es, args.chunks_index, vector_mapping(chunk_dim, "content"), args.reset)
    chunk_success, chunk_errors = index_actions(es, chunk_actions(data_dir, args.chunks_index), args.batch_size)
    print(f"Indexed chunks: success={chunk_success}, errors={chunk_errors}")

    if not args.skip_entities:
        ensure_index(es, args.entities_index, vector_mapping(entity_dim, "description"), args.reset)
        entity_success, entity_errors = index_actions(
            es,
            entity_actions(data_dir, args.entities_index),
            args.batch_size,
        )
        print(f"Indexed entities: success={entity_success}, errors={entity_errors}")

    print("Elasticsearch import complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
