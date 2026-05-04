"""HTML crawler that reads seeds from the centralized source registry."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone

import scrapy

from data_ingestion.ingestion_runtime import normalize_source_selector
from data_ingestion.source_registry import enabled_sources, load_source_registry

from ..items import PdfReferenceItem, SourcePageItem
from ..utils import (
    extract_text_preview,
    has_allowed_host,
    is_followable_html_url,
    is_pdf_url,
    is_asset_url,
    candidate_urls_for_matching,
    url_matches_patterns,
    normalize_url,
)


def _as_bool(raw_value: str | bool | None) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


class HtmlSourceRegistrySpider(scrapy.Spider):
    name = "html_source_registry"

    def __init__(
        self,
        source_id: str | None = None,
        registry_path: str | None = None,
        max_pages_per_source: int | str = 100,
        dry_run: str | bool | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.dry_run = _as_bool(dry_run)
        self.max_pages_per_source = int(max_pages_per_source)
        source_selector = normalize_source_selector(source_id)
        self.registry = load_source_registry(path=registry_path)
        self.sources = [
            source
            for source in enabled_sources(self.registry)
            if source_selector is None or source.id == source_selector
        ]
        if not self.sources:
            raise ValueError(f"No enabled sources found for source_id={source_selector!r}")

        self.sources_by_id = {source.id: source for source in self.sources}
        self.page_counts: dict[str, int] = defaultdict(int)
        self.scheduled_counts: dict[str, int] = defaultdict(int)
        self.seen_urls: dict[str, set[str]] = defaultdict(set)
        self.allowed_domains = sorted(
            {
                domain
                for source in self.sources
                for domain in source.allowed_domains
            }
        )
        self.start_urls = [str(url) for source in self.sources for url in source.start_urls]
        self.source_request_meta = {
            source.id: self._request_meta_for_source(source)
            for source in self.sources
        }

    def start_requests(self):
        for source in self.sources:
            for start_url in source.start_urls:
                if self.scheduled_counts[source.id] >= self.max_pages_per_source:
                    break
                canonical_url = normalize_url(str(start_url))
                self.seen_urls[source.id].add(canonical_url)
                self.scheduled_counts[source.id] += 1
                yield scrapy.Request(
                    url=canonical_url,
                    callback=self.parse_page,
                    meta={
                        "source_id": source.id,
                        "seed_url": canonical_url,
                        **self.source_request_meta[source.id],
                    },
                    dont_filter=True,
                )

    async def start(self):
        for request in self.start_requests():
            yield request

    def parse_page(self, response: scrapy.http.Response):
        source = self.sources_by_id[response.meta["source_id"]]
        normalized_url = normalize_url(response.url)
        self.page_counts[source.id] += 1

        title = self._extract_title(response)
        body_text = " ".join(response.css("body ::text").getall())
        internal_links, pdf_links = self._extract_discovered_links(response, source)
        content_hash = hashlib.sha256(response.body).hexdigest()
        fetched_at = datetime.now(timezone.utc).isoformat()

        yield SourcePageItem(
            record_type="html_page",
            source_name=source.id,
            source_type=source.source_type,
            seed_url=response.meta["seed_url"],
            fetch_url=response.url,
            url=normalized_url,
            normalized_url=normalized_url,
            doc_id="",
            title=title,
            text_preview=extract_text_preview(body_text),
            html=response.text,
            internal_links=internal_links,
            status_code=response.status,
            content_type=response.headers.get("Content-Type", b"").decode("utf-8", "ignore"),
            encoding=response.encoding or "utf-8",
            etag=response.headers.get("ETag", b"").decode("utf-8", "ignore") or None,
            last_modified=response.headers.get("Last-Modified", b"").decode("utf-8", "ignore") or None,
            content_hash=content_hash,
            fetched_at=fetched_at,
            discovered_link_count=len(internal_links),
        )

        for pdf_url in pdf_links:
            yield PdfReferenceItem(
                record_type="pdf_reference",
                source_name=source.id,
                source_type=source.source_type,
                seed_url=response.meta["seed_url"],
                parent_url=normalized_url,
                url=pdf_url,
                normalized_url=pdf_url,
                doc_id="",
                discovered_at=fetched_at,
            )

        if self.page_counts[source.id] >= self.max_pages_per_source:
            return

        for link in internal_links:
            if link in self.seen_urls[source.id]:
                continue
            if self.scheduled_counts[source.id] >= self.max_pages_per_source:
                continue
            self.seen_urls[source.id].add(link)
            self.scheduled_counts[source.id] += 1
            yield scrapy.Request(
                url=link,
                callback=self.parse_page,
                meta={
                    "source_id": source.id,
                    "seed_url": response.meta["seed_url"],
                    **self.source_request_meta[source.id],
                },
            )

    def _request_meta_for_source(self, source) -> dict[str, int]:
        if any(domain.endswith("tuyensinh.uet.vnu.edu.vn") for domain in source.allowed_domains):
            return {
                "download_timeout": 60,
                "max_retry_times": 5,
            }
        return {}

    def _extract_title(self, response: scrapy.http.Response) -> str:
        title = response.css("title::text").get()
        if title:
            return title.strip()
        heading = response.css("h1::text").get()
        if heading:
            return heading.strip()
        return normalize_url(response.url)

    def _extract_discovered_links(
        self,
        response: scrapy.http.Response,
        source,
    ) -> tuple[list[str], list[str]]:
        html_links: list[str] = []
        pdf_links: list[str] = []
        seen: set[str] = set()

        for href in response.css("a::attr(href)").getall():
            candidate = normalize_url(response.urljoin(href))
            if candidate in seen:
                continue
            if not has_allowed_host(candidate, source.allowed_domains):
                continue
            if any(
                url_matches_patterns(option, source.deny_patterns)
                for option in candidate_urls_for_matching(candidate)
            ):
                continue
            if is_pdf_url(candidate, source.pdf_patterns):
                seen.add(candidate)
                pdf_links.append(candidate)
                continue
            if is_asset_url(candidate):
                continue
            if not is_followable_html_url(
                candidate,
                allowed_domains=source.allowed_domains,
                deny_patterns=source.deny_patterns,
                pdf_patterns=source.pdf_patterns,
            ):
                continue
            seen.add(candidate)
            html_links.append(candidate)

        return html_links, pdf_links
