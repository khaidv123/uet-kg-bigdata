"""Phase 1 data contracts and object-key naming helpers."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

ObjectKind = Literal["html_json", "pdf_binary", "pdf_metadata", "pdf_text_json"]

RAW_HTML_REQUIRED_FIELDS = (
    "doc_id",
    "source_name",
    "url",
    "title",
    "fetched_at",
    "status_code",
    "content_type",
    "encoding",
    "html",
    "text_preview",
    "etag",
    "last_modified",
    "content_hash",
)

RAW_PDF_REQUIRED_FIELDS = (
    "doc_id",
    "source_name",
    "url",
    "filename",
    "fetched_at",
    "status_code",
    "content_type",
    "content_length",
    "etag",
    "last_modified",
    "content_hash",
    "object_key",
    "metadata_object_key",
)

PDF_TEXT_REQUIRED_FIELDS = (
    "doc_id",
    "source_name",
    "source_pdf_doc_id",
    "source_pdf_object_key",
    "url",
    "extracted_at",
    "extract_method",
    "page_count",
    "char_count",
    "has_text_layer",
    "full_text",
    "pages",
)

_KEY_PART_PATTERN = re.compile(r"[^a-z0-9._-]+")


def _safe_key_part(value: str) -> str:
    normalized = _KEY_PART_PATTERN.sub("-", value.strip().lower()).strip("-")
    return normalized or "unknown"


def _date_parts(value: date | datetime) -> tuple[str, str, str]:
    if isinstance(value, datetime):
        value = value.date()
    return (f"{value:%Y}", f"{value:%m}", f"{value:%d}")


def build_object_key(
    kind: ObjectKind,
    run_date: date | datetime,
    source_name: str,
    doc_id: str,
) -> str:
    """Build the canonical MinIO object key for a Phase 1 artifact."""
    yyyy, mm, dd = _date_parts(run_date)
    safe_source_name = _safe_key_part(source_name)
    safe_doc_id = _safe_key_part(doc_id)

    if kind == "html_json":
        return str(
            PurePosixPath("html", yyyy, mm, dd, safe_source_name, f"{safe_doc_id}.json")
        )
    if kind == "pdf_binary":
        return str(
            PurePosixPath("pdf", yyyy, mm, dd, safe_source_name, f"{safe_doc_id}.pdf")
        )
    if kind == "pdf_metadata":
        return str(
            PurePosixPath("pdf", yyyy, mm, dd, safe_source_name, f"{safe_doc_id}.metadata.json")
        )
    if kind == "pdf_text_json":
        return str(
            PurePosixPath("pdf_text", yyyy, mm, dd, safe_source_name, f"{safe_doc_id}.json")
        )
    raise ValueError(f"Unsupported object kind: {kind}")


class RawHtmlRecord(BaseModel):
    """Schema for a raw HTML object stored as JSON in MinIO."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    url: HttpUrl
    title: str = Field(min_length=1)
    fetched_at: datetime
    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(min_length=1)
    encoding: str = Field(min_length=1)
    html: str
    text_preview: str
    etag: str | None = None
    last_modified: str | None = None
    content_hash: str = Field(min_length=1)


class RawPdfMetadataRecord(BaseModel):
    """Schema for PDF metadata stored as JSON next to the binary PDF object."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    url: HttpUrl
    filename: str = Field(min_length=1)
    fetched_at: datetime
    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(min_length=1)
    content_length: int | None = Field(default=None, ge=0)
    etag: str | None = None
    last_modified: str | None = None
    content_hash: str = Field(min_length=1)
    object_key: str = Field(min_length=1)
    metadata_object_key: str = Field(min_length=1)


class PdfTextPage(BaseModel):
    """Per-page text extraction output for a PDF."""

    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    text: str
    char_count: int = Field(ge=0)


class PdfTextRecord(BaseModel):
    """Schema for extracted text from a PDF object stored as JSON in MinIO."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_pdf_doc_id: str = Field(min_length=1)
    source_pdf_object_key: str = Field(min_length=1)
    url: HttpUrl
    extracted_at: datetime
    extract_method: str = Field(min_length=1)
    page_count: int = Field(ge=0)
    char_count: int = Field(ge=0)
    has_text_layer: bool
    full_text: str
    pages: list[PdfTextPage]
