"""
GraphFrames comprehensive analysis on KG triplets.
Input:  /data/output/triplets_extracted.csv (35MB, 218k rows)
Output: /data/output/graph_analysis/ (Parquet + metrics)

Run via Docker:
  docker compose -f analysis/docker-compose.graphx.yml run --rm spark-submit-graphx \
    /opt/spark/bin/spark-submit \
      --packages graphframes:graphframes:0.8.3-spark3.5-s_2.12 \
      --driver-memory 4g \
      /workspace/analysis/jobs/02_full_analysis.py
"""
import json, time, os, sys
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import *

OUT = "/data/output/graph_analysis"
TIMING = {}


def timed(label):
    class Timer:
        def __enter__(self):
            self.t = time.time()
            print(f"\n{'='*60}\n  START: {label}\n{'='*60}", flush=True)
            return self
        def __exit__(self, *a):
            elapsed = time.time() - self.t
            TIMING[label] = round(elapsed, 2)
            print(f"  DONE: {label} ({elapsed:.1f}s)", flush=True)
    return Timer()


def main():
    spark = (SparkSession.builder
        .appName("KG-GraphX-Analysis")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.checkpoint.dir", "/tmp/graphx-ckpt")
        .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    spark.sparkContext.setCheckpointDir("/tmp/graphx-ckpt")

    metrics = {}
    t_total = time.time()

    # ── 1. Load CSV ──────────────────────────────────────────
    with timed("01_load_csv"):
        raw = (spark.read
            .option("header", "true")
            .option("inferSchema", "false")
            .csv("/data/output/triplets_extracted.csv"))
        raw = raw.filter(F.col("head").isNotNull() & F.col("tail").isNotNull() & F.col("relation").isNotNull())
        raw.cache()
        total = raw.count()
        metrics["total_triplets"] = total
        print(f"  Loaded {total:,} triplets")

        raw.groupBy("stage").count().orderBy(F.desc("count")).show(truncate=False)
        raw.groupBy("source").count().orderBy(F.desc("count")).show(truncate=False)

    # ── 2. Build GraphFrame ──────────────────────────────────
    with timed("02_build_graph"):
        heads = raw.select(F.col("head").alias("name")).distinct()
        tails = raw.select(F.col("tail").alias("name")).distinct()
        all_names = heads.union(tails).distinct()
        vertices = all_names.withColumn("id", F.col("name")).select("id", "name")
        vertices.cache()
        num_v = vertices.count()
        metrics["num_vertices"] = num_v
        print(f"  Vertices: {num_v:,}")

        edges = raw.select(
            F.col("head").alias("src"),
            F.col("tail").alias("dst"),
            F.col("relation"),
            F.col("stage"),
            F.col("source"),
        )
        edges.cache()
        num_e = edges.count()
        metrics["num_edges"] = num_e
        print(f"  Edges: {num_e:,}")

        from graphframes import GraphFrame
        g = GraphFrame(vertices, edges)

        # Distinct edges
        distinct_edges = edges.select("src", "dst", "relation").distinct().count()
        metrics["num_distinct_edges"] = distinct_edges
        print(f"  Distinct (src,dst,rel): {distinct_edges:,}")

    # ── 3. Degree Distribution ───────────────────────────────
    with timed("03_degree_distribution"):
        in_deg = g.inDegrees
        out_deg = g.outDegrees
        tot_deg = g.degrees

        deg = (tot_deg
            .join(in_deg, "id", "left")
            .join(out_deg, "id", "left")
            .na.fill(0))
        deg.cache()

        stats = deg.agg(
            F.max("degree").alias("max"),
            F.avg("degree").alias("avg"),
            F.percentile_approx("degree", 0.5).alias("median"),
            F.percentile_approx("degree", 0.95).alias("p95"),
            F.percentile_approx("degree", 0.99).alias("p99"),
            F.max("inDegree").alias("max_in"),
            F.max("outDegree").alias("max_out"),
        ).collect()[0]

        for k in ["max", "avg", "median", "p95", "p99", "max_in", "max_out"]:
            v = stats[k]
            metrics[f"degree_{k}"] = round(float(v), 2) if v else 0
        print(f"  Max degree: {stats['max']}, Avg: {stats['avg']:.2f}, Median: {stats['median']}, P95: {stats['p95']}, P99: {stats['p99']}")

        print("\n  Top-20 nodes by degree:")
        deg.orderBy(F.desc("degree")).show(20, truncate=50)

        # Histogram
        deg_hist = deg.groupBy("degree").count().orderBy("degree")
        deg_hist.coalesce(1).write.mode("overwrite").csv(f"{OUT}/degree_distribution", header=True)

    # ── 4. PageRank ──────────────────────────────────────────
    with timed("04_pagerank"):
        pr = g.pageRank(resetProbability=0.15, maxIter=20)
        pr_v = pr.vertices.select("id", "name", "pagerank").orderBy(F.desc("pagerank"))
        pr_v.cache()
        print("  Top-30 by PageRank:")
        pr_v.show(30, truncate=60)
        pr_v.coalesce(1).write.mode("overwrite").csv(f"{OUT}/pagerank", header=True)
        top10 = pr_v.limit(10).collect()
        metrics["top10_pagerank"] = [{"name": r["name"], "pr": round(float(r["pagerank"]), 6)} for r in top10]

    # ── 5. Connected Components ──────────────────────────────
    with timed("05_connected_components"):
        cc = g.connectedComponents()
        cc_sizes = cc.groupBy("component").agg(F.count("*").alias("size")).orderBy(F.desc("size"))
        cc_sizes.cache()
        n_cc = cc_sizes.count()
        giant = cc_sizes.first()
        metrics["num_connected_components"] = n_cc
        metrics["giant_component_size"] = int(giant["size"])
        metrics["giant_component_pct"] = round(100.0 * giant["size"] / num_v, 2)
        print(f"  Components: {n_cc}")
        print(f"  Giant component: {giant['size']:,} nodes ({metrics['giant_component_pct']}%)")
        print("\n  Top-10 component sizes:")
        cc_sizes.show(10)
        cc_sizes.coalesce(1).write.mode("overwrite").csv(f"{OUT}/connected_components", header=True)

    # ── 6. Strongly Connected Components ─────────────────────
    with timed("06_strongly_connected_components"):
        scc = g.stronglyConnectedComponents(maxIter=10)
        scc_sizes = scc.groupBy("component").agg(F.count("*").alias("size")).orderBy(F.desc("size"))
        scc_sizes.cache()
        n_scc = scc_sizes.count()
        largest_scc = scc_sizes.first()
        metrics["num_scc"] = n_scc
        metrics["largest_scc_size"] = int(largest_scc["size"])
        print(f"  SCC count: {n_scc}")
        print(f"  Largest SCC: {largest_scc['size']:,} nodes")
        scc_sizes.show(10)
        scc_sizes.coalesce(1).write.mode("overwrite").csv(f"{OUT}/scc", header=True)

    # ── 7. Triangle Count ────────────────────────────────────
    with timed("07_triangle_count"):
        tc = g.triangleCount()
        tc_sum = tc.agg(F.sum("count")).collect()[0][0] or 0
        total_tri = int(tc_sum) // 3
        metrics["total_triangles"] = total_tri
        print(f"  Total triangles: {total_tri:,}")
        print("\n  Top-20 nodes by triangle participation:")
        tc.orderBy(F.desc("count")).select("id", "count").show(20, truncate=50)
        tc.orderBy(F.desc("count")).limit(100).coalesce(1).write.mode("overwrite").csv(f"{OUT}/triangle_count", header=True)

    # ── 8. Label Propagation (Community Detection) ───────────
    with timed("08_label_propagation"):
        lpa = g.labelPropagation(maxIter=5)
        comm_sizes = lpa.groupBy("label").agg(F.count("*").alias("size")).orderBy(F.desc("size"))
        comm_sizes.cache()
        n_comm = comm_sizes.count()
        metrics["num_lpa_communities"] = n_comm
        print(f"  Communities: {n_comm}")
        print("\n  Top-15 community sizes:")
        comm_sizes.show(15)
        comm_sizes.coalesce(1).write.mode("overwrite").csv(f"{OUT}/communities", header=True)

        # Save community assignments for top communities
        top_labels = [r["label"] for r in comm_sizes.limit(5).collect()]
        for label_val in top_labels:
            members = lpa.filter(F.col("label") == label_val).select("id").limit(50).collect()
            print(f"\n  Community {label_val} ({len(members)} sample members):")
            for m in members[:10]:
                print(f"    - {m['id']}")

    # ── 9. Shortest Paths ────────────────────────────────────
    with timed("09_shortest_paths"):
        landmarks = [r["name"] for r in top10[:5]]
        print(f"  Landmarks (top-5 PageRank): {landmarks}")
        sp = g.shortestPaths(landmarks=landmarks)
        sp_sample = sp.filter(F.size("distances") > 0).limit(20)
        print("  Sample shortest paths:")
        sp_sample.select("id", "distances").show(20, truncate=80)

    # ── 10. Motif Finding ────────────────────────────────────
    with timed("10_motif_finding"):
        # 2-hop chains: A → B → C
        chains = g.find("(a)-[e1]->(b); (b)-[e2]->(c)")
        chain_count = chains.count()
        metrics["two_hop_chains"] = chain_count
        print(f"  2-hop chains (A→B→C): {chain_count:,}")
        print("\n  Sample chains:")
        chains.select(
            F.col("a.name").alias("A"),
            F.col("e1.relation").alias("R1"),
            F.col("b.name").alias("B"),
            F.col("e2.relation").alias("R2"),
            F.col("c.name").alias("C"),
        ).limit(20).show(truncate=35)

        # Reciprocal edges: A ↔ B
        recip = g.find("(a)-[e1]->(b); (b)-[e2]->(a)")
        recip_count = recip.count()
        metrics["reciprocal_edges"] = recip_count
        print(f"  Reciprocal edges (A↔B): {recip_count:,}")
        if recip_count > 0:
            recip.select(
                F.col("a.name").alias("A"),
                F.col("e1.relation").alias("A→B"),
                F.col("b.name").alias("B"),
                F.col("e2.relation").alias("B→A"),
            ).distinct().limit(15).show(truncate=40)

    # ── 11. Relation Analysis ────────────────────────────────
    with timed("11_relation_analysis"):
        rel_stats = (edges.groupBy("relation")
            .agg(
                F.count("*").alias("count"),
                F.countDistinct("src").alias("heads"),
                F.countDistinct("dst").alias("tails"),
                F.countDistinct(F.concat_ws("||", "src", "dst")).alias("pairs"),
            )
            .withColumn("specificity", F.round(F.col("count") / F.col("pairs"), 2))
            .orderBy(F.desc("count")))
        rel_stats.cache()
        n_rel = rel_stats.count()
        metrics["num_relation_types"] = n_rel
        print(f"  Relation types: {n_rel:,}")
        print("\n  Top-30 relations:")
        rel_stats.show(30, truncate=50)
        rare = rel_stats.filter(F.col("count") == 1).count()
        metrics["rare_relations_count1"] = rare
        print(f"  Rare relations (count=1): {rare}")
        rel_stats.coalesce(1).write.mode("overwrite").csv(f"{OUT}/relation_stats", header=True)

    # ── 12. Quality Checks ───────────────────────────────────
    with timed("12_quality_checks"):
        self_loops = edges.filter(F.col("src") == F.col("dst")).count()
        metrics["self_loops"] = self_loops
        print(f"  Self-loops: {self_loops}")

        leaf = deg.filter(F.col("degree") == 1).count()
        metrics["leaf_nodes"] = leaf
        metrics["leaf_node_pct"] = round(100.0 * leaf / num_v, 2) if num_v > 0 else 0
        print(f"  Leaf nodes (degree=1): {leaf} ({metrics['leaf_node_pct']}%)")

        density = num_e / (num_v * (num_v - 1)) if num_v > 1 else 0
        metrics["graph_density"] = round(density, 8)
        print(f"  Graph density: {density:.8f}")

        # Nodes only as head vs only as tail
        only_head = edges.select("src").distinct().subtract(edges.select("dst").distinct()).count()
        only_tail = edges.select("dst").distinct().subtract(edges.select("src").distinct()).count()
        metrics["nodes_only_head"] = only_head
        metrics["nodes_only_tail"] = only_tail
        print(f"  Nodes only appearing as head: {only_head}")
        print(f"  Nodes only appearing as tail: {only_tail}")

    # ── 13. PageRank per Stage ───────────────────────────────
    with timed("13_pagerank_per_stage"):
        stage_pr = {}
        for stage in ["entity_relation", "event_entity", "event_relation"]:
            se = edges.filter(F.col("stage") == stage)
            cnt = se.count()
            if cnt == 0:
                continue
            sv_ids = se.select(F.col("src").alias("id")).union(se.select(F.col("dst").alias("id"))).distinct()
            sv = vertices.join(sv_ids, "id", "inner")
            sg = GraphFrame(sv, se)
            spr = sg.pageRank(resetProbability=0.15, maxIter=10)
            top5 = spr.vertices.orderBy(F.desc("pagerank")).limit(5).collect()
            stage_pr[stage] = [{"name": r["name"], "pr": round(float(r["pagerank"]), 4)} for r in top5]
            print(f"\n  === {stage} ({cnt:,} edges) Top-5 PageRank ===")
            spr.vertices.orderBy(F.desc("pagerank")).select("name", "pagerank").show(10, truncate=50)
        metrics["pagerank_per_stage"] = stage_pr

    # ── 14. Save all metrics ─────────────────────────────────
    total_elapsed = time.time() - t_total
    TIMING["total"] = round(total_elapsed, 2)
    metrics["timing_seconds"] = TIMING

    metrics_path = f"{OUT}/metrics.json"
    # Write metrics as local JSON file
    os.makedirs(OUT, exist_ok=True)
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n\n{'='*60}")
    print(f"  ALL ANALYSIS COMPLETE — {total_elapsed:.1f}s total")
    print(f"{'='*60}")
    print(f"\nMetrics saved to {metrics_path}")
    print("\nKey metrics:")
    for k, v in sorted(metrics.items()):
        if k not in ("top10_pagerank", "pagerank_per_stage", "timing_seconds"):
            print(f"  {k}: {v}")
    print("\nTiming:")
    for k, v in sorted(TIMING.items()):
        print(f"  {k}: {v}s")

    spark.stop()


if __name__ == "__main__":
    main()
