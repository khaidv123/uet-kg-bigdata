"""Pure-Python parser and validator for extraction LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip().lstrip("\ufeff")
    fence_match = re.fullmatch(
        r"```(?:json|JSON)?\s*(.*?)\s*```",
        stripped,
        flags=re.DOTALL,
    )
    if fence_match:
        return fence_match.group(1).strip()
    return stripped


def _repair_json_candidate(text: str) -> str:
    without_trailing_commas = re.sub(r",\s*([}\]])", r"\1", text)
    return without_trailing_commas.strip()


def parse_json_payload(response_text: str | None) -> Any:
    """Parse common LLM JSON shapes without adding an external dependency."""
    if response_text is None or not response_text.strip():
        raise ValueError("empty_response")

    text = _strip_markdown_fence(response_text)
    candidates = [text, _repair_json_candidate(text)]
    decoder = json.JSONDecoder()

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    for start_index, character in enumerate(text):
        if character not in "[{":
            continue
        fragment = _repair_json_candidate(text[start_index:])
        try:
            parsed, _ = decoder.raw_decode(fragment)
            return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError("invalid_json")


def _clean_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}_must_be_string")
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(f"{field_name}_must_not_be_empty")
    return cleaned


def _dedup_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _unwrap_stage_payload(stage: str, payload: Any) -> Any:
    if isinstance(payload, dict) and stage in payload:
        return payload[stage]
    return payload


def validate_stage_payload(stage: str, payload: Any) -> list[dict[str, Any]]:
    payload = _unwrap_stage_payload(stage, payload)
    if not isinstance(payload, list):
        raise ValueError(f"{stage}_payload_must_be_array")

    normalized: list[dict[str, Any]] = []
    if stage in {"entity_relation", "event_relation"}:
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                raise ValueError(f"{stage}[{index}]_must_be_object")
            normalized.append(
                {
                    "Head": _clean_string(item.get("Head"), f"{stage}[{index}].Head"),
                    "Relation": _clean_string(
                        item.get("Relation"),
                        f"{stage}[{index}].Relation",
                    ),
                    "Tail": _clean_string(item.get("Tail"), f"{stage}[{index}].Tail"),
                }
            )
        return normalized

    if stage == "event_entity":
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                raise ValueError(f"{stage}[{index}]_must_be_object")
            raw_entities = item.get("Entity")
            if not isinstance(raw_entities, list):
                raise ValueError(f"{stage}[{index}].Entity_must_be_array")
            entities = _dedup_strings(
                _clean_string(value, f"{stage}[{index}].Entity[]")
                for value in raw_entities
            )
            if not entities:
                raise ValueError(f"{stage}[{index}].Entity_must_not_be_empty")
            normalized.append(
                {
                    "Event": _clean_string(item.get("Event"), f"{stage}[{index}].Event"),
                    "Entity": entities,
                }
            )
        return normalized

    raise ValueError(f"unsupported_stage:{stage}")
