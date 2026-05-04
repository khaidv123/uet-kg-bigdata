"""Small config loader utilities for Phase 2 jobs.

This module prefers PyYAML when available, but also supports the small YAML
subset used by this repository so Spark containers can run jobs without extra
Python dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple


def _parse_scalar(value: str) -> Any:
    if value == "":
        return ""
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        try:
            return int(value)
        except ValueError:
            pass
    try:
        return float(value)
    except ValueError:
        pass

    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _prepare_lines(text: str) -> List[Tuple[int, str]]:
    lines: List[Tuple[int, str]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append((indent, raw_line[indent:]))
    return lines


def _parse_block(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[Any, int]:
    if index >= len(lines):
        return {}, index

    current_indent, content = lines[index]
    if current_indent != indent:
        raise ValueError(f"Unexpected indentation at line: {content}")

    if content.startswith("- "):
        items: List[Any] = []
        while index < len(lines):
            line_indent, line_content = lines[index]
            if line_indent < indent:
                break
            if line_indent != indent or not line_content.startswith("- "):
                raise ValueError(f"Invalid list item indentation near: {line_content}")

            item_content = line_content[2:].strip()
            if not item_content:
                nested, index = _parse_block(lines, index + 1, indent + 2)
                items.append(nested)
                continue

            if ": " in item_content or item_content.endswith(":"):
                key, _, value = item_content.partition(":")
                mapping: Dict[str, Any] = {}
                key = key.strip()
                value = value.strip()
                if value:
                    mapping[key] = _parse_scalar(value)
                    index += 1
                else:
                    nested, index = _parse_block(lines, index + 1, indent + 2)
                    mapping[key] = nested

                while index < len(lines):
                    next_indent, next_content = lines[index]
                    if next_indent <= indent:
                        break
                    if next_indent != indent + 2:
                        raise ValueError(f"Invalid nested indentation near: {next_content}")
                    sub_key, _, sub_value = next_content.partition(":")
                    sub_key = sub_key.strip()
                    sub_value = sub_value.strip()
                    if sub_value:
                        mapping[sub_key] = _parse_scalar(sub_value)
                        index += 1
                    else:
                        nested, index = _parse_block(lines, index + 1, indent + 4)
                        mapping[sub_key] = nested
                items.append(mapping)
            else:
                items.append(_parse_scalar(item_content))
                index += 1
        return items, index

    mapping: Dict[str, Any] = {}
    while index < len(lines):
        line_indent, line_content = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent:
            raise ValueError(f"Unexpected indentation near: {line_content}")

        key, _, value = line_content.partition(":")
        key = key.strip()
        value = value.strip()
        if value:
            mapping[key] = _parse_scalar(value)
            index += 1
        else:
            nested, index = _parse_block(lines, index + 1, indent + 2)
            mapping[key] = nested
    return mapping, index


def _load_yaml_subset(path: Path) -> Dict[str, Any]:
    lines = _prepare_lines(path.read_text(encoding="utf-8"))
    if not lines:
        return {}
    parsed, _ = _parse_block(lines, 0, 0)
    if not isinstance(parsed, dict):
        raise ValueError(f"Top-level YAML document must be a mapping: {path}")
    return parsed


def load_yaml(path: str | Path) -> Dict[str, Any]:
    file_path = Path(path)
    try:
        import yaml  # type: ignore

        with file_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Top-level YAML document must be a mapping: {file_path}")
        return data
    except ModuleNotFoundError:
        return _load_yaml_subset(file_path)

