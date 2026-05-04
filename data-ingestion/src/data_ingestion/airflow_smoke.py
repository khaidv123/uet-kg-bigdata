"""Helpers for verifying the Airflow runtime wiring in Phase 0."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Mapping


def load_smoke_config(config_path: str | Path) -> dict:
    """Load the JSON config used by the Airflow smoke checks."""
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_paths(paths: Mapping[str, str], expect_files: bool) -> dict[str, str]:
    """Ensure the configured paths exist and match the expected type."""
    resolved_paths: dict[str, str] = {}

    for label, raw_path in paths.items():
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"{label} does not exist: {path}")
        if expect_files and not path.is_file():
            raise FileNotFoundError(f"{label} is not a file: {path}")
        if not expect_files and not path.is_dir():
            raise NotADirectoryError(f"{label} is not a directory: {path}")
        resolved_paths[label] = str(path.resolve())

    return resolved_paths


def _validate_required_env(names: list[str], environ: Mapping[str, str]) -> dict[str, str]:
    """Ensure the required environment variables are present and non-empty."""
    missing = [name for name in names if not environ.get(name)]
    if missing:
        joined = ", ".join(sorted(missing))
        raise KeyError(f"Missing required environment variables: {joined}")

    return {name: environ[name] for name in names}


def _validate_modules(module_names: list[str]) -> dict[str, str]:
    """Import the configured modules to prove the Airflow image is ready."""
    imported_modules: dict[str, str] = {}

    for module_name in module_names:
        module = importlib.import_module(module_name)
        imported_modules[module_name] = getattr(module, "__file__", "built-in")

    return imported_modules


def run_runtime_smoke(
    config_path: str | Path,
    environ: Mapping[str, str] | None = None,
    report_path: str | Path | None = None,
) -> dict:
    """Run the Airflow smoke checks and return a JSON-serializable summary."""
    env = os.environ if environ is None else environ
    config = load_smoke_config(config_path)

    mount_paths = _validate_paths(config.get("required_mounts", {}), expect_files=False)
    sample_files = _validate_paths(config.get("sample_files", {}), expect_files=True)
    required_env = _validate_required_env(config.get("required_env", []), env)
    imported_modules = _validate_modules(config.get("required_modules", []))

    summary = {
        "config_path": str(Path(config_path).resolve()),
        "required_env": required_env,
        "required_mounts": mount_paths,
        "sample_files": sample_files,
        "modules": imported_modules,
    }

    if report_path is not None:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return summary
