import json

from data_ingestion.ingestion_runtime import (
    build_quality_report,
    build_ingestion_manifest,
    normalize_source_selector,
    summarize_scrapy_log_text,
    summarize_feed_file,
    summarize_pdf_manifest,
)


def test_summarize_feed_file_counts_record_types_and_statuses(tmp_path) -> None:
    feed_path = tmp_path / "feed.json"
    feed_path.write_text(
        json.dumps(
            [
                {"record_type": "html_page", "crawl_status": "NEW"},
                {"record_type": "html_page", "crawl_status": "SKIPPED_UNCHANGED"},
                {"record_type": "pdf_reference", "crawl_status": "DISCOVERED_PDF"},
            ]
        ),
        encoding="utf-8",
    )

    summary = summarize_feed_file(feed_path)

    assert summary["item_count"] == 3
    assert summary["record_type_counts"]["html_page"] == 2
    assert summary["record_type_counts"]["pdf_reference"] == 1
    assert summary["crawl_status_counts"]["SKIPPED_UNCHANGED"] == 1


def test_summarize_pdf_manifest_counts_lines(tmp_path) -> None:
    manifest_path = tmp_path / "discovered_pdf_urls.jsonl"
    manifest_path.write_text('{"url": "a"}\n{"url": "b"}\n', encoding="utf-8")

    summary = summarize_pdf_manifest(manifest_path)

    assert summary["pdf_url_count"] == 2


def test_build_ingestion_manifest_aggregates_reports() -> None:
    manifest = build_ingestion_manifest(
        dag_id="phase1_ingestion_dag",
        selected_sources=[{"id": "uet-news"}],
        crawl_reports=[
            {
                "record_type_counts": {"html_page": 3, "pdf_reference": 1},
                "crawl_status_counts": {"NEW": 2, "SKIPPED_UNCHANGED": 1, "DISCOVERED_PDF": 1},
            },
            {
                "record_type_counts": {"html_page": 2},
                "crawl_status_counts": {"UPDATED": 1, "SKIPPED_UNCHANGED": 1},
                "network_error_summary": {
                    "timeout_count": 2,
                    "retry_exhausted_count": 1,
                    "download_error_count": 1,
                    "robots_error_count": 0,
                    "failed_url_count": 1,
                    "failed_urls": ["https://tuyensinh.uet.vnu.edu.vn/category/tin-tuyen-sinh"],
                    "total_failures": 2,
                },
            },
        ],
        pdf_summary={"pdf_url_count": 4, "path": "metadata/discovered_pdf_urls.jsonl"},
        max_pages_per_source=20,
        iterations=2,
    )

    assert manifest["html_items"] == 5
    assert manifest["html_fetched"] == 5
    assert manifest["html_new"] == 2
    assert manifest["html_updated"] == 1
    assert manifest["html_skipped_unchanged"] == 2
    assert manifest["pdf_reference_items_in_feed"] == 1
    assert manifest["pdf_url_discovered"] == 4
    assert manifest["pdf_downloaded"] == 0
    assert manifest["pdf_text_extracted"] == 0
    assert manifest["pdf_scanned_detected"] == 0
    assert manifest["errors"] == 2
    assert manifest["deferred_pdf_processing"] is True
    assert manifest["pdf_manifest_summary"]["pdf_url_count"] == 4
    assert manifest["crawl_status_counts"]["SKIPPED_UNCHANGED"] == 2
    assert manifest["network_error_summary"]["timeout_count"] == 2
    assert manifest["network_error_summary"]["failed_url_count"] == 1


