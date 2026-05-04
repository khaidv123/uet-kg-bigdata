"""Helpers for validating concept generation responses."""

from __future__ import annotations

import csv
import json
import re
from io import StringIO
from typing import Any


FENCED_JSON_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def strip_fenced_payload(response_text: str) -> str:
    """Remove a Markdown code fence when the model wraps the full payload."""

    match = FENCED_JSON_RE.match(response_text)
    if match:
        return match.group(1).strip()
    return response_text.strip()


def _parse_csv_fallback(payload: str) -> list[str]:
    reader = csv.reader(StringIO(payload), skipinitialspace=True)
    rows = list(reader)
    if len(rows) != 1:
        raise ValueError("comma-separated fallback must contain exactly one row")
    return [str(item) for item in rows[0]]


def parse_concept_response(response_text: str | None) -> list[str]:
    """Parse a concept response into a normalized list of concept strings.

    The locked prompt asks for a JSON array of strings. A small compatibility
    fallback accepts fenced JSON, {"concepts": [...]} payloads, and one-line
    comma-separated responses from older prompts.
    """

    if response_text is None:
        raise ValueError("response_text is null")

    payload = strip_fenced_payload(response_text)
    if not payload:
        return []

    parsed: Any
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        if payload.startswith("[") or payload.startswith("{"):
            raise
        parsed = _parse_csv_fallback(payload)

    if isinstance(parsed, dict) and "concepts" in parsed:
        parsed = parsed["concepts"]

    if not isinstance(parsed, list):
        raise ValueError("concept response must be a JSON array of strings")
    if not all(isinstance(item, str) for item in parsed):
        raise ValueError("concept response array must contain only strings")

    return normalize_concepts(parsed)


def normalize_concepts(concepts: list[str]) -> list[str]:
    """Trim, drop empty values, and deduplicate while preserving Unicode/case."""

    normalized: list[str] = []
    seen: set[str] = set()
    for concept in concepts:
        cleaned = " ".join(concept.strip().split())
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized
