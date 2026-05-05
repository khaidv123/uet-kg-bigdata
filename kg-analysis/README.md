# 📊 KG Graph Analysis — Spark + GraphFrames

Phân tích đồ thị tri thức (Knowledge Graph) sử dụng **Apache Spark GraphX / GraphFrames** chạy hoàn toàn trong **Docker**.

## Kiến trúc

```
analysis/
├── docker-compose.graphx.yml      # Spark cluster (master + worker + submit)
├── Dockerfile.graphx               # Image bổ sung cho preprocessing
├── scripts/
│   ├── start_graphx.sh             # Khởi động cluster
│   ├── submit_job.sh               # Submit job vào cluster
│   └── extract_triplets.py         # ETL: JSON 2.4GB → CSV 35MB (chỉ giữ triplets)
├── jobs/
│   ├── 01_load_triplets.py         # Spark: load CSV → Parquet
│   └── 02_full_analysis.py         # Spark + GraphFrames: phân tích toàn diện
├── output/                         # Kết quả phân tích
│   ├── triplets_extracted.csv      # CSV triplets (head, relation, tail, stage, source)
│   ├── report.md                   # Báo cáo tổng hợp
│   └── graph_analysis/             # Các file metrics + CSV kết quả
└── TODO.md                         # Kế hoạch chi tiết các task
```

## Yêu cầu

- Docker Engine ≥ 24.0
- Docker Compose ≥ 2.20
- RAM ≥ 8 GB (khuyến nghị 16 GB)
- Dữ liệu: `batch-prompt/output/kg_raw_triplets_4k.json`

## Hướng dẫn chạy

### Bước 0 — Trích xuất triplets từ JSON gốc

File JSON gốc nặng 2.4 GB, chứa rất nhiều metadata không cần cho phân tích đồ thị.
Bước này streaming extract chỉ 5 trường `head, relation, tail, stage, source` ra CSV 35 MB.

```bash
cd kg-construct
python3 analysis/scripts/extract_triplets.py
```

Output: `analysis/output/triplets_extracted.csv` (~218,685 rows, ~35 MB)

### Bước 1 — Khởi động Spark cluster

```bash
cd kg-construct
docker compose -f analysis/docker-compose.graphx.yml up -d \
  spark-master-graphx spark-worker-graphx
```

Kiểm tra cluster sẵn sàng:

```bash
# Đợi cả master và worker healthy
docker compose -f analysis/docker-compose.graphx.yml ps

# Spark Master UI: http://localhost:8092
```

### Bước 2 — Chạy Job 01: Load triplets → Parquet

```bash
docker compose -f analysis/docker-compose.graphx.yml run --rm \
  spark-submit-graphx bash -c '
  /opt/spark/bin/spark-submit \
    --master spark://spark-master-graphx:7078 \
    --driver-memory 4g \
    --executor-memory 4g \
    /workspace/analysis/jobs/01_load_triplets.py
'
```

Output: `/data/output/triplets_parquet/` (Parquet, dùng cho bước sau)

### Bước 3 — Chạy Job 02: Phân tích toàn diện bằng GraphFrames

```bash
docker compose -f analysis/docker-compose.graphx.yml run --rm \
  spark-submit-graphx bash -c '
  mkdir -p /tmp/ivy2/cache /tmp/ivy2/jars /tmp/graphx-ckpt
  /opt/spark/bin/spark-submit \
    --master spark://spark-master-graphx:7078 \
    --packages graphframes:graphframes:0.8.3-spark3.5-s_2.12 \
    --conf spark.jars.ivy=/tmp/ivy2 \
    --driver-memory 4g \
    --executor-memory 4g \
    --conf spark.sql.adaptive.enabled=true \
    /workspace/analysis/jobs/02_full_analysis.py
'
```

