from datetime import datetime
import os

from pyspark.sql import SparkSession


def main() -> None:
    run_id = os.getenv("PHASE2_RUN_ID") or datetime.utcnow().strftime("smoke-%Y%m%d%H%M%S")
    bucket = os.getenv("MINIO_BUCKET", "kg-construct-phase2")
    output_path = f"s3a://{bucket}/meta/phase2/smoke/{run_id}"

    spark = (
        SparkSession.builder.appName("phase2-smoke-s3a-minio")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )

    rows = [
        (1, "phase2", "ok"),
        (2, "s3a", "ok"),
        (3, run_id, "ok"),
    ]

    df = spark.createDataFrame(rows, ["id", "component", "status"])
    df.write.mode("overwrite").parquet(output_path)

    read_back = spark.read.parquet(output_path)
    count = read_back.count()
    print(f"SMOKE_WRITE_PATH={output_path}")
    print(f"SMOKE_ROW_COUNT={count}")

    spark.stop()


if __name__ == "__main__":
    main()
