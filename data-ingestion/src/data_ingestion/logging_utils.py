"""Helpers for loading the shared logging configuration."""

from __future__ import annotations

import logging
import logging.config
import os
from pathlib import Path
from typing import Any

from .bootstrap import load_yaml_file, project_root, resolve_project_path


def _expand_values(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, str):
        for name, replacement in variables.items():
            value = value.replace(f"${{{name}}}", replacement)
        return value
    if isinstance(value, list):
        return [_expand_values(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _expand_values(item, variables) for key, item in value.items()}
    return value


def configure_logging(
    config_path: str | Path | None = None,
    *,
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Load the shared YAML logging config and apply it."""
    root = project_root() if project_dir is None else Path(project_dir)
    raw_config_path = config_path or os.environ.get("LOGGING_CONFIG_PATH", "config/logging.yaml")
    resolved_config_path = resolve_project_path(raw_config_path, base_dir=root)
    config = load_yaml_file(resolved_config_path)

    expanded = _expand_values(
        config,
        {
            "PROJECT_ROOT": str(root),
        },
    )

    logs_dir = root / "logs" / "ingestion"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(expanded)
    return expanded
