# KG-Construct Pipeline

Hệ thống được thiết kế theo pipeline bao gồm nhiều bước: từ nạp tài liệu thô, làm sạch, cắt văn bản, rút trích bộ ba (triple: Thực thể - Quan hệ - Sự kiện), cho tới chuẩn hóa và tạo đồ thị cuối cùng. Để đáp ứng khối lượng dữ liệu lớn, KG-Construct sử dụng **Apache Spark** kết hợp bộ lưu trữ Object Storage (**MinIO**), và khai thác sức mạnh của LLM (thông qua OpenAI-compatible API) cho các bước phân tích ngôn ngữ phức tạp.

---

## 1. Chuẩn bị dữ liệu đầu vào

Dữ liệu thô dùng để chạy trên hệ thống đang được lưu trữ trên Google Drive. Bạn hãy thực hiện các bước sau để thiết lập data:

1. **Tải dữ liệu:** Tải file `uet_news.json` (hoặc file dữ liệu tương ứng của bạn) từ link Google Drive: `[Nhập link Google Drive của bạn vào đây]`
2. **Lưu trữ cục bộ:** Tại thư mục gốc của dự án `kg-construct`, tạo một thư mục mang tên `raw_web_page_data` và đặt file vừa tải vào đó.
3. **Cập nhật cấu hình:** Mở file `config/demo.yaml` và đảm bảo đường dẫn `path` trỏ đúng tới vị trí của file:
   ```yaml
   input:
     path: raw_web_page_data/uet_news.json
     format: json
     text_field: content
   ```

---

## 2. Thiết lập môi trường chạy (Docker)

Hệ thống yêu cầu các nền tảng Spark (Master/Worker) và MinIO phải được bật. Trước khi chạy code, hãy khởi động cụm Docker:

```bash
docker compose -f docker-compose.phase2.yml up -d
```

*Lưu ý: Bạn cũng cần cấu hình file `.env` (bạn có thể copy từ mẫu `.env.example`) để khai báo API Key cho các bước dùng LLM.*

---

## 3. Hướng dẫn chạy Pipeline

Bạn có thể kích hoạt toàn bộ chu trình xử lý thông qua script điều phối chính: `run_phase2_pipeline.py`. 

Dưới đây là một số cách chạy:

### A. Chạy test với giới hạn mặc định
Theo mặc định, pipeline được cấu hình với thông số nhỏ (chỉ xử lý khoảng 10 văn bản thô đầu tiên và tối đa 100 requests API):
```bash
python3 scripts/run_phase2_pipeline.py
```

### B. Chạy kiểm tra End-to-End test (Limit = 1)

```bash
python3 scripts/run_phase2_pipeline.py --ingest-limit 1 --extraction-limit 1 --concept-limit 1 --embedding-limit 1
```

### C. Chạy toàn bộ dữ liệu (Full run)
Khi muốn vận hành hệ thống để xử lý toàn bộ file dữ liệu đầu vào:
```bash
python3 scripts/run_phase2_pipeline.py --full
```
*(hoặc cấu hình cụ thể: `python3 scripts/run_phase2_pipeline.py --ingest-limit all --extraction-limit all --concept-limit all --embedding-limit all`)*


