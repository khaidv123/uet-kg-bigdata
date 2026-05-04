"""Placeholder spider that reads seeds from the centralized source registry."""

from __future__ import annotations

from pathlib import Path

import scrapy

from data_ingestion.source_registry import enabled_sources, load_source_registry

from ..items import SourcePageItem
from ..utils import extract_text_preview


def _as_bool(raw_value: str | bool | None) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


class SourceRegistryPlaceholderSpider(scrapy.Spider):
    name = "source_registry_placeholder"
    custom_settings = {
        "LOG_LEVEL": "INFO",
    }

    def __init__(
        self,
        source_id: str | None = None,
        registry_path: str | None = None,
        dry_run: str | bool | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.dry_run = _as_bool(dry_run)
        self.registry = load_source_registry(path=registry_path)
        self.sources = [
            source
            for source in enabled_sources(self.registry)
            if source_id is None or source.id == source_id
        ]
        if not self.sources:
            raise ValueError(f"No enabled sources found for source_id={source_id!r}")

        self.allowed_domains = sorted(
            {
                domain
                for source in self.sources
                for domain in source.allowed_domains
            }
        )
        self.start_urls = [
            str(url)
            for source in self.sources
            for url in source.start_urls
        ]

    def start_requests(self):
        for source in self.sources:
            for start_url in source.start_urls:
                request_url = str(start_url)
                if self.dry_run:
                    request_url = self._fixture_uri()

                yield scrapy.Request(
                    url=request_url,
                    callback=self.parse_source_page,
                    dont_filter=True,
                    meta={
                        "source_id": source.id,
                        "source_type": source.source_type,
                        "seed_url": str(start_url),
                        "canonical_url": str(start_url),
                    },
                )

    async def start(self):
        for request in self.start_requests():
            yield request

    def parse_source_page(self, response: scrapy.http.Response):
        title = response.css("title::text").get() or response.meta["source_id"]
        body_text = " ".join(response.css("body ::text").getall())
        internal_links = [
            response.urljoin(href)
            for href in response.css("a::attr(href)").getall()
            if href
        ]

        yield SourcePageItem(
            source_name=response.meta["source_id"],
            source_type=response.meta["source_type"],
            seed_url=response.meta["seed_url"],
            fetch_url=response.url,
            url=response.meta["canonical_url"],
            title=title.strip(),
            text_preview=extract_text_preview(body_text),
            status_code=response.status,
            content_type=response.headers.get("Content-Type", b"").decode("utf-8", "ignore"),
            discovered_link_count=len(internal_links),
        )

    def _fixture_uri(self) -> str:
        fixture_path = (
            Path(__file__).resolve().parents[2] / "fixtures" / "placeholder_source.html"
        )
        return fixture_path.as_uri()
