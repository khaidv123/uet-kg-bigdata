# Neo4j pipeline cho dữ liệu UET KG BigData

Repo hiện chỉ chứa artifacts đã build từ LightRAG, chưa có Neo4j đang chạy local. Dữ liệu chính nằm ở `output_verson1_uet_kg_bigdata/rag_storage`.

Nếu dùng Python environment khác, cài dependency:

```powershell
pip install -r requirements-neo4j.txt
```

## Dữ liệu đã rà soát

- `kv_store_full_docs.json`: 1,048 document gốc.
- `kv_store_text_chunks.json`: 1,110 chunk văn bản.
- `graph_chunk_entity_relation.graphml`: 16,260 entity và 17,120 quan hệ.
- `vdb_chunks.json`: 1,106 embedding chunk, dim 1,536.
- `vdb_entities.json`: 16,251 embedding entity, dim 1,536.
- `vdb_relationships.json`: 17,120 embedding quan hệ, hiện chưa import mặc định để tránh database phình quá lớn.
- `kv_store_entity_chunks.json` và `kv_store_relation_chunks.json`: map entity/quan hệ về chunk bằng chứng.
- `kv_store_doc_status.json`: 539 processed, 5 failed, 2 processing, 502 pending.

Embedding trong `vdb_*` là vector float16 nén bằng `zlib + base64`; script import sẽ giải nén thành list float32 để Neo4j tạo vector index.

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

Đặt thông tin kết nối Neo4j trong PowerShell:

```powershell
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="minhminh"
$env:NEO4J_DATABASE="UET_KG_BIGDATA"
```

Kiểm tra parse dữ liệu, không ghi database:

```powershell
python scripts\import_lightrag_to_neo4j.py --dry-run
```

Import đầy đủ, có embedding và vector index:

```powershell
python scripts\import_lightrag_to_neo4j.py --reset --batch-size 100
```

Nếu máy yếu RAM hoặc muốn import nhanh trước:

```powershell
python scripts\import_lightrag_to_neo4j.py --reset --skip-vectors --batch-size 500
```

## Truy vấn

Truy vấn lexical/fulltext, không cần OpenAI key:

```powershell
python scripts\query_neo4j.py "điểm chuẩn ngành khoa học máy tính 2024" --no-vector
```

Truy vấn hybrid fulltext + vector, cần `OPENAI_API_KEY` vì query mới phải được embedding cùng model `text-embedding-3-small`:

```powershell
$env:OPENAI_API_KEY="sk-..."
python scripts\query_neo4j.py "học phí ngành trí tuệ nhân tạo năm 2024"
```

Kết quả trả về gồm entity liên quan, các quan hệ lân cận có trọng số, và chunk bằng chứng. Phần này là retrieval layer; nếu muốn trả lời tự nhiên cho người dùng cuối thì lấy `chunks` làm context đưa vào LLM.

## Chatbot RAG

Chatbot dùng lại retrieval từ Neo4j, sau đó gọi LLM để sinh câu trả lời tự nhiên. Cần `OPENAI_API_KEY`; nếu Neo4j chưa có vector index hoặc chưa muốn dùng embedding query thì thêm `--no-vector`.

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:OPENAI_CHAT_MODEL="gpt-4o-mini"

python scripts\chatbot_neo4j.py "học phí ngành trí tuệ nhân tạo năm 2024 là bao nhiêu?" --show-sources
```

Chạy hội thoại nhiều lượt:

```powershell
python scripts\chatbot_neo4j.py --interactive --show-sources
```

Nếu đang dùng key OpenAI-compatible khác, ví dụ key có dạng `gsk_...`, cần truyền `--base-url` hoặc đặt `OPENAI_BASE_URL`. Nếu provider đó không hỗ trợ embeddings, thêm `--no-vector`:

```powershell
python scripts\chatbot_neo4j.py "điểm chuẩn khoa học máy tính 2024" --no-vector --base-url https://your-provider.example/v1 --chat-model your-chat-model --show-sources
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

Web UI có thể nhận Neo4j password, API key, base URL, model và lựa chọn bật/tắt vector search ngay trên màn hình. Mặc định vector search tắt để tránh lỗi khi provider chat không hỗ trợ embeddings.

## Chiến lược truy xuất hiệu quả

Luồng nên dùng cho input người dùng:

1. Chạy fulltext trên `entity_text` và `chunk_text` để bắt keyword, mã ngành, tên riêng, thuật ngữ tiếng Việt.
2. Nếu có embedding query, chạy vector search trên `entity_embedding` và `chunk_embedding`.
3. Gộp seed entities, mở rộng 1 hop qua `RELATES_TO`, ưu tiên `weight` cao.
4. Lấy chunk bằng chứng qua `MENTIONS` và `source_ids/chunk_ids` trên quan hệ.
5. Rerank chunks bằng điểm tổng hợp: fulltext/vector score, số entity match, relation weight, độ gần của seed.
6. Đưa 5-10 chunk tốt nhất vào prompt trả lời, yêu cầu trích nguồn theo `file_path` và `chunk_id`.
