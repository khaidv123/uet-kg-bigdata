from datetime import datetime

from data_ingestion.contracts import (
    PDF_TEXT_REQUIRED_FIELDS,
    RAW_HTML_REQUIRED_FIELDS,
    RAW_PDF_REQUIRED_FIELDS,
    RawHtmlRecord,
    build_object_key,
)


def test_build_object_key_uses_expected_partitions() -> None:
    run_date = datetime(2026, 4, 17, 7, 30, 0)

    assert build_object_key("html_json", run_date, "UET News", "doc-001") == (
        "html/2026/04/17/uet-news/doc-001.json"
    )
    assert build_object_key("pdf_binary", run_date, "UET News", "doc-001") == (
        "pdf/2026/04/17/uet-news/doc-001.pdf"
    )
    assert build_object_key("pdf_metadata", run_date, "UET News", "doc-001") == (
        "pdf/2026/04/17/uet-news/doc-001.metadata.json"
    )
    assert build_object_key("pdf_text_json", run_date, "UET News", "doc-001") == (
        "pdf_text/2026/04/17/uet-news/doc-001.json"
    )


def test_raw_html_record_accepts_phase1_contract_shape() -> None:
    record = RawHtmlRecord(
        doc_id="doc-001",
        source_name="uet-news",
        url="https://uet.vnu.edu.vn/category/tin-tuc/example-post/",
        title="Example post",
        fetched_at="2026-04-17T07:30:00+00:00",
        status_code=200,
        content_type="text/html; charset=utf-8",
        encoding="utf-8",
        html="<html><body>Example</body></html>",
        text_preview="Example",
        etag="etag-1",
        last_modified="Fri, 17 Apr 2026 07:00:00 GMT",
        content_hash="sha256:abc123",
    )

    assert record.doc_id == "doc-001"
    assert tuple(RAW_HTML_REQUIRED_FIELDS) == (
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
    assert "metadata_object_key" in RAW_PDF_REQUIRED_FIELDS
    assert "pages" in PDF_TEXT_REQUIRED_FIELDS
