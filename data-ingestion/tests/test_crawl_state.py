from data_ingestion.crawl_state import CrawlStateStore


def test_crawl_state_store_fetch_and_upsert_round_trip(tmp_path) -> None:
    db_path = tmp_path / "crawl_state.db"
    store = CrawlStateStore(db_path)

    store.upsert(
        {
            "url": "https://uet.vnu.edu.vn/category/tin-tuc/post-1/",
            "normalized_url": "https://uet.vnu.edu.vn/category/tin-tuc/post-1",
            "doc_id": "doc-001",
            "etag": "etag-1",
            "last_modified": "Fri, 17 Apr 2026 07:00:00 GMT",
            "content_hash": "hash-1",
            "fetched_at": "2026-04-17T07:30:00+00:00",
            "status": "NEW",
            "object_key": "html/2026/04/17/uet-news/doc-001.json",
        }
    )

    row = store.fetch("https://uet.vnu.edu.vn/category/tin-tuc/post-1")

    assert row is not None
    assert row["doc_id"] == "doc-001"
    assert row["status"] == "NEW"


def test_crawl_state_store_evaluate_change_uses_content_hash_first(tmp_path) -> None:
    db_path = tmp_path / "crawl_state.db"
    store = CrawlStateStore(db_path)
    normalized_url = "https://uet.vnu.edu.vn/category/tin-tuc/post-1"

    store.upsert(
        {
            "url": "https://uet.vnu.edu.vn/category/tin-tuc/post-1/",
            "normalized_url": normalized_url,
            "doc_id": "doc-001",
            "etag": "etag-1",
            "last_modified": "Fri, 17 Apr 2026 07:00:00 GMT",
            "content_hash": "hash-1",
            "fetched_at": "2026-04-17T07:30:00+00:00",
            "status": "NEW",
            "object_key": "html/2026/04/17/uet-news/doc-001.json",
        }
    )

    unchanged = store.evaluate_change(
        normalized_url,
        etag="etag-1",
        last_modified="Fri, 17 Apr 2026 07:00:00 GMT",
        content_hash="hash-1",
    )
    updated = store.evaluate_change(
        normalized_url,
        etag="etag-1",
        last_modified="Fri, 17 Apr 2026 08:00:00 GMT",
        content_hash="hash-2",
    )

    assert unchanged.status == "SKIPPED_UNCHANGED"
    assert "content_hash" in unchanged.matched_on
    assert updated.status == "UPDATED"


def test_crawl_state_store_evaluate_change_uses_headers_as_fallback(tmp_path) -> None:
    db_path = tmp_path / "crawl_state.db"
    store = CrawlStateStore(db_path)
    normalized_url = "https://uet.vnu.edu.vn/category/tin-tuc/post-2"

    store.upsert(
        {
            "url": "https://uet.vnu.edu.vn/category/tin-tuc/post-2/",
            "normalized_url": normalized_url,
            "doc_id": "doc-002",
            "etag": "etag-2",
            "last_modified": "Fri, 17 Apr 2026 07:00:00 GMT",
            "content_hash": None,
            "fetched_at": "2026-04-17T07:30:00+00:00",
            "status": "NEW",
            "object_key": "html/2026/04/17/uet-news/doc-002.json",
        }
    )

    unchanged = store.evaluate_change(
        normalized_url,
        etag="etag-2",
        last_modified="Fri, 17 Apr 2026 07:00:00 GMT",
        content_hash=None,
    )
    updated = store.evaluate_change(
        normalized_url,
        etag="etag-3",
        last_modified="Fri, 17 Apr 2026 08:00:00 GMT",
        content_hash=None,
    )

    assert unchanged.status == "SKIPPED_UNCHANGED"
    assert set(unchanged.matched_on) == {"etag", "last_modified"}
    assert updated.status == "UPDATED"
