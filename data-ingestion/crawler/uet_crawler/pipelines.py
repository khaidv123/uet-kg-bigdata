"""Item pipelines for the UET crawler project."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import boto3
from itemadapter import ItemAdapter

from data_ingestion.bootstrap import (
    bucket_targets_from_env,
    normalize_endpoint_url,
    project_root,
    resolve_project_path,
)
from data_ingestion.contracts import RawHtmlRecord, build_object_key
from data_ingestion.crawl_state import CrawlStateStore

from .utils import build_doc_id, extract_text_preview, normalize_url


class NormalizeSourcePagePipeline:
    """Populate stable URL and identifier fields for placeholder crawl items."""

    def process_item(self, item):
        adapter = ItemAdapter(item)
        source_name = adapter.get("source_name") or "unknown-source"
        canonical_url = adapter.get("url") or adapter.get("seed_url") or ""
        normalized_url = normalize_url(canonical_url)

        adapter["normalized_url"] = normalized_url
        adapter["doc_id"] = build_doc_id(normalized_url, source_name)
        try:
            adapter["text_preview"] = extract_text_preview(adapter.get("text_preview") or "")
        except KeyError:
            pass

        return item


class PersistHtmlItemPipeline:
    """Validate and persist raw HTML records into MinIO and crawl_state."""

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.crawler = crawler
        return pipeline

    def open_spider(self) -> None:
        self.enabled = not getattr(self.crawler.spider, "dry_run", False)
        if not self.enabled:
            self.client = None
            self.state_store = None
            return

        env = os.environ
        root = project_root()
        buckets = bucket_targets_from_env(env)

        self.raw_bucket = buckets.raw
        self.client = boto3.client(
            "s3",
            endpoint_url=normalize_endpoint_url(env.get("MINIO_ENDPOINT", "minio:9000")),
            aws_access_key_id=env.get("MINIO_ROOT_USER", "minioadmin"),
            aws_secret_access_key=env.get("MINIO_ROOT_PASSWORD", "change-me"),
            region_name="us-east-1",
        )
        db_path = resolve_project_path(env.get("METADATA_DB_PATH", "metadata/crawl_state.db"), base_dir=root)
        self.state_store = CrawlStateStore(db_path)

    def process_item(self, item):
        adapter = ItemAdapter(item)
        if adapter.get("record_type") != "html_page":
            return item
        if not self.enabled:
            return item

        record = RawHtmlRecord(
            doc_id=adapter["doc_id"],
            source_name=adapter["source_name"],
            url=adapter["url"],
            title=adapter["title"],
            fetched_at=adapter["fetched_at"],
            status_code=adapter["status_code"],
            content_type=adapter["content_type"] or "text/html",
            encoding=adapter["encoding"] or "utf-8",
            html=adapter["html"],
            text_preview=adapter["text_preview"],
            etag=adapter.get("etag"),
            last_modified=adapter.get("last_modified"),
            content_hash=adapter["content_hash"],
        )

        decision = self.state_store.evaluate_change(
            adapter["normalized_url"],
            etag=adapter.get("etag"),
            last_modified=adapter.get("last_modified"),
            content_hash=adapter["content_hash"],
        )
        status = decision.status
        object_key = build_object_key(
            "html_json",
            datetime.fromisoformat(adapter["fetched_at"]),
            adapter["source_name"],
            adapter["doc_id"],
        )

        if status == "SKIPPED_UNCHANGED" and decision.existing is not None:
            object_key = decision.existing["object_key"]

        if status != "SKIPPED_UNCHANGED":
            payload = record.model_dump(mode="json")
            self.client.put_object(
                Bucket=self.raw_bucket,
                Key=object_key,
                Body=(json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
                ContentType="application/json",
            )

        adapter["crawl_status"] = status
        adapter["object_key"] = object_key

        try:
            self.state_store.upsert(
                {
                    "url": adapter["url"],
                    "normalized_url": adapter["normalized_url"],
                    "doc_id": adapter["doc_id"],
                    "etag": adapter.get("etag"),
                    "last_modified": adapter.get("last_modified"),
                    "content_hash": adapter["content_hash"],
                    "fetched_at": adapter["fetched_at"],
                    "status": status,
                    "object_key": object_key,
                }
            )
        except Exception:
            self.state_store.upsert(
                {
                    "url": adapter["url"],
                    "normalized_url": adapter["normalized_url"],
                    "doc_id": adapter["doc_id"],
                    "etag": adapter.get("etag"),
                    "last_modified": adapter.get("last_modified"),
                    "content_hash": adapter["content_hash"],
                    "fetched_at": adapter["fetched_at"],
                    "status": "FAILED",
                    "object_key": object_key,
                }
            )
            raise

        return item


class PersistPdfReferencePipeline:
    """Persist discovered PDF URLs into a local JSONL manifest for later processing."""

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.crawler = crawler
        return pipeline

    def open_spider(self) -> None:
        self.enabled = not getattr(self.crawler.spider, "dry_run", False)
        self.seen_urls: set[str] = set()
        if not self.enabled:
            self.file_handle = None
            return

        env = os.environ
        root = project_root()
        manifest_path = resolve_project_path(
            env.get("PDF_URL_DISCOVERY_PATH", "metadata/discovered_pdf_urls.jsonl"),
            base_dir=root,
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path = manifest_path

        if manifest_path.exists():
            with manifest_path.open("r", encoding="utf-8") as existing_file:
                for line in existing_file:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    normalized_url = payload.get("normalized_url")
                    if normalized_url:
                        self.seen_urls.add(normalized_url)

        self.file_handle = manifest_path.open("a", encoding="utf-8")

    def close_spider(self) -> None:
        if getattr(self, "file_handle", None) is not None:
            self.file_handle.close()

    def process_item(self, item):
        adapter = ItemAdapter(item)
        if adapter.get("record_type") != "pdf_reference":
            return item
        if not self.enabled:
            return item

        normalized_url = adapter["normalized_url"]
        if normalized_url in self.seen_urls:
            adapter["crawl_status"] = "SKIPPED_ALREADY_DISCOVERED"
            adapter["object_key"] = str(self.manifest_path.resolve())
            return item

        payload = {
            "record_type": "pdf_reference",
            "source_name": adapter["source_name"],
            "source_type": adapter["source_type"],
            "seed_url": adapter["seed_url"],
            "parent_url": adapter["parent_url"],
            "url": adapter["url"],
            "normalized_url": normalized_url,
            "doc_id": adapter["doc_id"],
            "discovered_at": adapter["discovered_at"],
        }
        self.file_handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.file_handle.flush()
        self.seen_urls.add(normalized_url)
        adapter["crawl_status"] = "DISCOVERED_PDF"
        adapter["object_key"] = str(self.manifest_path.resolve())
        return item
