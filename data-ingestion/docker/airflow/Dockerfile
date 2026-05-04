FROM apache/airflow:2.9.3-python3.11

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends graphviz && \
    rm -rf /var/lib/apt/lists/*

USER airflow

COPY docker/airflow/requirements-airflow.txt /tmp/requirements-airflow.txt

RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt
