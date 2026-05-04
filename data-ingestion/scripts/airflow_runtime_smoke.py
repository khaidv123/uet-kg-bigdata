#!/usr/bin/env python3
"""Run a lightweight Airflow runtime smoke check from the scripts mount."""

from __future__ import annotations

import argparse
import json

from data_ingestion.airflow_smoke import run_runtime_smoke


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="/opt/project/config/airflow_smoke_config.json",
        help="Path to the JSON smoke-check config file.",
    )
    parser.add_argument(
        "--output",
        default="/opt/project/metadata/airflow_smoke_report.json",
        help="Optional path for the generated smoke-check report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_runtime_smoke(args.config, report_path=args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
