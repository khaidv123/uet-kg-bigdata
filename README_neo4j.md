# Multi-store RAG pipeline cho dữ liệu UET KG BigData

Repo hiện chứa artifacts đã build từ LightRAG. Dữ liệu chính nằm ở `output_verson1_uet_kg_bigdata/rag_storage`.

Nếu dùng Python environment khác, cài dependency:

```powershell
pip install -r requirements-neo4j.txt
```

## Kiến trúc lưu trữ

Pipeline lưu cùng một bộ dữ liệu trên 3 lớp:

- Raw data: HDFS/WebHDFS, mặc định thư mục `/uet-kg-bigdata/raw`.
- Graph DB: Neo4j chứa `Document`, `Chunk`, `Entity`, `RELATES_TO` để traversal multi-hop.
- Vector DB: Elasticsearch chứa chunk/entity embeddings dạng `dense_vector` để semantic search.

Luồng RAG serving:

1. Chuyển câu hỏi thành embedding bằng model cùng chiều với dữ liệu đã index, mặc định `text-embedding-3-small`.
2. Truy vấn song song Neo4j graph traversal và Elasticsearch vector kNN.
3. Gộp context, tạo citation `[S1]`, `[S2]`, rồi gọi LLM Groq qua OpenAI-compatible endpoint.

## Dữ liệu đã rà soát

- `kv_store_full_docs.json`: 1,048 document gốc.
- `kv_store_text_chunks.json`: 1,110 chunk văn bản.
- `graph_chunk_entity_relation.graphml`: 16,260 entity và 17,120 quan hệ.
- `vdb_chunks.json`: 1,106 embedding chunk, dim 1,536.
- `vdb_entities.json`: 16,251 embedding entity, dim 1,536.
- `vdb_relationships.json`: 17,120 embedding quan hệ, hiện chưa import mặc định để tránh database phình quá lớn.
- `kv_store_entity_chunks.json` và `kv_store_relation_chunks.json`: map entity/quan hệ về chunk bằng chứng.
- `kv_store_doc_status.json`: 539 processed, 5 failed, 2 processing, 502 pending.

Embedding trong `vdb_*` là vector float16 nén bằng `zlib + base64`; script import sẽ giải nén thành list float32 để Elasticsearch index semantic search. Neo4j vẫn có thể giữ vector nếu cần fallback.

## Mô hình Neo4j

Script import tạo graph:

- `(:Document {id, content, file_path, status, ...})`
- `(:Chunk {id, content, full_doc_id, file_path, embedding, ...})`
- `(:Entity {id, name, entity_type, description, embedding, name_ascii, ...})`
- `(Document)-[:HAS_CHUNK]->(Chunk)`
- `(Chunk)-[:NEXT_CHUNK]->(Chunk)`
- `(Chunk)-[:MENTIONS]->(Entity)`
- `(Entity)-[:RELATES_TO {weight, description, keywords, source_ids, chunk_ids, ...}]->(Entity)`

Indexes được tạo:

- Unique constraints cho `Document.id`, `Chunk.id`, `Entity.id`.
- Fulltext indexes: `document_text`, `chunk_text`, `entity_text`, `relation_text`.
- Vector indexes: `chunk_embedding`, `entity_embedding`.
- Range indexes cho `Chunk.full_doc_id`, `Entity.name_lc`, `Entity.name_ascii`, `RELATES_TO.pair_id`.

## Chạy import

Đặt thông tin kết nối các lớp lưu trữ trong PowerShell:

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

Kiểm tra parse dữ liệu, không ghi database:

```powershell
python scripts\import_lightrag_to_neo4j.py --dry-run
```

Import đồng bộ cả HDFS, Neo4j và Elasticsearch:

```powershell
python scripts\import_lightrag_multistore.py --reset --batch-size 100
```

Import từng lớp khi cần debug:

```powershell
python scripts\import_raw_to_hdfs.py
python scripts\import_lightrag_to_neo4j.py --reset --skip-vectors --batch-size 500
python scripts\import_lightrag_to_elasticsearch.py --reset --batch-size 200
```

Nếu vẫn muốn lưu vector trong Neo4j để fallback:

```powershell
python scripts\import_lightrag_to_neo4j.py --reset --batch-size 100
```

Nếu máy yếu RAM hoặc muốn import nhanh trước:

```powershell
python scripts\import_lightrag_to_neo4j.py --reset --skip-vectors --batch-size 500
```

## Truy vấn hybrid

Truy vấn graph/fulltext Neo4j, không cần embedding key:

```powershell
python scripts\query_neo4j.py "điểm chuẩn ngành khoa học máy tính 2024" --no-vector
```

Truy vấn hybrid Neo4j multi-hop + Elasticsearch semantic search. Query mới phải được embedding cùng model với vector đã index:

```powershell
$env:OPENAI_EMBEDDING_API_KEY="sk-..."
$env:ELASTICSEARCH_URL="http://localhost:9200"

python scripts\query_neo4j.py "học phí ngành trí tuệ nhân tạo năm 2024" --graph-hops 2 --json
```

Kết quả trả về gồm entity liên quan, path multi-hop trong Neo4j, chunk semantic từ Elasticsearch, chunk bằng chứng và metadata `vector_db`, `graph_db`, `graph_hops`. Phần này là retrieval layer; RAG sẽ lấy `chunks` làm context đưa vào LLM.

## Chatbot RAG

Chatbot dùng retrieval hybrid Neo4j + Elasticsearch, sau đó gọi Groq để sinh câu trả lời tự nhiên. Với Groq, đặt `GROQ_API_KEY`; code tự dùng OpenAI-compatible endpoint `https://api.groq.com/openai/v1` và model mặc định `llama-3.1-8b-instant`. Semantic search cần thêm embedding key tương thích với vector đã index.

```powershell
$env:GROQ_API_KEY="gsk_..."
$env:GROQ_CHAT_MODEL="llama-3.1-8b-instant"
$env:OPENAI_EMBEDDING_API_KEY="sk-..."
$env:ELASTICSEARCH_URL="http://localhost:9200"

python scripts\chatbot_neo4j.py "học phí ngành trí tuệ nhân tạo năm 2024 là bao nhiêu?" --graph-hops 2 --show-sources
```

Chạy hội thoại nhiều lượt:

```powershell
python scripts\chatbot_neo4j.py --interactive --show-sources
```

Vẫn có thể dùng OpenAI bằng `OPENAI_API_KEY`/`OPENAI_CHAT_MODEL`, hoặc dùng endpoint OpenAI-compatible khác bằng `--base-url`. Nếu chưa có Elasticsearch hoặc embedding key, thêm `--no-vector` để chạy graph-only:

```powershell
python scripts\chatbot_neo4j.py "điểm chuẩn khoa học máy tính 2024" --api-key provider-key --base-url https://your-provider.example/v1 --chat-model your-chat-model --no-vector --show-sources
```

Nếu dùng model hoặc endpoint OpenAI-compatible khác:

```powershell
python scripts\chatbot_neo4j.py "điểm chuẩn khoa học máy tính 2024" --chat-model your-model --base-url http://localhost:11434/v1 --api-key local-key
```

## Web UI local

Chạy web server:

```powershell
python scripts\web_server.py --host 127.0.0.1 --port 8000
```

Mở:

```text
http://127.0.0.1:8000
```

Web UI có thể nhận Neo4j password, Groq API key, embedding key, Elasticsearch URL/index, graph hops và lựa chọn bật/tắt vector search ngay trên màn hình. Nếu đã đặt `GROQ_API_KEY`, `OPENAI_EMBEDDING_API_KEY` và `ELASTICSEARCH_URL` trước khi chạy server thì không cần nhập lại trong UI.

## Chiến lược truy xuất hiệu quả

Luồng nên dùng cho input người dùng:

1. Chạy fulltext trên `entity_text` và `chunk_text` để bắt keyword, mã ngành, tên riêng, thuật ngữ tiếng Việt.
2. Tạo embedding câu hỏi và chạy kNN trên Elasticsearch index `uet_kg_chunks`.
3. Gộp seed entities, mở rộng multi-hop qua `RELATES_TO`, ưu tiên tổng `weight` cao và path ngắn.
4. Lấy chunk bằng chứng qua `MENTIONS` và `source_ids/chunk_ids` trên quan hệ.
5. Merge chunks từ Graph DB và Vector DB, bỏ trùng theo `chunk_id`, giữ `retrieval_source`.
6. Đưa 5-10 chunk tốt nhất vào prompt Groq, yêu cầu trích nguồn theo `file_path` và `chunk_id`.
