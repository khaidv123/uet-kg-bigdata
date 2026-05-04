# Phase 2 Docker Quickstart

## Lenh chay nhanh

```bash
cp .env.example .env
docker compose -f docker-compose.phase2.yml up -d --build
docker compose -f docker-compose.phase2.yml ps
```

## Smoke test Spark -> MinIO

Khi stack da healthy, chay smoke job:

```bash
docker compose -f docker-compose.phase2.yml run --rm --no-deps spark-submit \
  /bin/bash -lc '/bin/bash /workspace/scripts/spark_submit_phase2.sh /workspace/scripts/smoke_s3a_minio.py'
```

Ket qua mong doi:

- Spark submit duoc vao `spark-master`
- `spark-worker` nhan executor
- MinIO co object moi duoi `meta/phase2/smoke/`

## Scale len 2 worker sau nay

Compose hien tai mac dinh `1` worker. Khi can smoke demo scale-out:

```bash
docker compose -f docker-compose.phase2.yml up -d --scale spark-worker=2
```

Khong can sua logic job; chi can tuning lai memory/cores phu hop host.
