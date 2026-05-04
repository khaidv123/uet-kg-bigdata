"""Path helpers for MinIO/S3A-backed Phase 2 jobs."""

from __future__ import annotations

from pyspark.sql import SparkSession


def build_s3a_uri(bucket: str, relative_path: str) -> str:
    clean_path = relative_path.strip("/")
    return f"s3a://{bucket}/{clean_path}"


def build_run_path(base_path: str, run_id: str, filename: str | None = None) -> str:
    clean_base = base_path.strip("/")
    path = f"{clean_base}/run_id={run_id}"
    if filename:
        return f"{path}/{filename}"
    return path


def resolve_latest_run_id(spark: SparkSession, bucket: str, base_path: str) -> str:
    jvm = spark.sparkContext._jvm
    hadoop_conf = spark.sparkContext._jsc.hadoopConfiguration()
    qualified = jvm.org.apache.hadoop.fs.Path(build_s3a_uri(bucket, base_path))
    fs = qualified.getFileSystem(hadoop_conf)

    if not fs.exists(qualified):
        raise FileNotFoundError(f"Input base path does not exist: {qualified}")

    statuses = fs.listStatus(qualified)
    run_ids = []
    for status in statuses:
        if not status.isDirectory():
            continue
        name = status.getPath().getName()
        if name.startswith("run_id="):
            run_ids.append(name.split("=", 1)[1])

    if not run_ids:
        raise FileNotFoundError(f"No run_id directories found under {qualified}")
    return sorted(run_ids)[-1]
