#!/bin/sh
set -eu

/bin/sh /workspace/scripts/healthcheck_minio.sh

mc alias set local "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" >/dev/null
mc mb --ignore-existing "local/${MINIO_BUCKET}" >/dev/null

for prefix in \
  raw \
  bronze \
  silver \
  gold \
  meta/phase2 \
  meta/phase2/manifests \
  meta/phase2/checkpoints \
  meta/phase2/logs \
  meta/phase2/smoke
do
  mc pipe "local/${MINIO_BUCKET}/${prefix}/.keep" < /dev/null >/dev/null 2>&1 || true
done

echo "MINIO_BOOTSTRAP_OK bucket=${MINIO_BUCKET}"