def test_build_quality_report_passes_with_complete_html_objects() -> None:
    manifest = {
        "html_fetched": 2,
        "html_skipped_unchanged": 1,
        "pdf_url_discovered": 0,
        "pdf_downloaded": 0,
        "pdf_text_extracted": 0,
        "pdf_scanned_detected": 0,
        "errors": 0,
        "deferred_pdf_processing": True,
    }
    feed_records = [
        {
            "record_type": "html_page",
            "title": "Page A",
            "text_preview": "Lorem ipsum",
            "object_key": "html/2026/04/18/uet-news/doc-a.json",
        },
        {
            "record_type": "html_page",
            "title": "Page B",
            "text_preview": "Dolor sit amet",
            "object_key": "html/2026/04/18/uet-news/doc-b.json",
        },
    ]
    stored_html_objects = {
        "html/2026/04/18/uet-news/doc-a.json": {
            "doc_id": "doc-a",
            "source_name": "uet-news",
            "url": "https://uet.vnu.edu.vn/a",
            "title": "Page A",
            "fetched_at": "2026-04-18T00:00:00+00:00",
            "status_code": 200,
            "content_type": "text/html",
            "encoding": "utf-8",
            "html": "<html>A</html>",
            "text_preview": "Lorem ipsum",
            "etag": None,
            "last_modified": None,
            "content_hash": "hash-a",
        },
        "html/2026/04/18/uet-news/doc-b.json": {
            "doc_id": "doc-b",
            "source_name": "uet-news",
            "url": "https://uet.vnu.edu.vn/b",
            "title": "Page B",
            "fetched_at": "2026-04-18T00:00:00+00:00",
            "status_code": 200,
            "content_type": "text/html",
            "encoding": "utf-8",
            "html": "<html>B</html>",
            "text_preview": "Dolor sit amet",
            "etag": None,
            "last_modified": None,
            "content_hash": "hash-b",
        },
    }

    report = build_quality_report(
        manifest=manifest,
        feed_records=feed_records,
        stored_html_objects=stored_html_objects,
        object_fetch_failures=[],
        thresholds={
            "min_title_ratio": 0.95,
            "min_text_preview_ratio": 0.95,
            "min_metadata_completeness_ratio": 1.0,
            "min_object_match_ratio": 1.0,
            "max_error_count": 0,
        },
        manifest_path="metadata/ingestion_manifest.json",
        quality_report_path="metadata/ingestion_quality_report.json",
    )

    assert report["status"] == "passed"
    assert report["html_with_title_ratio"] == 1.0
    assert report["html_with_text_preview_ratio"] == 1.0
    assert report["metadata_complete_ratio"] == 1.0
    assert report["minio_object_match_ratio"] == 1.0
    assert report["errors"] == 0


def test_build_quality_report_fails_when_objects_are_missing() -> None:
    manifest = {
        "html_fetched": 1,
        "html_skipped_unchanged": 0,
        "pdf_url_discovered": 0,
        "pdf_downloaded": 0,
        "pdf_text_extracted": 0,
        "pdf_scanned_detected": 0,
        "errors": 0,
        "deferred_pdf_processing": True,
    }
    feed_records = [
        {
            "record_type": "html_page",
            "title": "Page A",
            "text_preview": "Lorem ipsum",
            "object_key": "html/2026/04/18/uet-news/doc-a.json",
        }
    ]

    report = build_quality_report(
        manifest=manifest,
        feed_records=feed_records,
        stored_html_objects={},
        object_fetch_failures=[{"object_key": "html/2026/04/18/uet-news/doc-a.json", "error": "missing"}],
        thresholds={
            "min_title_ratio": 0.95,
            "min_text_preview_ratio": 0.95,
            "min_metadata_completeness_ratio": 1.0,
            "min_object_match_ratio": 1.0,
            "max_error_count": 0,
        },
        manifest_path="metadata/ingestion_manifest.json",
        quality_report_path="metadata/ingestion_quality_report.json",
    )

    assert report["status"] == "failed"
    assert report["minio_object_found_count"] == 0
    assert report["minio_object_match_ratio"] == 0.0
    assert report["errors"] == 1
    assert any("object match ratio" in failure for failure in report["failures"])


def test_summarize_scrapy_log_text_counts_timeout_and_failed_urls() -> None:
    summary = summarize_scrapy_log_text(
        """
        2026-04-17 16:59:20 [scrapy.downloadermiddlewares.retry] ERROR: Gave up retrying <GET https://tuyensinh.uet.vnu.edu.vn/robots.txt> (failed 3 times): User timeout caused connection failure.
        2026-04-17 16:59:20 [scrapy.downloadermiddlewares.robotstxt] ERROR: Error downloading <GET https://tuyensinh.uet.vnu.edu.vn/category/tin-tuyen-sinh> : User timeout caused connection failure.
        twisted.internet.error.TimeoutError: User timeout caused connection failure.
        scrapy.exceptions.DownloadTimeoutError: User timeout caused connection failure.
        """
    )

    assert summary["timeout_count"] == 2
    assert summary["retry_exhausted_count"] == 1
    assert summary["download_error_count"] == 1
    assert summary["robots_error_count"] == 1
    assert summary["failed_url_count"] == 2


def test_normalize_source_selector_treats_all_as_none() -> None:
    assert normalize_source_selector(None) is None
    assert normalize_source_selector("") is None
    assert normalize_source_selector("all") is None
    assert normalize_source_selector("*") is None
    assert normalize_source_selector("uet-news") == "uet-news"
