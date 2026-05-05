#!/usr/bin/env bash
# ============================================================
# Submit a PySpark + GraphFrames job to the cluster
# Usage:  bash analysis/scripts/submit_job.sh analysis/jobs/01_load_triplets.py [args...]
# ============================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

JOB_FILE="${1:?Usage: submit_job.sh <job_py_file> [args...]}"
shift

GRAPHFRAMES_PKG="${GRAPHFRAMES_PKG:-graphframes:graphframes:0.8.3-spark3.5-s_2.12}"
DRIVER_MEM="${GRAPHX_DRIVER_MEMORY:-4g}"
EXECUTOR_MEM="${GRAPHX_EXECUTOR_MEMORY:-4g}"
EXECUTOR_CORES="${GRAPHX_EXECUTOR_CORES:-2}"

echo "=== Submitting job: ${JOB_FILE} ==="
docker compose -f "${SCRIPT_DIR}/docker-compose.graphx.yml" \
  run --rm spark-submit-graphx \
  /opt/spark/bin/spark-submit \
    --master spark://spark-master-graphx:7077 \
    --packages "${GRAPHFRAMES_PKG}" \
    --driver-memory "${DRIVER_MEM}" \
    --executor-memory "${EXECUTOR_MEM}" \
    --executor-cores "${EXECUTOR_CORES}" \
    --conf spark.sql.adaptive.enabled=true \
    --conf spark.serializer=org.apache.spark.serializer.KryoSerializer \
    "/workspace/${JOB_FILE}" "$@"

echo "=== Job completed ==="
