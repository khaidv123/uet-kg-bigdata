#!/usr/bin/env python3
"""
KG Graph Analysis using NetworkX (equivalent algorithms to Spark GraphX).
Runs inside Docker container: kg-graphx-analysis

Input:  /data/output/triplets_extracted.csv
Output: /data/output/graph_analysis/
"""
import csv, json, os, time, sys
from collections import Counter, defaultdict

import networkx as nx
import pandas as pd

INPUT  = "/data/output/triplets_extracted.csv"
OUT    = "/data/output/graph_analysis"
os.makedirs(OUT, exist_ok=True)

TIMING = {}
metrics = {}


def timed(label):
    class T:
        def __enter__(self):
            self.t = time.time()
            print(f"\n{'='*60}\n  START: {label}\n{'='*60}", flush=True)
            return self
        def __exit__(self, *a):
            e = time.time() - self.t
            TIMING[label] = round(e, 2)
            print(f"  DONE: {label}  ({e:.1f}s)", flush=True)
    return T()


def save_csv(data, filename, headers):
    path = os.path.join(OUT, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(data)
    print(f"    → Saved {path} ({len(data)} rows)", flush=True)


# ═══════════════════════════════════════════════════════════════
#  1. Load CSV
# ═══════════════════════════════════════════════════════════════
with timed("01_load_csv"):
    df = pd.read_csv(INPUT, dtype=str).fillna("")
    total = len(df)
    metrics["total_triplets"] = total
    print(f"  Loaded {total:,} triplets")

    stage_counts = df["stage"].value_counts().to_dict()
    source_counts = df["source"].value_counts().to_dict()
    metrics["stage_distribution"] = stage_counts
    metrics["source_distribution"] = source_counts
    print(f"  Stages: {stage_counts}")
    print(f"  Sources: {source_counts}")

# ═══════════════════════════════════════════════════════════════
#  2. Build MultiDiGraph
# ═══════════════════════════════════════════════════════════════
with timed("02_build_graph"):
    G = nx.MultiDiGraph()
    for _, row in df.iterrows():
        G.add_edge(row["head"], row["tail"],
                   relation=row["relation"],
                   stage=row["stage"],
                   source=row["source"])

    num_v = G.number_of_nodes()
    num_e = G.number_of_edges()
    metrics["num_vertices"] = num_v
    metrics["num_edges"] = num_e
    print(f"  Vertices: {num_v:,}")
    print(f"  Edges:    {num_e:,}")

    # Also build a simple DiGraph (for algorithms that need it)
    SG = nx.DiGraph()
    for u, v, d in G.edges(data=True):
        if SG.has_edge(u, v):
            SG[u][v]["weight"] = SG[u][v].get("weight", 1) + 1
        else:
            SG.add_edge(u, v, weight=1, relation=d["relation"])
    metrics["num_distinct_edges"] = SG.number_of_edges()
    print(f"  Distinct directed edges: {SG.number_of_edges():,}")

# ═══════════════════════════════════════════════════════════════
#  3. Degree Distribution
# ═══════════════════════════════════════════════════════════════
with timed("03_degree_distribution"):
    in_deg  = dict(G.in_degree())
    out_deg = dict(G.out_degree())
    tot_deg = dict(G.degree())

    degs = sorted(tot_deg.values(), reverse=True)
    metrics["degree_max"] = degs[0]
    metrics["degree_avg"] = round(sum(degs) / len(degs), 2)
    metrics["degree_median"] = degs[len(degs)//2]
    p95_idx = int(len(degs) * 0.05)
    p99_idx = int(len(degs) * 0.01)
    metrics["degree_p95"] = degs[p95_idx]
    metrics["degree_p99"] = degs[p99_idx]
    metrics["max_in_degree"] = max(in_deg.values())
    metrics["max_out_degree"] = max(out_deg.values())

    print(f"  Max: {metrics['degree_max']}, Avg: {metrics['degree_avg']}, "
          f"Median: {metrics['degree_median']}, P95: {metrics['degree_p95']}, P99: {metrics['degree_p99']}")

    # Top-20
    top20 = sorted(tot_deg.items(), key=lambda x: -x[1])[:20]
    print("\n  Top-20 nodes by degree:")
    for name, d in top20:
        print(f"    {d:>6}  in={in_deg[name]:<5} out={out_deg[name]:<5}  {name[:60]}")

    # Histogram
    deg_hist = Counter(tot_deg.values())
    save_csv(sorted(deg_hist.items()), "degree_distribution.csv", ["degree", "count"])

# ═══════════════════════════════════════════════════════════════
#  4. PageRank
# ═══════════════════════════════════════════════════════════════
with timed("04_pagerank"):
    pr = nx.pagerank(SG, alpha=0.85, max_iter=100)
    pr_sorted = sorted(pr.items(), key=lambda x: -x[1])

    print("  Top-30 by PageRank:")
    for name, score in pr_sorted[:30]:
        print(f"    {score:.6f}  {name[:70]}")

    metrics["top10_pagerank"] = [{"name": n, "pagerank": round(s, 6)} for n, s in pr_sorted[:10]]
    save_csv([(n, round(s, 8)) for n, s in pr_sorted[:200]], "pagerank_top200.csv", ["node", "pagerank"])

# ═══════════════════════════════════════════════════════════════
#  5. Connected Components (undirected view)
# ═══════════════════════════════════════════════════════════════
with timed("05_connected_components"):
    UG = G.to_undirected()
    components = list(nx.connected_components(UG))
    comp_sizes = sorted([len(c) for c in components], reverse=True)

    metrics["num_connected_components"] = len(components)
    metrics["giant_component_size"] = comp_sizes[0]
    metrics["giant_component_pct"] = round(100.0 * comp_sizes[0] / num_v, 2)

    print(f"  Components: {len(components)}")
    print(f"  Giant: {comp_sizes[0]:,} nodes ({metrics['giant_component_pct']}%)")
    print(f"  Top-10 sizes: {comp_sizes[:10]}")

    save_csv([(i, s) for i, s in enumerate(comp_sizes)],
             "connected_components.csv", ["component_id", "size"])

# ═══════════════════════════════════════════════════════════════
#  6. Strongly Connected Components
# ═══════════════════════════════════════════════════════════════
with timed("06_strongly_connected_components"):
    sccs = list(nx.strongly_connected_components(SG))
    scc_sizes = sorted([len(c) for c in sccs], reverse=True)

    metrics["num_scc"] = len(sccs)
    metrics["largest_scc_size"] = scc_sizes[0]

    print(f"  SCC count: {len(sccs)}")
    print(f"  Largest SCC: {scc_sizes[0]:,} nodes")
    print(f"  Top-10 sizes: {scc_sizes[:10]}")

    save_csv([(i, s) for i, s in enumerate(scc_sizes[:100])],
             "scc_sizes.csv", ["scc_id", "size"])

# ═══════════════════════════════════════════════════════════════
#  7. Triangle Count & Clustering Coefficient
# ═══════════════════════════════════════════════════════════════
with timed("07_triangles_clustering"):
    # Convert to undirected simple graph for triangle counting
    SU = nx.Graph(SG)
    triangles = nx.triangles(SU)
    total_tri = sum(triangles.values()) // 3
    metrics["total_triangles"] = total_tri
    print(f"  Total triangles: {total_tri:,}")

    # Local clustering
    clustering = nx.clustering(SU)
    avg_cc = nx.average_clustering(SU)
    metrics["avg_clustering_coefficient"] = round(avg_cc, 6)
    print(f"  Avg clustering coefficient: {avg_cc:.6f}")

    # Top triangle nodes
    top_tri = sorted(triangles.items(), key=lambda x: -x[1])[:20]
    print("\n  Top-20 nodes by triangle participation:")
    for n, c in top_tri:
        print(f"    {c:>6}  cc={clustering[n]:.4f}  {n[:60]}")

    save_csv([(n, c, round(clustering[n], 6)) for n, c in sorted(triangles.items(), key=lambda x: -x[1])[:200]],
             "triangle_count.csv", ["node", "triangles", "clustering_coeff"])

# ═══════════════════════════════════════════════════════════════
#  8. Community Detection (Label Propagation)
# ═══════════════════════════════════════════════════════════════
with timed("08_community_detection"):
    communities = list(nx.community.label_propagation_communities(SU))
    comm_sizes = sorted([len(c) for c in communities], reverse=True)

    metrics["num_communities_lpa"] = len(communities)
    print(f"  Communities (LPA): {len(communities)}")
    print(f"  Top-15 sizes: {comm_sizes[:15]}")

    # Save top communities with members
    comm_data = []
    for i, comm in enumerate(sorted(communities, key=len, reverse=True)[:50]):
        for member in list(comm)[:100]:
            comm_data.append((i, len(comm), member))
    save_csv(comm_data, "communities_lpa.csv", ["community_id", "community_size", "member"])

# ═══════════════════════════════════════════════════════════════
#  9. Betweenness Centrality (sampled)
# ═══════════════════════════════════════════════════════════════
with timed("09_betweenness_centrality"):
    # Sample-based for performance (k=500 random nodes)
    k = min(500, num_v)
    bc = nx.betweenness_centrality(SG, k=k, normalized=True)
    bc_sorted = sorted(bc.items(), key=lambda x: -x[1])

    print(f"  Top-20 bridge nodes (betweenness, sampled k={k}):")
    for n, s in bc_sorted[:20]:
        print(f"    {s:.6f}  {n[:60]}")

    metrics["top10_betweenness"] = [{"name": n, "score": round(s, 6)} for n, s in bc_sorted[:10]]
    save_csv([(n, round(s, 8)) for n, s in bc_sorted[:200]],
             "betweenness_centrality.csv", ["node", "betweenness"])

# ═══════════════════════════════════════════════════════════════
#  10. HITS (Hub & Authority)
# ═══════════════════════════════════════════════════════════════
with timed("10_hits"):
    hubs, auths = nx.hits(SG, max_iter=100, normalized=True)
    hub_sorted  = sorted(hubs.items(), key=lambda x: -x[1])
    auth_sorted = sorted(auths.items(), key=lambda x: -x[1])

    print("  Top-15 Hubs:")
    for n, s in hub_sorted[:15]:
        print(f"    {s:.6f}  {n[:60]}")

    print("\n  Top-15 Authorities:")
    for n, s in auth_sorted[:15]:
        print(f"    {s:.6f}  {n[:60]}")

    metrics["top10_hubs"]        = [{"name": n, "score": round(s, 6)} for n, s in hub_sorted[:10]]
    metrics["top10_authorities"] = [{"name": n, "score": round(s, 6)} for n, s in auth_sorted[:10]]
    save_csv([(n, round(h, 8), round(auths[n], 8)) for n, h in hub_sorted[:200]],
             "hits_scores.csv", ["node", "hub_score", "authority_score"])

# ═══════════════════════════════════════════════════════════════
#  11. Relation Analysis
# ═══════════════════════════════════════════════════════════════
with timed("11_relation_analysis"):
    rel_counter = Counter()
    rel_pairs   = defaultdict(set)
    rel_heads   = defaultdict(set)
    rel_tails   = defaultdict(set)

    for _, row in df.iterrows():
        r = row["relation"]
        rel_counter[r] += 1
        rel_pairs[r].add((row["head"], row["tail"]))
        rel_heads[r].add(row["head"])
        rel_tails[r].add(row["tail"])

    n_rel = len(rel_counter)
    metrics["num_relation_types"] = n_rel
    print(f"  Relation types: {n_rel:,}")

    rel_data = []
    for r, cnt in rel_counter.most_common():
        pairs = len(rel_pairs[r])
        spec = round(cnt / pairs, 2) if pairs > 0 else 0
        rel_data.append((r, cnt, len(rel_heads[r]), len(rel_tails[r]), pairs, spec))

    print("\n  Top-30 relations:")
    for r, cnt, h, t, p, sp in rel_data[:30]:
        print(f"    {cnt:>6}  heads={h:<5} tails={t:<5} pairs={p:<5} spec={sp:<5}  {r[:50]}")

    rare = sum(1 for _, c in rel_counter.items() if c == 1)
    metrics["rare_relations_count1"] = rare
    print(f"\n  Rare relations (count=1): {rare}")

    save_csv(rel_data, "relation_stats.csv",
             ["relation", "count", "distinct_heads", "distinct_tails", "distinct_pairs", "specificity"])

# ═══════════════════════════════════════════════════════════════
#  12. Reciprocal Edges
# ═══════════════════════════════════════════════════════════════
with timed("12_reciprocal_edges"):
    reciprocal = []
    for u, v in SG.edges():
        if SG.has_edge(v, u):
            r1 = SG[u][v].get("relation", "?")
            r2 = SG[v][u].get("relation", "?")
            reciprocal.append((u, r1, v, r2))

    metrics["reciprocal_edge_pairs"] = len(reciprocal) // 2  # each pair counted twice
    print(f"  Reciprocal edge pairs: {len(reciprocal)//2}")
    if reciprocal:
        print("\n  Sample reciprocal edges:")
        for a, r1, b, r2 in reciprocal[:15]:
            print(f"    {a[:30]} --[{r1[:15]}]--> {b[:30]} --[{r2[:15]}]--> (back)")

    save_csv(reciprocal[:500], "reciprocal_edges.csv", ["node_a", "relation_a_to_b", "node_b", "relation_b_to_a"])

# ═══════════════════════════════════════════════════════════════
#  13. Quality Checks
# ═══════════════════════════════════════════════════════════════
with timed("13_quality_checks"):
    self_loops = sum(1 for u, v in G.edges() if u == v)
    metrics["self_loops"] = self_loops
    print(f"  Self-loops: {self_loops}")

    leaf = sum(1 for n in G.nodes() if G.degree(n) == 1)
    metrics["leaf_nodes"] = leaf
    metrics["leaf_node_pct"] = round(100.0 * leaf / num_v, 2)
    print(f"  Leaf nodes (degree=1): {leaf} ({metrics['leaf_node_pct']}%)")

    density = nx.density(G)
    metrics["graph_density"] = round(density, 8)
    print(f"  Graph density: {density:.8f}")

    only_head = set(dict(G.out_degree()).keys()) - set(dict(G.in_degree()).keys())
    only_tail = set(dict(G.in_degree()).keys()) - set(dict(G.out_degree()).keys())
    # Actually for MultiDiGraph all nodes appear, so count by zero-degree
    only_head = sum(1 for n in G.nodes() if G.in_degree(n) == 0 and G.out_degree(n) > 0)
    only_tail = sum(1 for n in G.nodes() if G.out_degree(n) == 0 and G.in_degree(n) > 0)
    metrics["nodes_only_as_head"] = only_head
    metrics["nodes_only_as_tail"] = only_tail
    print(f"  Nodes only as head (source-only): {only_head}")
    print(f"  Nodes only as tail (sink-only):   {only_tail}")

# ═══════════════════════════════════════════════════════════════
#  14. PageRank per Stage (subgraph analysis)
# ═══════════════════════════════════════════════════════════════
with timed("14_pagerank_per_stage"):
    stage_pr = {}
    for stage in ["entity_relation", "event_entity", "event_relation"]:
        sub_df = df[df["stage"] == stage]
        if len(sub_df) == 0:
            continue
        sg = nx.DiGraph()
        for _, row in sub_df.iterrows():
            if sg.has_edge(row["head"], row["tail"]):
                sg[row["head"]][row["tail"]]["weight"] += 1
            else:
                sg.add_edge(row["head"], row["tail"], weight=1)

        spr = nx.pagerank(sg, alpha=0.85, max_iter=50)
        top5 = sorted(spr.items(), key=lambda x: -x[1])[:10]
        stage_pr[stage] = [{"name": n, "pagerank": round(s, 6)} for n, s in top5]
        print(f"\n  === {stage} ({len(sub_df):,} edges, {sg.number_of_nodes():,} nodes) ===")
        print(f"  Top-10 PageRank:")
        for n, s in top5:
            print(f"    {s:.6f}  {n[:60]}")

    metrics["pagerank_per_stage"] = stage_pr

# ═══════════════════════════════════════════════════════════════
#  15. Diameter Estimation (BFS from sample)
# ═══════════════════════════════════════════════════════════════
with timed("15_diameter_estimation"):
    # Estimate diameter using eccentricity of top PageRank nodes on giant component
    giant_nodes = max(components, key=len)
    giant_sub = SU.subgraph(giant_nodes).copy()
    print(f"  Giant component: {giant_sub.number_of_nodes():,} nodes, {giant_sub.number_of_edges():,} edges")

    # BFS from 10 random high-PageRank nodes
    sample_nodes = [n for n, _ in pr_sorted[:10] if n in giant_nodes][:5]
    max_dist = 0
    for seed in sample_nodes:
        lengths = nx.single_source_shortest_path_length(giant_sub, seed)
        d = max(lengths.values()) if lengths else 0
        if d > max_dist:
            max_dist = d
        print(f"    BFS from '{seed[:40]}': max_dist={d}, avg={sum(lengths.values())/len(lengths):.1f}")

    metrics["estimated_diameter"] = max_dist
    print(f"  Estimated diameter (lower bound): {max_dist}")

# ═══════════════════════════════════════════════════════════════
#  SAVE FINAL METRICS + REPORT
# ═══════════════════════════════════════════════════════════════
total_elapsed = time.time() - TIMING.get("_start", time.time())
# recalculate total from sum
total_elapsed = sum(TIMING.values())
TIMING["_total"] = round(total_elapsed, 2)
metrics["timing_seconds"] = TIMING

with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False, default=str)

print(f"\n\n{'='*60}")
print(f"  ALL ANALYSIS COMPLETE — {total_elapsed:.1f}s total")
print(f"{'='*60}")
print(f"\nTiming breakdown:")
for k, v in sorted(TIMING.items()):
    if not k.startswith("_"):
        print(f"  {k}: {v}s")
print(f"\nResults saved to {OUT}/")