> **Lưu ý quan trọng:**
> - `--conf spark.jars.ivy=/tmp/ivy2` — bắt buộc vì image `apache/spark:3.5.1` chạy user `spark` mà `/home/spark` không có quyền ghi. Đặt Ivy cache sang `/tmp` để resolve GraphFrames jar.
> - `mkdir -p /tmp/ivy2/cache /tmp/ivy2/jars` — tạo thư mục trước khi Spark submit.
> - Lần đầu chạy sẽ tải GraphFrames jar từ Maven (~vài giây).

### Bước 4 — Dọn dẹp

```bash
docker compose -f analysis/docker-compose.graphx.yml down -v
```

## Các phân tích được thực hiện

Job `02_full_analysis.py` chạy 15 phân tích bằng GraphFrames (tương đương GraphX):

| # | Phân tích | GraphFrames API | Mô tả |
|---|---|---|---|
| 1 | Load CSV | `spark.read.csv()` | Đọc triplets |
| 2 | Build Graph | `GraphFrame(vertices, edges)` | Xây dựng đồ thị |
| 3 | Degree Distribution | `g.degrees`, `g.inDegrees`, `g.outDegrees` | Phân bố bậc |
| 4 | PageRank | `g.pageRank(resetProbability, maxIter)` | Xếp hạng đỉnh quan trọng |
| 5 | Connected Components | `g.connectedComponents()` | Tính liên thông |
| 6 | Strongly Connected Components | `g.stronglyConnectedComponents(maxIter)` | SCC |
| 7 | Triangle Count | `g.triangleCount()` | Đếm tam giác + clustering |
| 8 | Label Propagation | `g.labelPropagation(maxIter)` | Phát hiện cộng đồng |
| 9 | Shortest Paths | `g.shortestPaths(landmarks)` | Đường đi ngắn nhất |
| 10 | Motif Finding | `g.find("(a)-[e1]->(b); ...")` | Tìm pattern trong đồ thị |
| 11 | Relation Analysis | Spark SQL `groupBy/agg` | Thống kê quan hệ |
| 12 | Quality Checks | Spark SQL filters | Self-loops, leaf nodes, density |
| 13 | PageRank per Stage | `GraphFrame.pageRank()` trên subgraph | So sánh giữa stages |
| 14 | Reciprocal Edges | `g.find("(a)-[e1]->(b); (b)-[e2]->(a)")` | Cạnh đối xứng |
| 15 | Save Metrics | JSON export | Lưu tổng hợp |

## Output

Kết quả được lưu tại `analysis/output/graph_analysis/`:

| File | Nội dung |
|---|---|
| `metrics.json` | Tổng hợp tất cả metrics |
| `degree_distribution/` | Phân bố bậc (Parquet) |
| `pagerank_results/` | Top PageRank (Parquet) |
| `connected_components/` | Thành phần liên thông (Parquet) |
| `scc_results/` | SCC (Parquet) |
| `triangle_count/` | Tam giác (Parquet) |
| `lpa_communities/` | Cộng đồng LPA (Parquet) |
| `shortest_paths/` | Shortest paths (Parquet) |
| `relation_stats/` | Thống kê relation (Parquet) |

Báo cáo tổng hợp: `analysis/output/report.md`

## Cấu hình

Các biến môi trường có thể override (trong `.env` hoặc export):

| Biến | Mặc định | Mô tả |
|---|---|---|
| `GRAPHX_WORKER_CORES` | `4` | CPU cores cho worker |
| `GRAPHX_WORKER_MEMORY` | `8g` | RAM cho worker |
| `GRAPHX_DRIVER_MEMORY` | `4g` | RAM cho driver (submit) |
| `GRAPHX_EXECUTOR_MEMORY` | `4g` | RAM cho executor |
| `GRAPHX_EXECUTOR_CORES` | `2` | CPU cores cho executor |
| `GRAPHX_WORKER_COUNT` | `1` | Số lượng worker containers |

Scale worker khi cần:

```bash
GRAPHX_WORKER_COUNT=2 docker compose -f analysis/docker-compose.graphx.yml up -d
```

