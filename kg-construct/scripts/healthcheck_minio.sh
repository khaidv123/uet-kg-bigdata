#!/bin/sh
set -eu

attempt="${1:-30}"
count=0

while [ "${count}" -lt "${attempt}" ]; do
  if mc alias set local "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" >/dev/null 2>&1 \
    && mc ready local >/dev/null 2>&1; then
    echo "MINIO_READY"
    exit 0
  fi

  count=$((count + 1))
  sleep 2
done

echo "MINIO_NOT_READY after ${attempt} attempts" >&2
exit 1
