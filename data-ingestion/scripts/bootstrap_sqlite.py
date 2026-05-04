#!/usr/bin/env python3
"""Initialize the SQLite crawl-state database used for incremental ingest."""

from __future__ import annotations

import argparse
import json
import logging
import os

from data_ingestion.bootstrap import ensure_crawl_state_schema, project_root, resolve_project_path, write_schema_snapshot
from data_ingestion.logging_utils import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        default=os.environ.get("METADATA_DB_PATH", "metadata/crawl_state.db"),
        help="SQLite database path, relative to the project root unless absolute.",
    )
    parser.add_argument(
        "--schema-output",
        default="metadata/crawl_state_schema.json",
        help="JSON snapshot path for the crawl state schema contract.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = project_root()
    configure_logging(project_dir=root)
    logger = logging.getLogger("data_ingestion.bootstrap.sqlite")

    db_path = resolve_project_path(args.db_path, base_dir=root)
    schema_output = resolve_project_path(args.schema_output, base_dir=root)

    summary = ensure_crawl_state_schema(db_path)
    write_schema_snapshot(schema_output)
    summary["schema_snapshot"] = str(schema_output.resolve())

    logger.info("Initialized SQLite crawl state store: %s", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
