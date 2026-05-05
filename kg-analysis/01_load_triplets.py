"""
Job 01: Load raw triplets JSON → Parquet (intermediate storage)
=============================================================
Input:  /data/input/kg_raw_triplets_4k.json
Output: /data/output/triplets_parquet/
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

def main():
    spark = (
        SparkSession.builder
        .appName("GraphX-Analysis-01-LoadTriplets")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    print("=== Loading triplets JSON ===")
    raw = spark.read.json("/data/input/kg_raw_triplets_4k.json")

    triplets = raw.select(
        F.col("head").cast("string"),
        F.col("relation").cast("string"),
        F.col("tail").cast("string"),
        F.col("stage").cast("string"),
        F.col("metadata.source").cast("string").alias("source"),
        F.col("metadata.doc_index").cast("int").alias("doc_index"),
        F.col("metadata.chunk_index").cast("int").alias("chunk_index"),
    ).filter(
        F.col("head").isNotNull() &
        F.col("tail").isNotNull() &
        F.col("relation").isNotNull()
    )

    triplets = triplets.cache()
    total = triplets.count()
    print(f"=== Total triplets loaded: {total} ===")

    # Basic stats
    print("\n--- Stage distribution ---")
    triplets.groupBy("stage").count().orderBy(F.desc("count")).show(truncate=False)

    print("\n--- Source distribution ---")
    triplets.groupBy("source").count().orderBy(F.desc("count")).show(truncate=False)

    print("\n--- Distinct heads / tails / relations ---")
    print(f"  Distinct heads:     {triplets.select('head').distinct().count()}")
    print(f"  Distinct tails:     {triplets.select('tail').distinct().count()}")
    print(f"  Distinct relations: {triplets.select('relation').distinct().count()}")

    # Save Parquet
    out_path = "/data/output/triplets_parquet"
    print(f"\n=== Saving Parquet to {out_path} ===")
    triplets.write.mode("overwrite").parquet(out_path)

    print("=== Done ===")
    spark.stop()

if __name__ == "__main__":
    main()
