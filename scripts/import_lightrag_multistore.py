#!/usr/bin/env python3
"""Load LightRAG artifacts into HDFS, Neo4j, and Elasticsearch."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def add_if_present(command: list[str], flag: str, value: str | None) -> None:
    if value:
        command.extend([flag, value])


def run_step(label: str, command: list[str]) -> None:
    print(f"\n== {label} ==")
    print(" ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="output_verson1_uet_kg_bigdata/rag_storage")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--reset", action="store_true")

    parser.add_argument("--skip-hdfs", action="store_true")
    parser.add_argument("--webhdfs-url", default=os.getenv("WEBHDFS_URL"))
    parser.add_argument("--hdfs-user", default=os.getenv("WEBHDFS_USER") or os.getenv("HDFS_USER"))
    parser.add_argument("--hdfs-raw-dir", default=os.getenv("HDFS_RAW_DIR"))

    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--neo4j-database", default=os.getenv("NEO4J_DATABASE"))
    parser.add_argument("--skip-neo4j-vectors", action="store_true")

    parser.add_argument("--skip-elasticsearch", action="store_true")
    parser.add_argument("--es-url", default=os.getenv("ELASTICSEARCH_URL"))
    parser.add_argument("--es-user", default=os.getenv("ELASTICSEARCH_USER"))
    parser.add_argument("--es-password", default=os.getenv("ELASTICSEARCH_PASSWORD"))
    parser.add_argument("--es-api-key", default=os.getenv("ELASTICSEARCH_API_KEY"))
    parser.add_argument("--es-ca-certs", default=os.getenv("ELASTICSEARCH_CA_CERTS"))
    parser.add_argument("--es-chunks-index", default=os.getenv("ES_CHUNKS_INDEX"))
    parser.add_argument("--es-entities-index", default=os.getenv("ES_ENTITIES_INDEX"))
    parser.add_argument("--skip-es-entities", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python = sys.executable

    if not args.skip_hdfs:
        command = [python, str(SCRIPTS / "import_raw_to_hdfs.py"), "--data-dir", args.data_dir]
        add_if_present(command, "--webhdfs-url", args.webhdfs_url)
        add_if_present(command, "--hdfs-user", args.hdfs_user)
        add_if_present(command, "--hdfs-raw-dir", args.hdfs_raw_dir)
        run_step("HDFS raw data", command)

    if not args.skip_neo4j:
        command = [
            python,
            str(SCRIPTS / "import_lightrag_to_neo4j.py"),
            "--data-dir",
            args.data_dir,
            "--batch-size",
            str(args.batch_size),
        ]
        add_if_present(command, "--uri", args.neo4j_uri)
        add_if_present(command, "--user", args.neo4j_user)
        add_if_present(command, "--password", args.neo4j_password)
        add_if_present(command, "--database", args.neo4j_database)
        if args.reset:
            command.append("--reset")
        if args.skip_neo4j_vectors:
            command.append("--skip-vectors")
        run_step("Neo4j graph DB", command)

    if not args.skip_elasticsearch:
        command = [
            python,
            str(SCRIPTS / "import_lightrag_to_elasticsearch.py"),
            "--data-dir",
            args.data_dir,
            "--batch-size",
            str(args.batch_size),
        ]
        add_if_present(command, "--es-url", args.es_url)
        add_if_present(command, "--es-user", args.es_user)
        add_if_present(command, "--es-password", args.es_password)
        add_if_present(command, "--es-api-key", args.es_api_key)
        add_if_present(command, "--es-ca-certs", args.es_ca_certs)
        add_if_present(command, "--chunks-index", args.es_chunks_index)
        add_if_present(command, "--entities-index", args.es_entities_index)
        if args.reset:
            command.append("--reset")
        if args.skip_es_entities:
            command.append("--skip-entities")
        run_step("Elasticsearch vector DB", command)

    print("\nMulti-store import complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
