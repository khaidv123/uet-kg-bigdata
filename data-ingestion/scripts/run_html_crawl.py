"""Run the Scrapy HTML crawl once and emit a JSON summary for orchestration."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from data_ingestion.bootstrap import project_root, resolve_project_path
from data_ingestion.ingestion_runtime import (
    normalize_source_selector,
    resolve_selected_sources,
    summarize_feed_file,
    summarize_pdf_manifest,
    summarize_scrapy_log_text,
    write_json_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", default=os.environ.get("INGESTION_SOURCE_ID") or None)
    parser.add_argument(
        "--registry-path",
        default=os.environ.get("INGESTION_REGISTRY_PATH", "/opt/project/config/sources.yaml"),
    )
    parser.add_argument(
        "--max-pages-per-source",
        type=int,
        default=int(os.environ.get("INGESTION_MAX_PAGES_PER_SOURCE", "20")),
    )
    parser.add_argument("--run-index", type=int, default=1)
    parser.add_argument(
        "--feed-output",
        required=True,
        help="JSON feed path written by Scrapy.",
    )
    parser.add_argument(
        "--report-output",
        required=True,
        help="JSON summary path written after the crawl finishes.",
    )
    parser.add_argument(
        "--db-path",
        default=os.environ.get("METADATA_DB_PATH", "metadata/crawl_state.db"),
    )
    parser.add_argument(
        "--pdf-manifest-path",
        default=os.environ.get("PDF_URL_DISCOVERY_PATH", "metadata/discovered_pdf_urls.jsonl"),
    )
    parser.add_argument(
        "--log-output",
        default=None,
        help="Optional path for the captured Scrapy stdout/stderr log.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_selector = normalize_source_selector(args.source_id)
    root = project_root()
    crawler_root = root / "crawler"
    feed_output = resolve_project_path(args.feed_output, base_dir=root)
    report_output = resolve_project_path(args.report_output, base_dir=root)
    db_path = resolve_project_path(args.db_path, base_dir=root)
    pdf_manifest_path = resolve_project_path(args.pdf_manifest_path, base_dir=root)
    log_output = (
        resolve_project_path(args.log_output, base_dir=root)
        if args.log_output
        else report_output.with_suffix(".log")
    )

    feed_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    log_output.parent.mkdir(parents=True, exist_ok=True)

    selected_sources = resolve_selected_sources(
        source_id=source_selector,
        registry_path=args.registry_path,
    )

    command = [
        sys.executable,
        "-m",
        "scrapy",
        "crawl",
        "html_source_registry",
        "-a",
        f"max_pages_per_source={args.max_pages_per_source}",
        "-O",
        str(feed_output),
        "-s",
        "LOG_LEVEL=ERROR",
    ]
    if source_selector:
        command.extend(["-a", f"source_id={source_selector}"])
    if args.registry_path:
        command.extend(["-a", f"registry_path={args.registry_path}"])

    env = os.environ.copy()
    env["METADATA_DB_PATH"] = str(db_path)
    env["PDF_URL_DISCOVERY_PATH"] = str(pdf_manifest_path)
    env["PYTHONPATH"] = env.get("PYTHONPATH", "/opt/project/src")

    started_at = datetime.now(timezone.utc)
    process = subprocess.run(
        command,
        cwd=crawler_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    finished_at = datetime.now(timezone.utc)
    log_text = "\n".join(part for part in (process.stdout, process.stderr) if part).strip()
    if log_text:
        log_output.write_text(log_text + "\n", encoding="utf-8")
    else:
        log_output.write_text("", encoding="utf-8")

    feed_summary = summarize_feed_file(feed_output)
    pdf_summary = summarize_pdf_manifest(pdf_manifest_path)
    network_error_summary = summarize_scrapy_log_text(log_text)

    payload = {
        "run_index": args.run_index,
        "source_id": source_selector,
        "selected_sources": selected_sources,
        "max_pages_per_source": args.max_pages_per_source,
        "feed_output_path": str(feed_output),
        "report_output_path": str(report_output),
        "db_path": str(db_path),
        "pdf_manifest_path": str(pdf_manifest_path),
        "log_output_path": str(log_output),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "scrapy_return_code": process.returncode,
        **feed_summary,
        "pdf_manifest_summary": pdf_summary,
        "network_error_summary": network_error_summary,
    }
    write_json_file(report_output, payload)

    if process.returncode != 0:
        raise SystemExit(process.returncode)
    print(report_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
