from scrapy.http import HtmlResponse, Request

from uet_crawler.spiders.source_registry_placeholder import SourceRegistryPlaceholderSpider
from uet_crawler.utils import build_doc_id, normalize_url


def test_normalize_url_and_build_doc_id_are_stable() -> None:
    normalized = normalize_url("https://UET.VNU.EDU.VN/category/tin-tuc/?b=2&a=1#fragment")

    assert normalized == "https://uet.vnu.edu.vn/category/tin-tuc?a=1&b=2"
    assert build_doc_id(normalized, "uet-news") == build_doc_id(normalized, "uet-news")


def test_placeholder_spider_reads_source_registry() -> None:
    spider = SourceRegistryPlaceholderSpider(source_id="uet-news", dry_run=True)

    assert spider.allowed_domains == ["uet.vnu.edu.vn", "www.uet.vnu.edu.vn"]
    assert spider.start_urls == ["https://uet.vnu.edu.vn/category/tin-tuc/"]


def test_placeholder_spider_parses_response_into_item() -> None:
    spider = SourceRegistryPlaceholderSpider(source_id="uet-news", dry_run=True)
    request = Request(
        url="file:///tmp/placeholder_source.html",
        meta={
            "source_id": "uet-news",
            "source_type": "news",
            "seed_url": "https://uet.vnu.edu.vn/category/tin-tuc/",
            "canonical_url": "https://uet.vnu.edu.vn/category/tin-tuc/",
        },
    )
    response = HtmlResponse(
        url="file:///tmp/placeholder_source.html",
        request=request,
        body=b"""
        <html>
          <head><title>Sample source</title></head>
          <body>
            <h1>Sample source</h1>
            <p>Example body text for preview generation.</p>
            <a href="/category/tin-tuc/post-1/">Post 1</a>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    item = next(spider.parse_source_page(response))

    assert item["source_name"] == "uet-news"
    assert item["url"] == "https://uet.vnu.edu.vn/category/tin-tuc/"
    assert item["title"] == "Sample source"
    assert item["discovered_link_count"] == 1
