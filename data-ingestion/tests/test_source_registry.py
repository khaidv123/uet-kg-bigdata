from data_ingestion.source_registry import enabled_sources, load_source_registry


def test_load_source_registry_uses_defaults_from_yaml(tmp_path) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        """
version: 1
scope:
  owner: Demo
  objective: Demo crawl
  root_domain: example.org
defaults:
  allowed_domains:
    - example.org
  deny_patterns:
    - /ignore/
  pdf_patterns:
    - \\.pdf$
sources:
  - id: demo-news
    source_type: news
    display_name: Demo news
    description: Demo news source
    start_urls:
      - https://example.org/news/
    crawl_interval_hours: 6
""".strip()
        + "\n",
        encoding="utf-8",
    )

    registry = load_source_registry(config_path)

    source = registry.sources[0]
    assert source.allowed_domains == ["example.org"]
    assert source.deny_patterns == ["/ignore/"]
    assert source.pdf_patterns == ["\\.pdf$"]


def test_load_real_source_registry_returns_enabled_sources() -> None:
    registry = load_source_registry()

    assert [source.id for source in enabled_sources(registry)] == [
        "uet-news",
        "uet-events",
        "uet-notices",
        "uet-admissions",
        "uet-scholarships",
        "uet-public-documents",
    ]
