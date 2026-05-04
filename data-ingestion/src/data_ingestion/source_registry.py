"""Source registry models and loaders for Phase 1 crawl configuration."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from .bootstrap import load_yaml_file, project_root, resolve_project_path

SOURCE_TYPES = Literal[
    "news",
    "events",
    "notices",
    "admissions",
    "scholarships",
    "public_documents",
]

SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def _normalize_domain(value: str) -> str:
    domain = value.strip().lower()
    if "://" in domain:
        domain = domain.split("://", maxsplit=1)[1]
    return domain.strip("/")


def _domain_matches(host: str, allowed_domain: str) -> bool:
    return host == allowed_domain


class SourceRegistryScope(BaseModel):
    owner: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    root_domain: str = Field(min_length=1)

    @field_validator("root_domain")
    @classmethod
    def validate_root_domain(cls, value: str) -> str:
        return _normalize_domain(value)


class SourceRegistryDefaults(BaseModel):
    allowed_domains: list[str] = Field(min_length=1)
    deny_patterns: list[str] = Field(default_factory=list)
    pdf_patterns: list[str] = Field(default_factory=list)

    @field_validator("allowed_domains", mode="before")
    @classmethod
    def validate_allowed_domains(cls, value: Any) -> list[str]:
        if not isinstance(value, list) or not value:
            raise ValueError("allowed_domains must be a non-empty list")
        return _dedupe_keep_order([_normalize_domain(item) for item in value])

    @field_validator("deny_patterns", "pdf_patterns", mode="before")
    @classmethod
    def validate_pattern_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("pattern lists must be lists")
        return _dedupe_keep_order([str(item).strip() for item in value if str(item).strip()])


class SourceDefinition(BaseModel):
    id: str
    source_type: SOURCE_TYPES
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    enabled: bool = True
    start_urls: list[HttpUrl] = Field(min_length=1)
    allowed_domains: list[str] = Field(min_length=1)
    deny_patterns: list[str] = Field(default_factory=list)
    pdf_patterns: list[str] = Field(default_factory=list)
    crawl_interval_hours: int = Field(ge=1)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not SOURCE_ID_PATTERN.fullmatch(value):
            raise ValueError("source id must use lowercase kebab-case")
        return value

    @field_validator("allowed_domains", mode="before")
    @classmethod
    def normalize_allowed_domains(cls, value: Any) -> list[str]:
        if not isinstance(value, list) or not value:
            raise ValueError("allowed_domains must be a non-empty list")
        return _dedupe_keep_order([_normalize_domain(item) for item in value])

    @field_validator("deny_patterns", "pdf_patterns", mode="before")
    @classmethod
    def normalize_patterns(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("pattern lists must be lists")
        return _dedupe_keep_order([str(item).strip() for item in value if str(item).strip()])

    @model_validator(mode="after")
    def ensure_urls_match_allowed_domains(self) -> "SourceDefinition":
        for url in self.start_urls:
            host = (url.host or "").lower()
            if not any(_domain_matches(host, domain) for domain in self.allowed_domains):
                raise ValueError(
                    f"start_urls host '{host}' is outside allowed_domains for source '{self.id}'"
                )
        return self


class SourceRegistry(BaseModel):
    version: int = Field(ge=1)
    scope: SourceRegistryScope
    defaults: SourceRegistryDefaults
    sources: list[SourceDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def ensure_unique_ids(self) -> "SourceRegistry":
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique")
        return self


def _merge_source_defaults(
    raw_source: dict[str, Any],
    defaults: SourceRegistryDefaults,
) -> dict[str, Any]:
    merged = dict(raw_source)
    merged["allowed_domains"] = _dedupe_keep_order(
        list(merged.get("allowed_domains") or defaults.allowed_domains)
    )
    merged["deny_patterns"] = _dedupe_keep_order(
        [*defaults.deny_patterns, *(merged.get("deny_patterns") or [])]
    )
    merged["pdf_patterns"] = _dedupe_keep_order(
        [*defaults.pdf_patterns, *(merged.get("pdf_patterns") or [])]
    )
    return merged


def load_source_registry(
    path: str | Path | None = None,
    environ: dict[str, str] | None = None,
    base_dir: Path | None = None,
) -> SourceRegistry:
    """Load the source registry YAML and merge source-specific defaults."""
    env = os.environ if environ is None else environ
    root = project_root() if base_dir is None else base_dir
    raw_path = path or env.get("SOURCE_REGISTRY_PATH", "config/sources.yaml")
    resolved_path = resolve_project_path(raw_path, base_dir=root)
    payload = load_yaml_file(resolved_path)
    defaults = SourceRegistryDefaults.model_validate(payload.get("defaults", {}))
    merged_sources = [
        _merge_source_defaults(source, defaults)
        for source in payload.get("sources", [])
    ]

    return SourceRegistry.model_validate(
        {
            **payload,
            "defaults": defaults.model_dump(),
            "sources": merged_sources,
        }
    )


def enabled_sources(registry: SourceRegistry) -> list[SourceDefinition]:
    """Return only enabled sources in declaration order."""
    return [source for source in registry.sources if source.enabled]
