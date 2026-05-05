#!/usr/bin/env bash
# ============================================================
# Start the GraphX analysis Spark cluster
# Usage:  bash analysis/scripts/start_graphx.sh
# ============================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Starting Spark GraphX cluster ==="
docker compose -f "${SCRIPT_DIR}/docker-compose.graphx.yml" up -d \
  spark-master-graphx spark-worker-graphx

echo "=== Waiting for Spark Master to become healthy ==="
timeout 120 bash -c '
  until docker inspect --format="{{.State.Health.Status}}" spark-master-graphx 2>/dev/null | grep -q healthy; do
    sleep 2
    echo -n "."
  done
'
echo ""
echo "=== Spark Master UI: http://localhost:8090 ==="
echo "=== Cluster is ready ==="
