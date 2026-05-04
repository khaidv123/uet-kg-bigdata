"""Utility helpers for URL normalization and document ids."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_WHITESPACE_RE = re.compile(r"\s+")
_ASSET_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".css",
    ".js",
    ".xml",
    ".zip",
    ".rar",
    ".7z",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
)


def normalize_whitespace(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


def normalize_url(url: str) -> str:
    """Return a stable normalized URL for deduplication."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, path, query, ""))


def build_doc_id(url: str, source_name: str) -> str:
    """Build a deterministic document id from normalized URL and source name."""
    canonical = f"{source_name.strip().lower()}|{normalize_url(url)}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def extract_text_preview(text: str, limit: int = 280) -> str:
    """Collapse whitespace and truncate a preview without breaking words too early."""
    normalized = normalize_whitespace(text)
    if len(normalized) <= limit:
        return normalized
    trimmed = normalized[: limit + 1].rsplit(" ", maxsplit=1)[0].strip()
    return (trimmed or normalized[:limit].strip()) + "..."


def url_matches_patterns(url: str, patterns: list[str]) -> bool:
    """Return true when the URL matches any deny or discovery pattern."""
    for pattern in patterns:
        candidate = pattern.strip()
        if not candidate:
            continue
        try:
            if re.search(candidate, url):
                return True
        except re.error:
            pass
        if candidate in url:
            return True
    return False


def candidate_urls_for_matching(url: str) -> list[str]:
    raw_url = url.strip()
    normalized = normalize_url(raw_url)
    return [
        raw_url,
        raw_url.rstrip("/"),
        normalized,
        normalized.rstrip("/"),
    ]


def is_asset_url(url: str) -> bool:
    lowered = url.lower()
    return lowered.startswith(("mailto:", "tel:", "javascript:")) or lowered.endswith(_ASSET_EXTENSIONS)


def has_allowed_host(url: str, allowed_domains: list[str]) -> bool:
    normalized = normalize_url(url)
    host = urlsplit(normalized).netloc.lower()
    return host in allowed_domains


def is_pdf_url(url: str, pdf_patterns: list[str]) -> bool:
    return any(url_matches_patterns(candidate, pdf_patterns) for candidate in candidate_urls_for_matching(url))


def is_followable_html_url(
    url: str,
    *,
    allowed_domains: list[str],
    deny_patterns: list[str],
    pdf_patterns: list[str],
) -> bool:
    """Apply source scope, deny rules, and lightweight asset filtering."""
    if not url or is_asset_url(url):
        return False

    raw_url = url.strip()
    normalized = normalize_url(raw_url)
    candidate_urls = candidate_urls_for_matching(raw_url)

    if not has_allowed_host(normalized, allowed_domains):
        return False
    if any(url_matches_patterns(candidate, deny_patterns) for candidate in candidate_urls):
        return False
    if is_pdf_url(normalized, pdf_patterns):
        return False
    return True
