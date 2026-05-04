#!/usr/bin/env python3
"""Import LightRAG JSON/GraphML artifacts into Neo4j."""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from collections.abc import Iterator
from typing import Any

import numpy as np
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


SEP = "<SEP>"
GRAPHML_NS = {"g": "http://graphml.graphdrawing.org/xmlns"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def split_sep(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x not in (None, "")]
    return [part for part in str(value).split(SEP) if part]


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ascii_fold(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").casefold()


def decode_vector(value: str) -> list[float]:
    raw = zlib.decompress(base64.b64decode(value))
    return np.frombuffer(raw, dtype=np.float16).astype(np.float32).tolist()


def clean_props(props: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in props.items():
        if value is None or isinstance(value, dict):
            continue
        cleaned[key] = value
    return cleaned


def parse_graphml(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    root = ET.parse(path).getroot()
    key_map = {
        key.attrib["id"]: key.attrib.get("attr.name", key.attrib["id"])
        for key in root.findall("g:key", GRAPHML_NS)
    }
    graph = root.find("g:graph", GRAPHML_NS)
    if graph is None:
        raise ValueError(f"No <graph> element found in {path}")

    nodes: dict[str, dict[str, Any]] = {}
    for node in graph.findall("g:node", GRAPHML_NS):
        props = {
            key_map.get(data.attrib.get("key", ""), data.attrib.get("key", "")): data.text or ""
            for data in node.findall("g:data", GRAPHML_NS)
        }
        entity_id = props.get("entity_id") or node.attrib["id"]
        nodes[entity_id] = {
            "id": entity_id,
            "name": entity_id,
            "name_lc": entity_id.casefold(),
            "name_ascii": ascii_fold(entity_id),
            "entity_type": props.get("entity_type"),
            "description": props.get("description"),
            "source_ids": split_sep(props.get("source_id")),
            "file_paths": split_sep(props.get("file_path")),
            "created_at": to_int(props.get("created_at")),
        }

    edges: list[dict[str, Any]] = []
    for edge in graph.findall("g:edge", GRAPHML_NS):
        props = {
            key_map.get(data.attrib.get("key", ""), data.attrib.get("key", "")): data.text or ""
            for data in edge.findall("g:data", GRAPHML_NS)
        }
        src_id = edge.attrib["source"]
        tgt_id = edge.attrib["target"]
        keywords_text = props.get("keywords") or ""
        pair_id = f"{src_id}{SEP}{tgt_id}"
        edges.append(
            {
                "pair_id": pair_id,
                "src_id": src_id,
                "tgt_id": tgt_id,
                "weight": to_float(props.get("weight")),
                "description": props.get("description"),
                "keywords": [x.strip() for x in keywords_text.split(",") if x.strip()],
                "keywords_text": keywords_text,
                "source_ids": split_sep(props.get("source_id")),
                "file_paths": split_sep(props.get("file_path")),
                "created_at": to_int(props.get("created_at")),
            }
        )
    return nodes, edges


def build_indexes(driver: Any, database: str, vector_dim: int, with_vectors: bool) -> None:
    statements = [
        "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
        "CREATE INDEX chunk_full_doc_id IF NOT EXISTS FOR (c:Chunk) ON (c.full_doc_id)",
        "CREATE INDEX entity_name_lc IF NOT EXISTS FOR (e:Entity) ON (e.name_lc)",
        "CREATE INDEX entity_name_ascii IF NOT EXISTS FOR (e:Entity) ON (e.name_ascii)",
        "CREATE INDEX relates_pair IF NOT EXISTS FOR ()-[r:RELATES_TO]-() ON (r.pair_id)",
        (
            "CREATE FULLTEXT INDEX document_text IF NOT EXISTS "
            "FOR (d:Document) ON EACH [d.content, d.file_path]"
        ),
        (
            "CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS "
            "FOR (c:Chunk) ON EACH [c.content, c.file_path, c.full_doc_id]"
        ),
        (
            "CREATE FULLTEXT INDEX entity_text IF NOT EXISTS "
            "FOR (e:Entity) ON EACH [e.name, e.name_lc, e.name_ascii, e.description, e.entity_type]"
        ),
        (
            "CREATE FULLTEXT INDEX relation_text IF NOT EXISTS "
            "FOR ()-[r:RELATES_TO]-() ON EACH [r.description, r.keywords_text]"
        ),
    ]
    if with_vectors:
        statements.extend(
            [
                (
                    "CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS "
                    "FOR (c:Chunk) ON (c.embedding) "
                    f"OPTIONS {{indexConfig: {{`vector.dimensions`: {vector_dim}, "
                    f"`vector.similarity_function`: 'cosine'}}}}"
                ),
                (
                    "CREATE VECTOR INDEX entity_embedding IF NOT EXISTS "
                    "FOR (e:Entity) ON (e.embedding) "
                    f"OPTIONS {{indexConfig: {{`vector.dimensions`: {vector_dim}, "
                    f"`vector.similarity_function`: 'cosine'}}}}"
                ),
            ]
        )

    with driver.session(database=database) as session:
        for statement in statements:
            try:
                session.run(statement).consume()
            except Neo4jError as exc:
                print(f"WARN: could not create index/constraint: {exc}", file=sys.stderr)


def run_batch(driver: Any, database: str, cypher: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    def work(tx: Any) -> None:
        tx.run(cypher, rows=rows).consume()

    with driver.session(database=database) as session:
        session.execute_write(work)


def batched(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def import_rows(
    driver: Any,
    database: str,
    label: str,
    cypher: str,
    rows: list[dict[str, Any]],
    batch_size: int,
) -> None:
    print(f"Importing {label}: {len(rows)} rows")
    for batch in batched(rows, batch_size):
        run_batch(driver, database, cypher, batch)


def create_document_rows(data_dir: Path) -> list[dict[str, Any]]:
    full_docs = load_json(data_dir / "kv_store_full_docs.json")
    statuses = load_json(data_dir / "kv_store_doc_status.json")
    rows: list[dict[str, Any]] = []
    for doc_id, doc in full_docs.items():
        status = statuses.get(doc_id, {})
        rows.append(
            {
                "id": doc_id,
                "props": clean_props(
                    {
                        "content": doc.get("content"),
                        "file_path": doc.get("file_path") or status.get("file_path"),
                        "status": status.get("status"),
                        "chunks_count": status.get("chunks_count"),
                        "content_length": status.get("content_length"),
                        "created_at": status.get("created_at"),
                        "updated_at": status.get("updated_at"),
                        "track_id": status.get("track_id"),
                        "processing_start_time": status.get("metadata", {}).get("processing_start_time"),
                        "processing_end_time": status.get("metadata", {}).get("processing_end_time"),
                    }
                ),
            }
        )
    return rows


def create_chunk_rows(data_dir: Path, with_vectors: bool) -> tuple[list[dict[str, Any]], int]:
    chunks = load_json(data_dir / "kv_store_text_chunks.json")
    vdb_chunks = load_json(data_dir / "vdb_chunks.json")
    vector_by_id = {record["__id__"]: record.get("vector") for record in vdb_chunks["data"]}
    vector_dim = int(vdb_chunks.get("embedding_dim") or 0)

    rows: list[dict[str, Any]] = []
    for chunk_id, chunk in chunks.items():
        props = {
            "content": chunk.get("content"),
            "tokens": chunk.get("tokens"),
            "chunk_order_index": chunk.get("chunk_order_index"),
            "full_doc_id": chunk.get("full_doc_id"),
            "file_path": chunk.get("file_path"),
            "created_at": chunk.get("create_time"),
            "updated_at": chunk.get("update_time"),
        }
        vector_value = vector_by_id.get(chunk_id)
        if with_vectors and vector_value:
            props["embedding"] = decode_vector(vector_value)
        rows.append({"id": chunk_id, "props": clean_props(props)})
    return rows, vector_dim


def create_doc_chunk_rows(data_dir: Path) -> list[dict[str, Any]]:
    statuses = load_json(data_dir / "kv_store_doc_status.json")
    rows: list[dict[str, Any]] = []
    for doc_id, status in statuses.items():
        for chunk_id in status.get("chunks_list", []):
            rows.append({"doc_id": doc_id, "chunk_id": chunk_id})
    return rows


def create_next_chunk_rows(data_dir: Path) -> list[dict[str, Any]]:
    chunks = load_json(data_dir / "kv_store_text_chunks.json")
    by_doc: dict[str, list[tuple[int, str]]] = {}
    for chunk_id, chunk in chunks.items():
        full_doc_id = chunk.get("full_doc_id")
        if not full_doc_id:
            continue
        by_doc.setdefault(full_doc_id, []).append((int(chunk.get("chunk_order_index") or 0), chunk_id))
    rows: list[dict[str, Any]] = []
    for doc_chunks in by_doc.values():
        ordered = [chunk_id for _, chunk_id in sorted(doc_chunks)]
        rows.extend({"left_id": left, "right_id": right} for left, right in zip(ordered, ordered[1:]))
    return rows


def build_entity_row(
    entity_id: str,
    graph_nodes: dict[str, dict[str, Any]],
    entity_records: dict[str, dict[str, Any]],
    with_vectors: bool,
) -> dict[str, Any]:
    graph_props = graph_nodes.get(entity_id, {})
    vdb_record = entity_records.get(entity_id, {})
    source_ids = graph_props.get("source_ids") or split_sep(vdb_record.get("source_id"))
    file_paths = graph_props.get("file_paths") or split_sep(vdb_record.get("file_path"))
    description = graph_props.get("description") or vdb_record.get("content")
    props = {
        "name": entity_id,
        "name_lc": entity_id.casefold(),
        "name_ascii": ascii_fold(entity_id),
        "entity_type": graph_props.get("entity_type"),
        "description": description,
        "source_ids": source_ids,
        "source_count": len(source_ids),
        "file_paths": file_paths,
        "created_at": graph_props.get("created_at") or vdb_record.get("__created_at__"),
    }
    vector_value = vdb_record.get("vector")
    if with_vectors and vector_value:
        props["embedding"] = decode_vector(vector_value)
    return {"id": entity_id, "props": clean_props(props)}


def create_entity_rows(data_dir: Path, graph_nodes: dict[str, dict[str, Any]], with_vectors: bool) -> list[dict[str, Any]]:
    vdb_entities = load_json(data_dir / "vdb_entities.json")
    entity_records = {record["entity_name"]: record for record in vdb_entities["data"]}
    return [
        build_entity_row(entity_id, graph_nodes, entity_records, with_vectors)
        for entity_id in sorted(set(graph_nodes) | set(entity_records))
    ]


def iter_entity_batches(
    data_dir: Path,
    graph_nodes: dict[str, dict[str, Any]],
    with_vectors: bool,
    batch_size: int,
) -> Iterator[list[dict[str, Any]]]:
    vdb_entities = load_json(data_dir / "vdb_entities.json")
    entity_records = {record["entity_name"]: record for record in vdb_entities["data"]}
    all_entity_ids = sorted(set(graph_nodes) | set(entity_records))
    batch: list[dict[str, Any]] = []
    for entity_id in all_entity_ids:
        batch.append(build_entity_row(entity_id, graph_nodes, entity_records, with_vectors))
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def create_mention_rows(data_dir: Path) -> list[dict[str, Any]]:
    entity_chunks = load_json(data_dir / "kv_store_entity_chunks.json")
    rows: list[dict[str, Any]] = []
    for entity_id, info in entity_chunks.items():
        for chunk_id in info.get("chunk_ids", []):
            rows.append({"entity_id": entity_id, "chunk_id": chunk_id})
    return rows


def create_relation_rows(data_dir: Path, graph_edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relation_chunks = load_json(data_dir / "kv_store_relation_chunks.json")
    rows: list[dict[str, Any]] = []
    for edge in graph_edges:
        pair_id = edge["pair_id"]
        reverse_pair_id = f"{edge['tgt_id']}{SEP}{edge['src_id']}"
        chunk_info = relation_chunks.get(pair_id) or relation_chunks.get(reverse_pair_id) or {}
        props = dict(edge)
        props["chunk_ids"] = chunk_info.get("chunk_ids", [])
        props["chunk_count"] = len(props["chunk_ids"])
        rows.append(
            {
                "pair_id": pair_id,
                "src_id": edge["src_id"],
                "tgt_id": edge["tgt_id"],
                "props": clean_props(props),
            }
        )
    return rows


def summarize(data_dir: Path, graph_nodes: dict[str, dict[str, Any]], graph_edges: list[dict[str, Any]]) -> None:
    status = load_json(data_dir / "kv_store_doc_status.json")
    status_counts: dict[str, int] = {}
    for item in status.values():
        status_counts[item.get("status", "unknown")] = status_counts.get(item.get("status", "unknown"), 0) + 1
    print("Data summary")
    print(f"- documents: {len(load_json(data_dir / 'kv_store_full_docs.json'))}")
    print(f"- chunks: {len(load_json(data_dir / 'kv_store_text_chunks.json'))}")
    print(f"- graph entities: {len(graph_nodes)}")
    print(f"- graph relations: {len(graph_edges)}")
    print(f"- doc status: {status_counts}")
    for name in ["vdb_chunks.json", "vdb_entities.json", "vdb_relationships.json"]:
        data = load_json(data_dir / name)
        print(f"- {name}: {len(data.get('data', []))} records, dim={data.get('embedding_dim')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="output_verson1_uet_kg_bigdata/rag_storage")
    parser.add_argument("--uri", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize data without connecting to Neo4j.")
    parser.add_argument("--indexes-only", action="store_true", help="Only create constraints/indexes, then exit.")
    parser.add_argument("--reset", action="store_true", help="Delete existing Document/Chunk/Entity graph before import.")
    parser.add_argument("--skip-vectors", action="store_true", help="Do not import embedding lists or vector indexes.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)
    graphml_path = data_dir / "graph_chunk_entity_relation.graphml"
    if not data_dir.exists():
        raise SystemExit(f"Data dir not found: {data_dir}")
    if not graphml_path.exists():
        raise SystemExit(f"GraphML not found: {graphml_path}")

    graph_nodes, graph_edges = parse_graphml(graphml_path)
    summarize(data_dir, graph_nodes, graph_edges)
    if args.dry_run:
        return 0

    uri = args.uri or "bolt://localhost:7687"
    user = args.user or "neo4j"
    password = args.password or getpass.getpass("Neo4j password: ")
    database = args.database or "neo4j"
    with_vectors = not args.skip_vectors

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        _, vector_dim = create_chunk_rows(data_dir, with_vectors=False)
        build_indexes(driver, database, vector_dim, with_vectors)
        if args.indexes_only:
            print("Index creation complete")
            return 0

        if args.reset:
            print("Deleting existing Document/Chunk/Entity graph")
            with driver.session(database=database) as session:
                session.run("MATCH (n) WHERE n:Document OR n:Chunk OR n:Entity DETACH DELETE n").consume()

        import_rows(
            driver,
            database,
            "documents",
            "UNWIND $rows AS row MERGE (d:Document {id: row.id}) SET d += row.props",
            create_document_rows(data_dir),
            args.batch_size,
        )

        chunk_rows, _ = create_chunk_rows(data_dir, with_vectors=with_vectors)
        import_rows(
            driver,
            database,
            "chunks",
            "UNWIND $rows AS row MERGE (c:Chunk {id: row.id}) SET c += row.props",
            chunk_rows,
            max(10, min(args.batch_size, 100 if with_vectors else args.batch_size)),
        )

        import_rows(
            driver,
            database,
            "document-chunk links",
            """
            UNWIND $rows AS row
            MATCH (d:Document {id: row.doc_id})
            MATCH (c:Chunk {id: row.chunk_id})
            MERGE (d)-[:HAS_CHUNK]->(c)
            """,
            create_doc_chunk_rows(data_dir),
            args.batch_size,
        )

        import_rows(
            driver,
            database,
            "next-chunk links",
            """
            UNWIND $rows AS row
            MATCH (left:Chunk {id: row.left_id})
            MATCH (right:Chunk {id: row.right_id})
            MERGE (left)-[:NEXT_CHUNK]->(right)
            """,
            create_next_chunk_rows(data_dir),
            args.batch_size,
        )

        entity_batch_size = max(10, min(args.batch_size, 50 if with_vectors else args.batch_size))
        entity_cypher = "UNWIND $rows AS row MERGE (e:Entity {id: row.id}) SET e += row.props"
        print(f"Importing entities: {len(graph_nodes)}+ rows")
        for batch in iter_entity_batches(data_dir, graph_nodes, with_vectors=with_vectors, batch_size=entity_batch_size):
            run_batch(driver, database, entity_cypher, batch)

        import_rows(
            driver,
            database,
            "chunk-entity mentions",
            """
            UNWIND $rows AS row
            MATCH (c:Chunk {id: row.chunk_id})
            MATCH (e:Entity {id: row.entity_id})
            MERGE (c)-[:MENTIONS]->(e)
            """,
            create_mention_rows(data_dir),
            args.batch_size,
        )

        import_rows(
            driver,
            database,
            "entity relations",
            """
            UNWIND $rows AS row
            MATCH (src:Entity {id: row.src_id})
            MATCH (tgt:Entity {id: row.tgt_id})
            MERGE (src)-[r:RELATES_TO {pair_id: row.pair_id}]->(tgt)
            SET r += row.props
            """,
            create_relation_rows(data_dir, graph_edges),
            args.batch_size,
        )

        print("Import complete")
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
