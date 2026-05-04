#!/usr/bin/env python3
"""Upload raw LightRAG artifacts to HDFS through WebHDFS."""

from __future__ import annotations

import argparse
import os
import posixpath
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_WEBHDFS_URL = "http://localhost:9870"
DEFAULT_HDFS_RAW_DIR = "/uet-kg-bigdata/raw"


class WebHdfsClient:
    def __init__(self, base_url: str, user: str | None = None, timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.timeout = timeout
        self.session = requests.Session()

    def _url(self, hdfs_path: str) -> str:
        normalized = "/" + hdfs_path.strip("/")
        return f"{self.base_url}/webhdfs/v1{quote(normalized)}"

    def _params(self, op: str, **extra: Any) -> dict[str, Any]:
        params: dict[str, Any] = {"op": op}
        if self.user:
            params["user.name"] = self.user
        params.update({key: value for key, value in extra.items() if value is not None})
        return params

    def mkdirs(self, hdfs_path: str) -> None:
        response = self.session.put(
            self._url(hdfs_path),
            params=self._params("MKDIRS"),
            timeout=self.timeout,
        )
        response.raise_for_status()

    def create_file(self, local_path: Path, hdfs_path: str, overwrite: bool = True) -> None:
        initial = self.session.put(
            self._url(hdfs_path),
            params=self._params("CREATE", overwrite=str(overwrite).lower()),
            allow_redirects=False,
            timeout=self.timeout,
        )
        if initial.status_code in {307, 308} and initial.headers.get("Location"):
            with local_path.open("rb") as handle:
                upload = self.session.put(initial.headers["Location"], data=handle, timeout=self.timeout)
            upload.raise_for_status()
            return
        initial.raise_for_status()


def iter_files(data_dir: Path) -> list[Path]:
    return sorted(path for path in data_dir.rglob("*") if path.is_file())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="output_verson1_uet_kg_bigdata/rag_storage")
    parser.add_argument("--webhdfs-url", default=os.getenv("WEBHDFS_URL", DEFAULT_WEBHDFS_URL))
    parser.add_argument("--hdfs-user", default=os.getenv("WEBHDFS_USER") or os.getenv("HDFS_USER"))
    parser.add_argument("--hdfs-raw-dir", default=os.getenv("HDFS_RAW_DIR", DEFAULT_HDFS_RAW_DIR))
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--no-overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Show files without uploading.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"Data dir not found: {data_dir}")

    files = iter_files(data_dir)
    print("HDFS raw upload summary")
    print(f"- local data dir: {data_dir}")
    print(f"- hdfs raw dir: {args.hdfs_raw_dir}")
    print(f"- files: {len(files)}")
    if args.dry_run:
        for path in files:
            relative = path.relative_to(data_dir).as_posix()
            print(f"  {relative}")
        return 0

    client = WebHdfsClient(args.webhdfs_url, user=args.hdfs_user, timeout=args.timeout)
    client.mkdirs(args.hdfs_raw_dir)
    for path in files:
        relative = path.relative_to(data_dir).as_posix()
        target = posixpath.join(args.hdfs_raw_dir, relative)
        parent = posixpath.dirname(target)
        if parent:
            client.mkdirs(parent)
        client.create_file(path, target, overwrite=not args.no_overwrite)
        print(f"Uploaded {relative} -> {target}")

    print("HDFS raw upload complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
