#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <spark_app.py> [app args...]" >&2
  exit 1
fi

app_path="$1"
shift || true

master_url="${SPARK_MASTER_URL:-spark://spark-master:7077}"
deploy_mode="${SPARK_SUBMIT_DEPLOY_MODE:-client}"
minio_endpoint="${MINIO_ENDPOINT:-http://minio:9000}"
minio_access_key="${MINIO_ACCESS_KEY:-minioadmin}"
minio_secret_key="${MINIO_SECRET_KEY:-minioadmin123}"
minio_region="${MINIO_REGION:-us-east-1}"
s3a_packages="${S3A_PACKAGES:-org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262}"
driver_memory="${SPARK_DRIVER_MEMORY:-2g}"
executor_instances="${SPARK_EXECUTOR_INSTANCES:-}"
executor_memory="${SPARK_EXECUTOR_MEMORY:-4g}"
executor_cores="${SPARK_EXECUTOR_CORES:-2}"
ivy_dir="${SPARK_IVY_DIR:-/opt/spark/.ivy2}"

ssl_enabled="false"
if [[ "${minio_endpoint}" == https://* ]]; then
  ssl_enabled="true"
fi

mkdir -p "${ivy_dir}/cache" "${ivy_dir}/jars"
export PYTHONPATH="/workspace:${PYTHONPATH:-}"
executor_pythonpath="/workspace"
if [[ -n "${PYTHONPATH:-}" ]]; then
  executor_pythonpath="/workspace:${PYTHONPATH}"
fi

openai_conf=()
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  openai_conf+=(--conf "spark.executorEnv.OPENAI_API_KEY=${OPENAI_API_KEY}")
fi
if [[ -n "${OPENAI_BASE_URL:-}" ]]; then
  openai_conf+=(--conf "spark.executorEnv.OPENAI_BASE_URL=${OPENAI_BASE_URL}")
fi
if [[ -n "${OPENAI_TIMEOUT_SECONDS:-}" ]]; then
  openai_conf+=(--conf "spark.executorEnv.OPENAI_TIMEOUT_SECONDS=${OPENAI_TIMEOUT_SECONDS}")
fi
if [[ -n "${OPENAI_MAX_RETRIES:-}" ]]; then
  openai_conf+=(--conf "spark.executorEnv.OPENAI_MAX_RETRIES=${OPENAI_MAX_RETRIES}")
fi
if [[ -n "${OPENAI_BACKOFF_SECONDS:-}" ]]; then
  openai_conf+=(--conf "spark.executorEnv.OPENAI_BACKOFF_SECONDS=${OPENAI_BACKOFF_SECONDS}")
fi
executor_instance_conf=()
if [[ -n "${executor_instances}" ]]; then
  executor_instance_conf+=(--conf "spark.executor.instances=${executor_instances}")
fi

exec /opt/spark/bin/spark-submit \
  --master "${master_url}" \
  --deploy-mode "${deploy_mode}" \
  --packages "${s3a_packages}" \
  --conf "spark.jars.ivy=${ivy_dir}" \
  --conf "spark.driver.memory=${driver_memory}" \
  "${executor_instance_conf[@]}" \
  --conf "spark.executor.memory=${executor_memory}" \
  --conf "spark.executor.cores=${executor_cores}" \
  --conf "spark.executorEnv.PYTHONPATH=${executor_pythonpath}" \
  "${openai_conf[@]}" \
  --conf "spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem" \
  --conf "spark.hadoop.fs.s3a.endpoint=${minio_endpoint}" \
  --conf "spark.hadoop.fs.s3a.access.key=${minio_access_key}" \
  --conf "spark.hadoop.fs.s3a.secret.key=${minio_secret_key}" \
  --conf "spark.hadoop.fs.s3a.path.style.access=true" \
  --conf "spark.hadoop.fs.s3a.connection.ssl.enabled=${ssl_enabled}" \
  --conf "spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider" \
  --conf "spark.hadoop.fs.s3a.endpoint.region=${minio_region}" \
  "${app_path}" \
  "$@"
