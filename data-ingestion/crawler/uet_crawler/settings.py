"""Scrapy settings for the UET crawler project."""

import os

BOT_NAME = "uet_crawler"

SPIDER_MODULES = ["uet_crawler.spiders"]
NEWSPIDER_MODULE = "uet_crawler.spiders"

USER_AGENT = "data-ingestion-uet-mvp/0.1 (+https://uet.vnu.edu.vn)"
ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 1.0
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 4
RETRY_ENABLED = True
RETRY_TIMES = int(os.environ.get("CRAWLER_RETRY_TIMES", "4"))
DOWNLOAD_TIMEOUT = int(os.environ.get("CRAWLER_DOWNLOAD_TIMEOUT", "45"))
COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False
LOG_LEVEL = "INFO"
FEED_EXPORT_ENCODING = "utf-8"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"

ITEM_PIPELINES = {
    "uet_crawler.pipelines.NormalizeSourcePagePipeline": 300,
    "uet_crawler.pipelines.PersistHtmlItemPipeline": 500,
    "uet_crawler.pipelines.PersistPdfReferencePipeline": 600,
}
