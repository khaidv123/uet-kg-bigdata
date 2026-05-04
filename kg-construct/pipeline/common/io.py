"""I/O helpers for runtime environment and JSON serialization."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def load_dotenv_values(path: str | Path) -> dict[str, str]:
    file_path = Path(path)
    if not file_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        key, sep, value = raw_line.partition("=")
        if not sep:
            continue

        clean_key = key.strip()
        clean_value = value.strip()
        if (
            len(clean_value) >= 2
            and clean_value[0] == clean_value[-1]
            and clean_value[0] in {'"', "'"}
        ):
            clean_value = clean_value[1:-1]
        values[clean_key] = clean_value
    return values


def collect_runtime_env(
    repo_root: str | Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    root = Path(repo_root)
    merged = load_dotenv_values(root / ".env")
    source = environ if environ is not None else os.environ
    for key, value in source.items():
        if value is None or value == "":
            continue
        merged[key] = value
    return merged


def get_env_value(
    name: str,
    default: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    source = environ if environ is not None else os.environ
    value = source.get(name)
    if value is None or value == "":
        return default
    return value


def get_env_int(
    name: str,
    default: int,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    value = get_env_value(name, None, environ=environ)
    if value is None:
        return default
    return int(value)


def get_env_float(
    name: str,
    default: float,
    *,
    environ: Mapping[str, str] | None = None,
) -> float:
    value = get_env_value(name, None, environ=environ)
    if value is None:
        return default
    return float(value)


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safe_json_loads(payload: str | None) -> Any:
    if payload is None:
        return None
    stripped = payload.strip()
    if not stripped:
        return None
    return json.loads(stripped)
