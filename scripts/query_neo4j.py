#!/usr/bin/env python3
"""Hybrid retrieval over Neo4j graph traversal and Elasticsearch vector search."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from openai import OpenAIError

try:
    from elasticsearch import Elasticsearch
except ImportError:  # pragma: no cover - optional until Elasticsearch support is installed.
    Elasticsearch = None  # type: ignore[assignment]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_ES_CHUNKS_INDEX = "uet_kg_chunks"
RRF_K = 60


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
    api_key = (
        api_key
        or os.getenv("EMBEDDING_API_KEY")
        or os.getenv("OPENAI_EMBEDDING_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    base_url = (
        base_url
        or os.getenv("EMBEDDING_BASE_URL")
        or os.getenv("OPENAI_EMBEDDING_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
    )
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


def get_es_url(args: argparse.Namespace) -> str | None:
    return getattr(args, "es_url", None) or os.getenv("ELASTICSEARCH_URL")


def get_es_client(args: argparse.Namespace) -> Any:
    if Elasticsearch is None:
        raise RuntimeError("Install elasticsearch package to use Vector DB semantic search.")
    es_url = get_es_url(args)
    if not es_url:
        raise RuntimeError("Set ELASTICSEARCH_URL or pass --es-url to use Vector DB semantic search.")
    kwargs: dict[str, Any] = {}
    api_key = getattr(args, "es_api_key", None) or os.getenv("ELASTICSEARCH_API_KEY")
    user = getattr(args, "es_user", None) or os.getenv("ELASTICSEARCH_USER")
    password = getattr(args, "es_password", None) or os.getenv("ELASTICSEARCH_PASSWORD")
    ca_certs = getattr(args, "es_ca_certs", None) or os.getenv("ELASTICSEARCH_CA_CERTS")
    if api_key:
        kwargs["api_key"] = api_key
    elif user and password:
        kwargs["basic_auth"] = (user, password)
    if ca_certs:
        kwargs["ca_certs"] = ca_certs
    return Elasticsearch(es_url, **kwargs)


def es_chunks_index(args: argparse.Namespace) -> str:
    return (
        getattr(args, "es_chunks_index", None)
        or os.getenv("ES_CHUNKS_INDEX")
        or DEFAULT_ES_CHUNKS_INDEX
    )


def es_num_candidates(args: argparse.Namespace, limit: int) -> int:
    configured = getattr(args, "es_num_candidates", None)
    if configured:
        return max(limit, int(configured))
    return max(limit * 10, 50)


def semantic_chunks_es(args: argparse.Namespace, embedding: list[float] | None) -> list[dict[str, Any]]:
    if not embedding or getattr(args, "no_es", False) or not get_es_url(args):
        return []

    limit = int(getattr(args, "chunk_k", 8))
    index = es_chunks_index(args)
    es = get_es_client(args)
    source_filter = {
        "includes": ["id", "content", "file_path", "full_doc_id", "tokens", "chunk_order_index"],
        "excludes": ["embedding"],
    }
    knn_body = {
        "knn": {
            "field": "embedding",
            "query_vector": embedding,
            "k": limit,
            "num_candidates": es_num_candidates(args, limit),
        },
        "_source": source_filter,
    }

    try:
        response = es.search(index=index, body=knn_body)
    except Exception:
        script_body = {
            "size": limit,
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                        "params": {"query_vector": embedding},
                    },
                }
            },
            "_source": source_filter,
        }
        response = es.search(index=index, body=script_body)

    chunks: list[dict[str, Any]] = []
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source") or {}
        chunks.append(
            {
                "id": source.get("id") or hit.get("_id"),
                "content": source.get("content"),
                "file_path": source.get("file_path"),
                "full_doc_id": source.get("full_doc_id"),
                "tokens": source.get("tokens"),
                "chunk_order_index": source.get("chunk_order_index"),
                "score": hit.get("_score") or 0.0,
                "source": "elasticsearch_vector",
                "storage_layer": "vector_db",
            }
        )
    return chunks


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


def merge_ranked_groups(
    groups: list[list[dict[str, Any]]],
    key: str,
    limit: int,
    weights: list[float] | None = None,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group_index, items in enumerate(groups):
        weight = weights[group_index] if weights and group_index < len(weights) else 1.0
        for rank, item in enumerate(items, start=1):
            item_key = item.get(key)
            if not item_key:
                continue
            source = item.get("source") or f"source_{group_index}"
            rrf_score = weight / (RRF_K + rank)
            current = merged.get(item_key)
            if current is None:
                current = dict(item)
                current["score"] = rrf_score
                current["rrf_score"] = rrf_score
                current["raw_scores"] = {source: item.get("score")}
                current["source"] = source
                merged[item_key] = current
                continue

            current["score"] = float(current.get("score") or 0.0) + rrf_score
            current["rrf_score"] = float(current.get("rrf_score") or 0.0) + rrf_score
            raw_scores = current.setdefault("raw_scores", {})
            if isinstance(raw_scores, dict):
                raw_scores[source] = item.get("score")
            sources = set(str(current.get("source") or "").split("+"))
            sources.add(str(source))
            current["source"] = "+".join(sorted(source for source in sources if source))
    return sorted(merged.values(), key=lambda x: float(x.get("score") or 0), reverse=True)[:limit]


def merge_ranked(items: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
    return merge_ranked_groups([items], key, limit)


def merge_ranked_by_raw_score(items: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
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


def entity_neighborhood(
    session: Any,
    entity_ids: list[str],
    per_seed: int,
    graph_hops: int = 2,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    max_hops = max(1, min(int(graph_hops or 1), 5))
    total_limit = int(limit or len(entity_ids) * per_seed)
    cypher = f"""
    UNWIND $ids AS seed_id
    MATCH (seed:Entity {{id: seed_id}})
    CALL (seed) {{
      MATCH path = (seed)-[:RELATES_TO*1..{max_hops}]-(neighbor:Entity)
      WHERE neighbor.id <> seed.id
      WITH path, neighbor,
           reduce(total = 0.0, rel IN relationships(path) | total + coalesce(rel.weight, 0.0)) AS path_weight
      RETURN path, neighbor, path_weight
      ORDER BY path_weight DESC, length(path) ASC
      LIMIT $per_seed
    }}
    WITH seed, path, neighbor, path_weight, nodes(path) AS path_nodes, relationships(path) AS path_rels
    RETURN seed.id AS seed_id, seed.name AS seed_name,
           neighbor.id AS neighbor_id, neighbor.name AS neighbor_name,
           neighbor.entity_type AS neighbor_type,
           length(path) AS hops,
           path_weight AS weight,
           [node IN path_nodes | coalesce(node.name, node.id)] AS path_names,
           [rel IN path_rels | rel.description] AS descriptions,
           [rel IN path_rels | rel.keywords] AS keywords_by_hop,
           reduce(ids = [], rel IN path_rels | ids + coalesce(rel.source_ids, []) + coalesce(rel.chunk_ids, [])) AS chunk_ids,
           'neo4j_graph_traversal' AS source
    ORDER BY seed_id, weight DESC
    LIMIT $limit
    """
    rows = run(session, cypher, ids=entity_ids, per_seed=per_seed, limit=total_limit)
    for row in rows:
        descriptions = [item for item in row.get("descriptions") or [] if item]
        row["description"] = " | ".join(compact_text(item, 240) for item in descriptions)
        row["source_ids"] = list(dict.fromkeys(row.get("chunk_ids") or []))
    return rows


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


def retrieve_graph(args: argparse.Namespace, embedding: list[float] | None = None) -> dict[str, Any]:
    uri = args.uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = args.user or os.getenv("NEO4J_USER", "neo4j")
    password = args.password or os.getenv("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("Set NEO4J_PASSWORD or pass --password.")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=args.database or os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            entity_fulltext_hits = fulltext_entities(session, args.query, args.entity_k)
            entity_vector_hits: list[dict[str, Any]] = []
            chunk_fulltext_hits = fulltext_chunks(session, args.query, args.chunk_k)
            chunk_vector_hits: list[dict[str, Any]] = []
            if embedding is not None and getattr(args, "neo4j_vector", False):
                entity_vector_hits = vector_entities(session, embedding, args.entity_k)
                chunk_vector_hits = vector_chunks(session, embedding, args.chunk_k)

            entities = merge_ranked_groups(
                [entity_fulltext_hits, entity_vector_hits],
                "id",
                args.entity_k,
                [getattr(args, "rrf_entity_fulltext_weight", 1.0), getattr(args, "rrf_entity_vector_weight", 1.0)],
            )
            seed_ids = [item["id"] for item in entities]
            relations = entity_neighborhood(
                session,
                seed_ids,
                args.relations_per_entity,
                getattr(args, "graph_hops", 2),
                args.relation_k,
            )

            relation_chunk_ids: list[str] = []
            for relation in relations:
                relation_chunk_ids.extend(relation.get("source_ids") or [])
                relation_chunk_ids.extend(relation.get("chunk_ids") or [])

            entity_chunks = chunks_for_entities(session, seed_ids, args.chunk_k)
            relation_chunks = chunks_by_ids(session, list(dict.fromkeys(relation_chunk_ids)), args.chunk_k)
            chunks = merge_ranked_groups(
                [chunk_fulltext_hits, chunk_vector_hits, entity_chunks, relation_chunks],
                "id",
                args.chunk_k,
                [
                    getattr(args, "rrf_chunk_fulltext_weight", 1.0),
                    getattr(args, "rrf_chunk_vector_weight", 1.0),
                    getattr(args, "rrf_entity_mentions_weight", 1.0),
                    getattr(args, "rrf_relation_evidence_weight", 1.0),
                ],
            )

            return {
                "query": args.query,
                "entities": entities,
                "relations": relations[: args.relation_k],
                "chunks": chunks,
                "neo4j_vector_chunk_count": len(chunk_vector_hits),
                "neo4j_vector_entity_count": len(entity_vector_hits),
                "graph_hops": getattr(args, "graph_hops", 2),
            }
    finally:
        driver.close()


def retrieve(args: argparse.Namespace) -> dict[str, Any]:
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

    warnings: list[str] = []
    if not args.no_vector and embedding is None:
        warnings.append(
            "Embedding query skipped; set EMBEDDING_API_KEY/OPENAI_EMBEDDING_API_KEY "
            "or pass --embedding-api-key."
        )
    if embedding is not None and not getattr(args, "no_es", False) and not get_es_url(args):
        warnings.append("Elasticsearch semantic search skipped; set ELASTICSEARCH_URL or pass --es-url.")
    with ThreadPoolExecutor(max_workers=2) as executor:
        graph_future = executor.submit(retrieve_graph, args, embedding)
        vector_future = executor.submit(semantic_chunks_es, args, embedding)
        graph_result = graph_future.result()
        try:
            vector_chunks = vector_future.result()
        except Exception as exc:
            vector_chunks = []
            warnings.append(f"Elasticsearch semantic search skipped: {exc}")

    chunks = merge_ranked_groups(
        [graph_result.get("chunks") or [], vector_chunks],
        "id",
        args.chunk_k,
        [getattr(args, "rrf_neo4j_graph_weight", 1.0), getattr(args, "rrf_es_vector_weight", 1.0)],
    )
    return {
        "query": args.query,
        "embedding_created": embedding is not None,
        "vector_used": bool(vector_chunks) or bool(graph_result.get("neo4j_vector_chunk_count")),
        "vector_db": "+".join(
            source
            for source, used in [
                ("neo4j", bool(graph_result.get("neo4j_vector_chunk_count"))),
                ("elasticsearch", bool(vector_chunks)),
            ]
            if used
        )
        or None,
        "graph_db": "neo4j",
        "graph_hops": getattr(args, "graph_hops", 2),
        "semantic_chunk_count": len(vector_chunks),
        "neo4j_vector_chunk_count": graph_result.get("neo4j_vector_chunk_count", 0),
        "neo4j_vector_entity_count": graph_result.get("neo4j_vector_entity_count", 0),
        "entities": graph_result.get("entities") or [],
        "relations": graph_result.get("relations") or [],
        "chunks": chunks,
        "warnings": warnings,
    }


def print_human(result: dict[str, Any]) -> None:
    print(f"Query: {result['query']}")
    print(f"Embedding created: {'yes' if result.get('embedding_created') else 'no'}")
    print(f"Vector DB search: {'yes' if result.get('vector_used') else 'no'}")
    print(f"Graph traversal hops: {result.get('graph_hops')}")
    for warning in result.get("warnings") or []:
        print(f"WARN: {warning}", file=sys.stderr)

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
            f"hops={relation.get('hops', 1)} weight={relation.get('weight')}"
        )
        if relation.get("path_names"):
            print(f"   path: {' -> '.join(relation.get('path_names') or [])}")
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
    parser.add_argument("--graph-hops", type=int, default=2, help="Max Neo4j RELATES_TO hops for graph traversal.")
    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    parser.add_argument("--embedding-api-key", default=None)
    parser.add_argument("--embedding-base-url", default=None)
    parser.add_argument("--es-url", default=None)
    parser.add_argument("--es-user", default=None)
    parser.add_argument("--es-password", default=None)
    parser.add_argument("--es-api-key", default=None)
    parser.add_argument("--es-ca-certs", default=None)
    parser.add_argument("--es-chunks-index", default=os.getenv("ES_CHUNKS_INDEX", DEFAULT_ES_CHUNKS_INDEX))
    parser.add_argument("--es-num-candidates", type=int, default=None)
    parser.add_argument("--no-es", action="store_true", help="Do not query Elasticsearch Vector DB.")
    parser.add_argument("--neo4j-vector", action="store_true", help="Also use Neo4j vector indexes if available.")
    parser.add_argument("--rrf-entity-fulltext-weight", type=float, default=1.0)
    parser.add_argument("--rrf-entity-vector-weight", type=float, default=1.0)
    parser.add_argument("--rrf-chunk-fulltext-weight", type=float, default=1.0)
    parser.add_argument("--rrf-chunk-vector-weight", type=float, default=1.0)
    parser.add_argument("--rrf-entity-mentions-weight", type=float, default=1.0)
    parser.add_argument("--rrf-relation-evidence-weight", type=float, default=1.0)
    parser.add_argument("--rrf-neo4j-graph-weight", type=float, default=1.0)
    parser.add_argument("--rrf-es-vector-weight", type=float, default=1.0)
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
