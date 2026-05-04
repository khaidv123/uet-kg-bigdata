#!/usr/bin/env python3
"""Run the Phase 0 infrastructure smoke tests and write a JSON report."""

from __future__ import annotations

import argparse
import json
import logging

from data_ingestion.bootstrap import project_root, resolve_project_path
from data_ingestion.logging_utils import configure_logging
from data_ingestion.smoke_tests import run_phase0_smoke_checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="metadata/smoke_test_report.json",
        help="JSON report path, relative to the project root unless absolute.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = project_root()
    configure_logging(project_dir=root)
    logger = logging.getLogger("data_ingestion.smoke")

    report_path = resolve_project_path(args.output, base_dir=root)
    report = run_phase0_smoke_checks(report_path=report_path)

    logger.info("Phase 0 smoke checks completed: %s", report_path)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
