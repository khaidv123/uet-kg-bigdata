# UET Knowledge Graph BigData

> Hệ thống Knowledge Graph kết hợp Big Data và mô hình ngôn ngữ lớn (LLM) phục vụ hỏi đáp thông tin Trường Đại học Công nghệ (UET).

---

## 1. Giới thiệu

Dự án xây dựng hệ thống **RAG Knowledge Graph** dành riêng cho dữ liệu UET, với kiến trúc pipeline gồm 4 giai đoạn chính:

| Giai đoạn | Mô tả |
|-----------|-------|
| **Phase 1 – Data Ingestion** | Thu thập dữ liệu tự động từ website UET (HTML, PDF) qua Apache Airflow + Scrapy |
| **Phase 2 – KG Construction** | Xử lý phân tán bằng Apache Spark, trích xuất triplets bằng LLM, lưu trên MinIO theo kiến trúc Medallion (Bronze → Silver → Gold) |
| **Phase 3 – KG Analysis** | Phân tích đồ thị với Spark GraphFrames: PageRank, Community Detection, Connected Components |
| **Phase 4 – GraphRAG** | Hỏi đáp thông minh bằng Hybrid Retrieval (Neo4j graph traversal + Elasticsearch vector search) kết hợp LLM sinh câu trả lời |

![Tổng quan kiến trúc hệ thống](assets/big-data-overview-image.png)

### Dữ liệu 

Dữ liệu được lưu trên Google Drive:

> **[Tải dữ liệu tại đây]** — *(Cập nhật link Google Drive vào đây)*

---

## 2. Hướng dẫn chạy KG-Construct (Phase 2)

Toàn bộ code của pipeline xây dựng đồ thị nằm trong thư mục `/kg-construct`.

### 2.1. Chuẩn bị dữ liệu

```bash
cd kg-construct
mkdir -p raw_web_page_data
# Đặt file uet_news.json vào thư mục raw_web_page_data/
```

Kiểm tra file `config/demo.yaml`, đảm bảo đường dẫn trỏ đúng:

```yaml
input:
  path: raw_web_page_data/uet_news.json
  format: json
  text_field: content
```

Cấu hình API key cho LLM bằng cách copy file `.env.example` thành `.env` và điền thông tin:

```bash
cp .env.example .env
# Chỉnh sửa .env và điền API Key
```

### 2.2. Khởi động môi trường Docker

```bash
cd kg-construct
docker compose -f docker-compose.phase2.yml up -d
```

### 2.3. Chạy pipeline

**Test nhanh với giới hạn mặc định (~10 văn bản):**

```bash
cd kg-construct
python3 scripts/run_phase2_pipeline.py
```

**End-to-end test với 1 văn bản:**

```bash
cd kg-construct
python3 scripts/run_phase2_pipeline.py --ingest-limit 1 --extraction-limit 1 --concept-limit 1 --embedding-limit 1
```

**Chạy toàn bộ dữ liệu:**

```bash
cd kg-construct
python3 scripts/run_phase2_pipeline.py --full
```

---

## 3. Hướng dẫn chạy GraphRAG trên Neo4j và Deploy Web

### 3.1. Cài đặt dependencies

```powershell
pip install -r requirements-neo4j.txt
```

### 3.2. Cấu hình biến môi trường

```powershell
$env:WEBHDFS_URL="http://localhost:9870"
$env:WEBHDFS_USER="hadoop"
$env:HDFS_RAW_DIR="/uet-kg-bigdata/raw"

$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="minhminh"
$env:NEO4J_DATABASE="UET_KG_BIGDATA"

$env:ELASTICSEARCH_URL="http://localhost:9200"
$env:ES_CHUNKS_INDEX="uet_kg_chunks"
$env:ES_ENTITIES_INDEX="uet_kg_entities"
```

### 3.3. Import dữ liệu vào các lớp lưu trữ

**Kiểm tra parse (không ghi database):**

```powershell
python scripts\import_lightrag_to_neo4j.py --dry-run
```

**Import đồng bộ cả HDFS, Neo4j và Elasticsearch:**

```powershell
python scripts\import_lightrag_multistore.py --reset --batch-size 100
```

**Import từng lớp (khi cần debug):**

```powershell
python scripts\import_raw_to_hdfs.py
python scripts\import_lightrag_to_neo4j.py --reset --skip-vectors --batch-size 500
python scripts\import_lightrag_to_elasticsearch.py --reset --batch-size 200
```

### 3.4. Truy vấn

**Graph/fulltext (không cần embedding):**

```powershell
python scripts\query_neo4j.py "điểm chuẩn ngành khoa học máy tính 2024" --no-vector
```

**Hybrid (Neo4j multi-hop + Elasticsearch semantic search):**

```powershell
$env:OPENAI_EMBEDDING_API_KEY="sk-..."
python scripts\query_neo4j.py "học phí ngành trí tuệ nhân tạo năm 2024" --graph-hops 2 --json
```

### 3.5. Chatbot RAG

```powershell
$env:GROQ_API_KEY="gsk_..."
$env:GROQ_CHAT_MODEL="llama-3.1-8b-instant"
$env:OPENAI_EMBEDDING_API_KEY="sk-..."

# Câu hỏi đơn
python scripts\chatbot_neo4j.py "học phí ngành trí tuệ nhân tạo năm 2024 là bao nhiêu?" --graph-hops 2 --show-sources

# Hội thoại nhiều lượt
python scripts\chatbot_neo4j.py --interactive --show-sources
```

### 3.6. Deploy Web UI

```powershell
python scripts\web_server.py --host 127.0.0.1 --port 8000
```

Mở trình duyệt tại: [http://127.0.0.1:8000](http://127.0.0.1:8000)

> Web UI hỗ trợ nhập Neo4j password, Groq API key, Elasticsearch URL và các tùy chọn trực tiếp trên giao diện.

---

## 4. Kết quả thực nghiệm

### Thu thập dữ liệu

- **12,264 tài liệu** thu thập được từ `uet.vnu.edu.vn` và `tuyensinh.uet.vnu.edu.vn` (HTML + PDF).
- Pipeline crawl hoạt động ổn định với chu kỳ: 6h (tin tức), 12h (tuyển sinh), 24h (PDF).

### Quy mô Knowledge Graph

| Metric | Giá trị |
|--------|---------|
| Số thực thể (Nodes) | 157,635 |
| Số quan hệ (Edges) | 218,685 |
| Loại quan hệ | 16,375 |
| Leaf nodes | 84,960 (~54%) |
| Giant Component | 105,598 nodes (~67%) |
| Số cộng đồng (LPA) | 49,426 |

### Phân bố bậc

| Chỉ số | Giá trị |
|--------|---------|
| Bậc lớn nhất | 5,943 (Trường Đại học Công nghệ) |
| Bậc trung bình | 2.77 |
| Bậc trung vị | 1 |
| Percentile 99 | 18 |

### Top entities theo PageRank

| Thực thể | PageRank |
|----------|----------|
| Trường Đại học Công nghệ | 0.00613 |
| Đại học Quốc gia Hà Nội | 0.00335 |
| Sinh viên | 0.00264 |
| Phòng Đào tạo | 0.00091 |
| Học phí | 0.00041 |
| Khoa học máy tính | 0.00041 |

---

## Thành viên nhóm

| Họ tên | MSSV |
|--------|------|
| Đặng Văn Khải | 25025071 |
| Nguyễn Thị Ngọc Minh | 25025080 |
| Hồ Thu Giang | 25025060 |
| Nguyễn Việt Bắc | 25025055 |
| Nguyễn An Bằng | 23025052 |
