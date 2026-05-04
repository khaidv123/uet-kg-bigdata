#!/usr/bin/env python3
"""Local web UI server for the Neo4j RAG chatbot."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from chatbot_neo4j import answer_question


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")


def bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clean_history(raw_history: Any) -> list[dict[str, str]]:
    if not isinstance(raw_history, list):
        return []
    history: list[dict[str, str]] = []
    for item in raw_history[-12:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            history.append({"role": role, "content": content.strip()[:4000]})
    return history


def build_args(settings: dict[str, Any]) -> argparse.Namespace:
    vector_enabled = bool_value(settings.get("vectorSearch"), default=False)
    return argparse.Namespace(
        uri=settings.get("neo4jUri") or os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=settings.get("neo4jUser") or os.getenv("NEO4J_USER", "neo4j"),
        password=settings.get("neo4jPassword") or os.getenv("NEO4J_PASSWORD"),
        database=settings.get("neo4jDatabase") or os.getenv("NEO4J_DATABASE", "neo4j"),
        api_key=settings.get("apiKey") or os.getenv("OPENAI_CHAT_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=settings.get("baseUrl") or os.getenv("OPENAI_CHAT_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
        chat_model=settings.get("chatModel")
        or os.getenv("OPENAI_CHAT_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "gpt-4o-mini",
        embedding_model=settings.get("embeddingModel") or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        embedding_api_key=settings.get("embeddingApiKey") or os.getenv("OPENAI_EMBEDDING_API_KEY"),
        embedding_base_url=settings.get("embeddingBaseUrl") or os.getenv("OPENAI_EMBEDDING_BASE_URL"),
        entity_k=int_value(settings.get("entityK"), 8),
        chunk_k=int_value(settings.get("chunkK"), 8),
        relation_k=int_value(settings.get("relationK"), 20),
        relations_per_entity=int_value(settings.get("relationsPerEntity"), 5),
        no_vector=not vector_enabled,
        max_context_chars=int_value(settings.get("maxContextChars"), 12000),
        chunk_char_limit=int_value(settings.get("chunkCharLimit"), 1200),
        history_turns=int_value(settings.get("historyTurns"), 3),
        retrieval_history_turns=int_value(settings.get("retrievalHistoryTurns"), 1),
        temperature=float_value(settings.get("temperature"), 0.2),
        show_sources=True,
        json=False,
    )


@app.get("/")
def index() -> Any:
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/api/health")
def health() -> Any:
    return jsonify({"ok": True})


@app.post("/api/chat")
def chat() -> Any:
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400

    settings = body.get("settings") if isinstance(body.get("settings"), dict) else {}
    history = clean_history(body.get("history"))
    args = build_args(settings)

    try:
        payload = answer_question(args, message, history)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    retrieval = payload.get("retrieval") or {}
    return jsonify(
        {
            "answer": payload.get("answer"),
            "sources": payload.get("sources", []),
            "usage": payload.get("usage", {}),
            "retrieval": {
                "query": retrieval.get("query"),
                "vector_used": retrieval.get("vector_used"),
                "entity_count": len(retrieval.get("entities") or []),
                "relation_count": len(retrieval.get("relations") or []),
                "chunk_count": len(retrieval.get("chunks") or []),
            },
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
