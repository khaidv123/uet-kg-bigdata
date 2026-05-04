"""Scrapy items for the UET crawler project."""

import scrapy


class SourcePageItem(scrapy.Item):
    record_type = scrapy.Field()
    source_name = scrapy.Field()
    source_type = scrapy.Field()
    seed_url = scrapy.Field()
    fetch_url = scrapy.Field()
    url = scrapy.Field()
    normalized_url = scrapy.Field()
    doc_id = scrapy.Field()
    title = scrapy.Field()
    text_preview = scrapy.Field()
    html = scrapy.Field()
    internal_links = scrapy.Field()
    status_code = scrapy.Field()
    content_type = scrapy.Field()
    encoding = scrapy.Field()
    etag = scrapy.Field()
    last_modified = scrapy.Field()
    content_hash = scrapy.Field()
    fetched_at = scrapy.Field()
    crawl_status = scrapy.Field()
    object_key = scrapy.Field()
    discovered_link_count = scrapy.Field()


class PdfReferenceItem(scrapy.Item):
    record_type = scrapy.Field()
    source_name = scrapy.Field()
    source_type = scrapy.Field()
    seed_url = scrapy.Field()
    parent_url = scrapy.Field()
    url = scrapy.Field()
    normalized_url = scrapy.Field()
    doc_id = scrapy.Field()
    discovered_at = scrapy.Field()
    crawl_status = scrapy.Field()
    object_key = scrapy.Field()
