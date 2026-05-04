#!/usr/bin/env python3
"""Hybrid retrieval over the imported Neo4j knowledge graph."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from openai import OpenAIError


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def ascii_fold(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").casefold()


def compact_text(value: str | None, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def lucene_query(text: str) -> str:
    terms = re.findall(r"[\wÀ-ỹ]+", text.casefold(), flags=re.UNICODE)
    query_terms = []
    for term in terms:
        escaped = re.sub(r'([+\-!(){}\[\]^"~*?:\\/])', r"\\\1", term)
        query_terms.append(f"{escaped}~1" if len(escaped) >= 4 and not escaped.isdigit() else escaped)
    return " OR ".join(query_terms) or "*"


def embed_query(
    text: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> list[float] | None:
    api_key = api_key or os.getenv("OPENAI_EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = base_url or os.getenv("OPENAI_EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if not api_key:
        return None
    from openai import OpenAI

    try:
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        response = client.embeddings.create(model=model, input=text)
        return response.data[0].embedding
    except OpenAIError as exc:
        print(f"WARN: embedding query skipped: {exc}", file=sys.stderr)
        return None


def run(session: Any, cypher: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(record) for record in session.run(cypher, **params)]


def fulltext_entities(session: Any, query: str, limit: int) -> list[dict[str, Any]]:
    cypher = """
    CALL db.index.fulltext.queryNodes('entity_text', $lucene) YIELD node, score
    RETURN node.id AS id, node.name AS name, node.entity_type AS entity_type,
           node.description AS description, score, 'entity_fulltext' AS source
    ORDER BY score DESC
    LIMIT $limit
    """
    try:
        return run(session, cypher, lucene=lucene_query(query), limit=limit)
    except Neo4jError as exc:
        print(f"WARN: entity fulltext skipped: {exc}", file=sys.stderr)
        fallback = """
        MATCH (node:Entity)
        WHERE node.name_lc CONTAINS $q OR node.name_ascii CONTAINS $qa
           OR toLower(node.description) CONTAINS $q
        RETURN node.id AS id, node.name AS name, node.entity_type AS entity_type,
               node.description AS description, 0.0 AS score, 'entity_contains' AS source
        ORDER BY coalesce(node.source_count, 0) DESC
        LIMIT $limit
        """
        return run(session, fallback, q=query.casefold(), qa=ascii_fold(query), limit=limit)


def fulltext_chunks(session: Any, query: str, limit: int) -> list[dict[str, Any]]:
    cypher = """
    CALL db.index.fulltext.queryNodes('chunk_text', $lucene) YIELD node, score
    RETURN node.id AS id, node.content AS content, node.file_path AS file_path,
           node.full_doc_id AS full_doc_id, score, 'chunk_fulltext' AS source
    ORDER BY score DESC
    LIMIT $limit
    """
    try:
        return run(session, cypher, lucene=lucene_query(query), limit=limit)
    except Neo4jError as exc:
        print(f"WARN: chunk fulltext skipped: {exc}", file=sys.stderr)
        fallback = """
        MATCH (node:Chunk)
        WHERE toLower(node.content) CONTAINS $q
        RETURN node.id AS id, node.content AS content, node.file_path AS file_path,
               node.full_doc_id AS full_doc_id, 0.0 AS score, 'chunk_contains' AS source
        LIMIT $limit
        """
        return run(session, fallback, q=query.casefold(), limit=limit)


def vector_entities(session: Any, embedding: list[float], limit: int) -> list[dict[str, Any]]:
    cypher = """
    CALL db.index.vector.queryNodes('entity_embedding', $limit, $embedding) YIELD node, score
    RETURN node.id AS id, node.name AS name, node.entity_type AS entity_type,
           node.description AS description, score, 'entity_vector' AS source
    ORDER BY score DESC
    """
    try:
        return run(session, cypher, embedding=embedding, limit=limit)
    except Neo4jError as exc:
        print(f"WARN: entity vector search skipped: {exc}", file=sys.stderr)
        return []


def vector_chunks(session: Any, embedding: list[float], limit: int) -> list[dict[str, Any]]:
    cypher = """
    CALL db.index.vector.queryNodes('chunk_embedding', $limit, $embedding) YIELD node, score
    RETURN node.id AS id, node.content AS content, node.file_path AS file_path,
           node.full_doc_id AS full_doc_id, score, 'chunk_vector' AS source
    ORDER BY score DESC
    """
    try:
        return run(session, cypher, embedding=embedding, limit=limit)
    except Neo4jError as exc:
        print(f"WARN: chunk vector search skipped: {exc}", file=sys.stderr)
        return []


def merge_ranked(items: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in items:
        item_key = item.get(key)
        if not item_key:
            continue
        current = merged.get(item_key)
        if current is None or float(item.get("score") or 0) > float(current.get("score") or 0):
            merged[item_key] = item
        else:
            sources = {current.get("source"), item.get("source")}
            current["source"] = "+".join(sorted(x for x in sources if x))
    return sorted(merged.values(), key=lambda x: float(x.get("score") or 0), reverse=True)[:limit]


def entity_neighborhood(session: Any, entity_ids: list[str], per_seed: int) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    cypher = """
    UNWIND $ids AS seed_id
    MATCH (seed:Entity {id: seed_id})
    CALL (seed) {
      MATCH (seed)-[r:RELATES_TO]-(neighbor:Entity)
      RETURN r, neighbor
      ORDER BY coalesce(r.weight, 0.0) DESC
      LIMIT $per_seed
    }
    RETURN seed.id AS seed_id, seed.name AS seed_name,
           neighbor.id AS neighbor_id, neighbor.name AS neighbor_name,
           neighbor.entity_type AS neighbor_type,
           r.weight AS weight, r.description AS description,
           r.keywords AS keywords, r.source_ids AS source_ids,
           r.chunk_ids AS chunk_ids
    ORDER BY seed_id, weight DESC
    """
    return run(session, cypher, ids=entity_ids, per_seed=per_seed)


def chunks_for_entities(session: Any, entity_ids: list[str], limit: int) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    cypher = """
    MATCH (chunk:Chunk)-[:MENTIONS]->(entity:Entity)
    WHERE entity.id IN $ids
    WITH chunk, collect(entity.name)[..5] AS matched_entities, count(entity) AS hit_count
    RETURN chunk.id AS id, chunk.content AS content, chunk.file_path AS file_path,
           chunk.full_doc_id AS full_doc_id, hit_count AS score,
           matched_entities, 'entity_mentions' AS source
    ORDER BY hit_count DESC, coalesce(chunk.tokens, 0) DESC
    LIMIT $limit
    """
    return run(session, cypher, ids=entity_ids, limit=limit)


def chunks_by_ids(session: Any, chunk_ids: list[str], limit: int) -> list[dict[str, Any]]:
    if not chunk_ids:
        return []
    cypher = """
    MATCH (chunk:Chunk)
    WHERE chunk.id IN $ids
    RETURN chunk.id AS id, chunk.content AS content, chunk.file_path AS file_path,
           chunk.full_doc_id AS full_doc_id, 0.0 AS score, 'relation_evidence' AS source
    LIMIT $limit
    """
    return run(session, cypher, ids=chunk_ids[:limit], limit=limit)


def retrieve(args: argparse.Namespace) -> dict[str, Any]:
    uri = args.uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = args.user or os.getenv("NEO4J_USER", "neo4j")
    password = args.password or os.getenv("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("Set NEO4J_PASSWORD or pass --password.")

    embedding = (
        None
        if args.no_vector
        else embed_query(
            args.query,
            args.embedding_model,
            getattr(args, "embedding_api_key", None),
            getattr(args, "embedding_base_url", None),
        )
    )
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=args.database or os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            entity_hits = fulltext_entities(session, args.query, args.entity_k)
            chunk_hits = fulltext_chunks(session, args.query, args.chunk_k)
            if embedding is not None:
                entity_hits.extend(vector_entities(session, embedding, args.entity_k))
                chunk_hits.extend(vector_chunks(session, embedding, args.chunk_k))

            entities = merge_ranked(entity_hits, "id", args.entity_k)
            seed_ids = [item["id"] for item in entities]
            relations = entity_neighborhood(session, seed_ids, args.relations_per_entity)

            relation_chunk_ids: list[str] = []
            for relation in relations:
                relation_chunk_ids.extend(relation.get("source_ids") or [])
                relation_chunk_ids.extend(relation.get("chunk_ids") or [])

            chunk_hits.extend(chunks_for_entities(session, seed_ids, args.chunk_k))
            chunk_hits.extend(chunks_by_ids(session, list(dict.fromkeys(relation_chunk_ids)), args.chunk_k))
            chunks = merge_ranked(chunk_hits, "id", args.chunk_k)

            return {
                "query": args.query,
                "vector_used": embedding is not None,
                "entities": entities,
                "relations": relations[: args.relation_k],
                "chunks": chunks,
            }
    finally:
        driver.close()


def print_human(result: dict[str, Any]) -> None:
    print(f"Query: {result['query']}")
    print(f"Vector search: {'yes' if result['vector_used'] else 'no'}")

    print("\nEntities")
    for index, entity in enumerate(result["entities"], start=1):
        print(
            f"{index}. {entity.get('name') or entity.get('id')} "
            f"[{entity.get('entity_type') or 'unknown'}] "
            f"score={float(entity.get('score') or 0):.4f} source={entity.get('source')}"
        )
        print(f"   {compact_text(entity.get('description'), 220)}")

    print("\nRelations")
    for index, relation in enumerate(result["relations"], start=1):
        print(
            f"{index}. {relation.get('seed_name')} -- {relation.get('neighbor_name')} "
            f"weight={relation.get('weight')}"
        )
        print(f"   {compact_text(relation.get('description'), 220)}")

    print("\nEvidence Chunks")
    for index, chunk in enumerate(result["chunks"], start=1):
        print(
            f"{index}. {chunk.get('id')} score={float(chunk.get('score') or 0):.4f} "
            f"source={chunk.get('source')} file={chunk.get('file_path')}"
        )
        print(f"   {compact_text(chunk.get('content'), 360)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--uri", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--entity-k", type=int, default=8)
    parser.add_argument("--chunk-k", type=int, default=8)
    parser.add_argument("--relation-k", type=int, default=20)
    parser.add_argument("--relations-per-entity", type=int, default=5)
    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    parser.add_argument("--embedding-api-key", default=None)
    parser.add_argument("--embedding-base-url", default=None)
    parser.add_argument("--no-vector", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of a human-readable report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = retrieve(args)
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
            return 1
        print(f"Lỗi: {exc}")
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
