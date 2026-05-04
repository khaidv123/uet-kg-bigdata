import sqlite3
from datetime import date

from data_ingestion.bootstrap import ensure_crawl_state_schema, render_storage_prefixes


def test_render_storage_prefixes_uses_expected_layout() -> None:
    prefixes = render_storage_prefixes(
        {
            "placeholder_name": ".keep",
            "raw_prefix_templates": {
                "html": "html/{yyyy}/{mm}/{dd}/",
                "pdf": "pdf/{yyyy}/{mm}/{dd}/",
            },
            "meta_prefixes": {
                "crawl_state": "metadata/crawl_state/",
                "ingestion_logs": "logs/ingestion/",
            },
        },
        date(2026, 4, 17),
    )

    assert prefixes["raw"] == [
        "html/2026/04/17/.keep",
        "pdf/2026/04/17/.keep",
    ]
    assert prefixes["meta"] == [
        "metadata/crawl_state/.keep",
        "logs/ingestion/.keep",
    ]


def test_ensure_crawl_state_schema_creates_expected_columns(tmp_path) -> None:
    db_path = tmp_path / "crawl_state.db"

    summary = ensure_crawl_state_schema(db_path)

    with sqlite3.connect(db_path) as connection:
        columns = [
            row[1]
            for row in connection.execute("PRAGMA table_info(crawl_state)").fetchall()
        ]

    assert summary["table"] == "crawl_state"
    assert columns == [
        "url",
        "normalized_url",
        "doc_id",
        "etag",
        "last_modified",
        "content_hash",
        "fetched_at",
        "status",
        "object_key",
    ]
