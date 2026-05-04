from types import SimpleNamespace

from uet_crawler.items import PdfReferenceItem
from uet_crawler.pipelines import PersistPdfReferencePipeline


def test_pdf_reference_pipeline_writes_deduped_manifest(tmp_path, monkeypatch) -> None:
    manifest_path = tmp_path / "discovered_pdf_urls.jsonl"
    monkeypatch.setenv("PDF_URL_DISCOVERY_PATH", str(manifest_path))

    pipeline = PersistPdfReferencePipeline.from_crawler(
        SimpleNamespace(spider=SimpleNamespace(dry_run=False))
    )
    pipeline.open_spider()

    first_item = PdfReferenceItem(
        record_type="pdf_reference",
        source_name="uet-news",
        source_type="news",
        seed_url="https://uet.vnu.edu.vn/category/tin-tuc/",
        parent_url="https://uet.vnu.edu.vn/category/tin-tuc/",
        url="https://uet.vnu.edu.vn/wp-content/uploads/example.pdf",
        normalized_url="https://uet.vnu.edu.vn/wp-content/uploads/example.pdf",
        doc_id="doc-pdf-001",
        discovered_at="2026-04-17T08:00:00+00:00",
    )
    second_item = PdfReferenceItem(
        record_type="pdf_reference",
        source_name="uet-news",
        source_type="news",
        seed_url="https://uet.vnu.edu.vn/category/tin-tuc/",
        parent_url="https://uet.vnu.edu.vn/category/tin-tuc/",
        url="https://uet.vnu.edu.vn/wp-content/uploads/example.pdf",
        normalized_url="https://uet.vnu.edu.vn/wp-content/uploads/example.pdf",
        doc_id="doc-pdf-001",
        discovered_at="2026-04-17T08:05:00+00:00",
    )

    pipeline.process_item(first_item)
    pipeline.process_item(second_item)
    pipeline.close_spider()

    lines = manifest_path.read_text(encoding="utf-8").strip().splitlines()

    assert len(lines) == 1
    assert first_item["crawl_status"] == "DISCOVERED_PDF"
    assert second_item["crawl_status"] == "SKIPPED_ALREADY_DISCOVERED"
