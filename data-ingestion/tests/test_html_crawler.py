from scrapy.http import HtmlResponse, Request

from uet_crawler.spiders.html_source_registry import HtmlSourceRegistrySpider
from uet_crawler.utils import is_followable_html_url, is_pdf_url


def test_is_followable_html_url_filters_denied_and_pdf_links() -> None:
    allowed_domains = ["uet.vnu.edu.vn"]
    deny_patterns = ["/wp-admin/", "/search/"]
    pdf_patterns = ["(?i)\\.pdf($|\\?)"]

    assert is_followable_html_url(
        "https://uet.vnu.edu.vn/category/tin-tuc/post-1/",
        allowed_domains=allowed_domains,
        deny_patterns=deny_patterns,
        pdf_patterns=pdf_patterns,
    )
    assert not is_followable_html_url(
        "https://uet.vnu.edu.vn/wp-admin/",
        allowed_domains=allowed_domains,
        deny_patterns=deny_patterns,
        pdf_patterns=pdf_patterns,
    )
    assert not is_followable_html_url(
        "https://uet.vnu.edu.vn/wp-content/uploads/example.pdf",
        allowed_domains=allowed_domains,
        deny_patterns=deny_patterns,
        pdf_patterns=pdf_patterns,
    )
    assert is_pdf_url(
        "https://uet.vnu.edu.vn/wp-content/uploads/example.pdf",
        pdf_patterns=pdf_patterns,
    )


def test_html_source_registry_spider_extracts_internal_links() -> None:
    spider = HtmlSourceRegistrySpider(source_id="uet-news", max_pages_per_source=5, dry_run=True)
    request = Request(
        url="https://uet.vnu.edu.vn/category/tin-tuc/",
        meta={"source_id": "uet-news", "seed_url": "https://uet.vnu.edu.vn/category/tin-tuc/"},
    )
    response = HtmlResponse(
        url="https://uet.vnu.edu.vn/category/tin-tuc/",
        request=request,
        body=b"""
        <html>
          <head><title>News listing</title></head>
          <body>
            <a href="/category/tin-tuc/post-1/">Post 1</a>
            <a href="/wp-content/uploads/example.pdf">PDF</a>
            <a href="https://facebook.com/uet">Facebook</a>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    results = list(spider.parse_page(response))
    item = results[0]
    pdf_item = results[1]
    follow_request = results[2]

    assert item["source_name"] == "uet-news"
    assert item["normalized_url"] == "https://uet.vnu.edu.vn/category/tin-tuc"
    assert item["discovered_link_count"] == 1
    assert item["internal_links"] == ["https://uet.vnu.edu.vn/category/tin-tuc/post-1"]
    assert pdf_item["record_type"] == "pdf_reference"
    assert pdf_item["url"] == "https://uet.vnu.edu.vn/wp-content/uploads/example.pdf"
    assert pdf_item["parent_url"] == "https://uet.vnu.edu.vn/category/tin-tuc"
    assert follow_request.url == "https://uet.vnu.edu.vn/category/tin-tuc/post-1"


def test_html_source_registry_spider_respects_max_pages_cap() -> None:
    spider = HtmlSourceRegistrySpider(source_id="uet-news", max_pages_per_source=1, dry_run=True)
    request = Request(
        url="https://uet.vnu.edu.vn/category/tin-tuc/",
        meta={"source_id": "uet-news", "seed_url": "https://uet.vnu.edu.vn/category/tin-tuc/"},
    )
    response = HtmlResponse(
        url="https://uet.vnu.edu.vn/category/tin-tuc/",
        request=request,
        body=b"""
        <html>
          <head><title>News listing</title></head>
          <body>
            <a href="/category/tin-tuc/post-1/">Post 1</a>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    spider.scheduled_counts["uet-news"] = 1
    results = list(spider.parse_page(response))

    assert len(results) == 1


def test_html_source_registry_spider_uses_higher_timeout_for_admissions_source() -> None:
    spider = HtmlSourceRegistrySpider(source_id="uet-admissions", max_pages_per_source=5, dry_run=True)
    requests = list(spider.start_requests())

    assert requests
    assert all(request.meta["download_timeout"] == 60 for request in requests)
    assert all(request.meta["max_retry_times"] == 5 for request in requests)
