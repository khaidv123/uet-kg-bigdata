"""Evaluate ingestion quality for a run and fail on threshold breaches."""

from __future__ import annotations

import argparse
import os

from data_ingestion.ingestion_runtime import (
    build_quality_report,
    fetch_html_objects_from_minio,
    html_object_keys_from_records,
    load_feed_records,
    load_json_file,
    write_json_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-path",
        required=True,
        help="Path to the ingestion manifest JSON file.",
    )
    parser.add_argument(
        "--quality-report-path",
        required=True,
        help="Path to the output quality report JSON file.",
    )
    parser.add_argument(
        "--feed-path",
        action="append",
        dest="feed_paths",
        required=True,
        help="JSON feed path produced by a crawl run. Repeat for multiple iterations.",
    )
    parser.add_argument(
        "--min-title-ratio",
        type=float,
        default=float(os.environ.get("QUALITY_MIN_TITLE_RATIO", "0.95")),
    )
    parser.add_argument(
        "--min-text-preview-ratio",
        type=float,
        default=float(os.environ.get("QUALITY_MIN_TEXT_PREVIEW_RATIO", "0.95")),
    )
    parser.add_argument(
        "--min-metadata-completeness-ratio",
        type=float,
        default=float(os.environ.get("QUALITY_MIN_METADATA_COMPLETENESS_RATIO", "1.0")),
    )
    parser.add_argument(
        "--min-object-match-ratio",
        type=float,
        default=float(os.environ.get("QUALITY_MIN_OBJECT_MATCH_RATIO", "1.0")),
    )
    parser.add_argument(
        "--max-error-count",
        type=int,
        default=int(os.environ.get("QUALITY_MAX_ERROR_COUNT", "0")),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    manifest = load_json_file(args.manifest_path)
    if not isinstance(manifest, dict):
        raise TypeError(f"Expected object manifest payload in {args.manifest_path}")

    feed_records = load_feed_records(args.feed_paths)
    object_keys = html_object_keys_from_records(feed_records)
    stored_html_objects, object_fetch_failures = fetch_html_objects_from_minio(object_keys)

    thresholds = {
        "min_title_ratio": args.min_title_ratio,
        "min_text_preview_ratio": args.min_text_preview_ratio,
        "min_metadata_completeness_ratio": args.min_metadata_completeness_ratio,
        "min_object_match_ratio": args.min_object_match_ratio,
        "max_error_count": args.max_error_count,
    }
    quality_report = build_quality_report(
        manifest=manifest,
        feed_records=feed_records,
        stored_html_objects=stored_html_objects,
        object_fetch_failures=object_fetch_failures,
        thresholds=thresholds,
        manifest_path=args.manifest_path,
        quality_report_path=args.quality_report_path,
    )
    write_json_file(args.quality_report_path, quality_report)

    manifest["quality_report_path"] = args.quality_report_path
    manifest["quality_status"] = quality_report["status"]
    manifest["quality_thresholds"] = quality_report["thresholds"]
    manifest["quality_summary"] = {
        "html_with_title_ratio": quality_report["html_with_title_ratio"],
        "html_with_text_preview_ratio": quality_report["html_with_text_preview_ratio"],
        "metadata_complete_ratio": quality_report["metadata_complete_ratio"],
        "minio_object_match_ratio": quality_report["minio_object_match_ratio"],
        "errors": quality_report["errors"],
    }
    write_json_file(args.manifest_path, manifest)

    print(args.quality_report_path)
    return 0 if quality_report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
