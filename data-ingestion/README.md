# Dự án Data Ingestion (UET MVP)

Dự án thu thập dữ liệu tự động (Crawler) từ các nguồn HTML và PDF, phục vụ cho hệ thống tri thức của UET.

## Hướng dẫn chạy dự án

### Bước 1: Cài đặt và cấu hình ban đầu
Sao chép file biến môi trường gốc:
```bash
cp .env.example .env
```
*(Nếu cần chạy mã Python ở ngoài (local), bạn có thể tạo virtual environment và chạy `pip install -e .`)*

### Bước 2: Khởi động hệ thống (Docker & Airflow)
Dự án được đóng gói bằng Docker. Khởi động tất cả các dịch vụ (Airflow, MinIO, Postgres, Crawler Runtime):
```bash
docker compose up -d --build
```
> Kiểm tra trạng thái các container: `docker compose ps`
> Truy cập giao diện quản lý Airflow tại: **http://localhost:8080** (Tài khoản/Mật khẩu lấy từ file `.env`).

### Bước 3: Khởi tạo Storage (Chỉ chạy 1 lần)
Tạo cấu trúc lưu trữ trên MinIO (dữ liệu thô) và SQLite (trạng thái crawl):
```bash
sudo docker exec data-ingestion-crawler-runtime python /opt/project/scripts/init_minio.py
sudo docker exec data-ingestion-crawler-runtime python /opt/project/scripts/bootstrap_sqlite.py
```

### Bước 4: Kiểm tra hệ thống (Smoke Tests)
Đảm bảo kết nối DB, MinIO và Airflow hoạt động trơn tru:
```bash
sudo docker exec data-ingestion-crawler-runtime python /opt/project/scripts/run_smoke_tests.py
```
*(Báo cáo kiểm tra sẽ được xuất ra thư mục `metadata/smoke_test_report.json`)*

### Bước 5: Chạy Crawler thu thập dữ liệu
Để chạy thủ công crawler lấy tin tức UET (giới hạn 20 trang):
```bash
sudo docker exec data-ingestion-crawler-runtime sh -lc "cd /opt/project/crawler && scrapy crawl html_source_registry -a source_id=uet-news -a max_pages_per_source=20 -O /tmp/uet-news-pilot.json"
```
> **Ghi chú:** Khi hệ thống thực sự vận hành, tiến trình thu thập dữ liệu này sẽ được tự động kích hoạt định kỳ thông qua các DAG trên Airflow (`phase1_ingestion_dag`).

---

## Cấu trúc thư mục chính
- `crawler/`: Mã nguồn Scrapy dùng để đi cào dữ liệu (HTML/PDF).
- `dags/`: Chứa các luồng tự động hóa của Airflow.
- `docker/`: Cấu hình các container.
- `scripts/`: Chứa các lệnh chạy tiện ích.
- `config/`: Cấu hình danh sách các trang web cần thu thập (`sources.yaml`).
- `metadata/`: Nơi lưu các báo cáo và file SQLite theo dõi trạng thái cào dữ liệu.

## Tiến độ dự án
- **Giai đoạn 0:** Hoàn thiện hạ tầng Docker, Airflow, MinIO, chuẩn hóa quy tắc lưu trữ.
- **Giai đoạn 1:** Crawler HTML hoạt động, lưu trữ MinIO thành công, quản lý state bằng SQLite, tự động hoá chạy crawl & check chất lượng trên Airflow. Đã chạy thử nghiệm Pilot thành công.
