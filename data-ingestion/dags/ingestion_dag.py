"""Phase 1 ingestion DAG for HTML crawl orchestration."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

from data_ingestion.bootstrap import project_root, resolve_project_path
from data_ingestion.ingestion_runtime import (
    build_ingestion_manifest,
    default_project_artifact_dir,
    load_crawl_reports,
    normalize_source_selector,
    resolve_selected_sources,
    summarize_pdf_manifest,
    write_json_file,
)

INGESTION_DAG_SCHEDULE = os.getenv("INGESTION_DAG_SCHEDULE", "@once")
INGESTION_DEMO_ITERATIONS = int(os.getenv("INGESTION_DEMO_ITERATIONS", "1"))
INGESTION_MAX_PAGES_PER_SOURCE = int(os.getenv("INGESTION_MAX_PAGES_PER_SOURCE", "20"))
INGESTION_SOURCE_ID = normalize_source_selector(os.getenv("INGESTION_SOURCE_ID"))
INGESTION_REGISTRY_PATH = os.getenv("INGESTION_REGISTRY_PATH", "/opt/project/config/sources.yaml")
INGESTION_ARTIFACT_DIR = default_project_artifact_dir(
    os.getenv("INGESTION_ARTIFACT_DIR", "/opt/project/metadata/ingestion_runs")
)
INGESTION_MANIFEST_PATH = Path(
    os.getenv("INGESTION_MANIFEST_PATH", "/opt/project/metadata/ingestion_manifest.json")
)
INGESTION_QUALITY_REPORT_PATH = Path(
    os.getenv("INGESTION_QUALITY_REPORT_PATH", "/opt/project/metadata/ingestion_quality_report.json")
)
PDF_URL_DISCOVERY_PATH = resolve_project_path(
    os.getenv("PDF_URL_DISCOVERY_PATH", "/opt/project/metadata/discovered_pdf_urls.jsonl"),
    base_dir=project_root(),
)
QUALITY_MIN_TITLE_RATIO = float(os.getenv("QUALITY_MIN_TITLE_RATIO", "0.95"))
QUALITY_MIN_TEXT_PREVIEW_RATIO = float(os.getenv("QUALITY_MIN_TEXT_PREVIEW_RATIO", "0.95"))
QUALITY_MIN_METADATA_COMPLETENESS_RATIO = float(
    os.getenv("QUALITY_MIN_METADATA_COMPLETENESS_RATIO", "1.0")
)
QUALITY_MIN_OBJECT_MATCH_RATIO = float(os.getenv("QUALITY_MIN_OBJECT_MATCH_RATIO", "1.0"))
QUALITY_MAX_ERROR_COUNT = int(os.getenv("QUALITY_MAX_ERROR_COUNT", "0"))
INGESTION_TASK_TIMEOUT_MINUTES = int(os.getenv("INGESTION_TASK_TIMEOUT_MINUTES", "30"))
INGESTION_TASK_RETRIES = int(os.getenv("INGESTION_TASK_RETRIES", "1"))
INGESTION_TASK_RETRY_DELAY_MINUTES = int(os.getenv("INGESTION_TASK_RETRY_DELAY_MINUTES", "2"))


def _feed_output_path(run_index: int) -> Path:
    return INGESTION_ARTIFACT_DIR / f"crawl_feed_run_{run_index}.json"


def _report_output_path(run_index: int) -> Path:
    return INGESTION_ARTIFACT_DIR / f"crawl_report_run_{run_index}.json"


def _log_output_path(run_index: int) -> Path:
    return INGESTION_ARTIFACT_DIR / f"crawl_log_run_{run_index}.log"


@dag(
    dag_id="phase1_ingestion_dag",
    schedule=INGESTION_DAG_SCHEDULE,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    default_args={
        "owner": "ingestion",
        "retries": INGESTION_TASK_RETRIES,
        "retry_delay": timedelta(minutes=INGESTION_TASK_RETRY_DELAY_MINUTES),
        "execution_timeout": timedelta(minutes=INGESTION_TASK_TIMEOUT_MINUTES),
    },
    tags=["phase1", "wbs-1.9", "ingestion"],
)
def build_phase1_ingestion_dag():
    @task
    def load_source_registry_task() -> dict[str, object]:
        selected_sources = resolve_selected_sources(
            source_id=INGESTION_SOURCE_ID,
            registry_path=INGESTION_REGISTRY_PATH,
        )
        return {
            "selected_sources": selected_sources,
            "iterations": INGESTION_DEMO_ITERATIONS,
            "max_pages_per_source": INGESTION_MAX_PAGES_PER_SOURCE,
            "artifact_dir": str(INGESTION_ARTIFACT_DIR),
            "pdf_manifest_path": str(PDF_URL_DISCOVERY_PATH),
        }

    @task
    def fetch_pdf_sources() -> dict[str, object]:
        return summarize_pdf_manifest(PDF_URL_DISCOVERY_PATH)

    @task
    def build_manifest_task(source_summary: dict[str, object], pdf_summary: dict[str, object]) -> dict[str, object]:
        feed_output_paths = [_feed_output_path(index + 1) for index in range(INGESTION_DEMO_ITERATIONS)]
        report_output_paths = [_report_output_path(index + 1) for index in range(INGESTION_DEMO_ITERATIONS)]
        crawl_reports = load_crawl_reports(
            report_output_paths
        )
        manifest = build_ingestion_manifest(
            dag_id="phase1_ingestion_dag",
            selected_sources=source_summary["selected_sources"],  # type: ignore[index]
            crawl_reports=crawl_reports,
            pdf_summary=pdf_summary,
            max_pages_per_source=INGESTION_MAX_PAGES_PER_SOURCE,
            iterations=INGESTION_DEMO_ITERATIONS,
        )
        write_json_file(INGESTION_MANIFEST_PATH, manifest)
        return {
            **manifest,
            "manifest_path": str(INGESTION_MANIFEST_PATH),
            "feed_output_paths": [str(path) for path in feed_output_paths],
            "report_output_paths": [str(path) for path in report_output_paths],
        }

    source_summary = load_source_registry_task()

    crawl_tasks: list[BashOperator] = []
    for run_index in range(1, INGESTION_DEMO_ITERATIONS + 1):
        crawl_task = BashOperator(
            task_id=f"crawl_html_sources_run_{run_index}",
            bash_command=(
                "python /opt/project/scripts/run_html_crawl.py "
                f"--run-index {run_index} "
                f"--feed-output '{_feed_output_path(run_index)}' "
                f"--report-output '{_report_output_path(run_index)}' "
                f"--log-output '{_log_output_path(run_index)}' "
                f"--registry-path '{INGESTION_REGISTRY_PATH}' "
                f"--max-pages-per-source {INGESTION_MAX_PAGES_PER_SOURCE} "
                + (f"--source-id '{INGESTION_SOURCE_ID}' " if INGESTION_SOURCE_ID else "")
            ),
            append_env=True,
            env={
                "METADATA_DB_PATH": os.getenv("METADATA_DB_PATH", "metadata/crawl_state.db"),
                "PDF_URL_DISCOVERY_PATH": str(PDF_URL_DISCOVERY_PATH),
                "INGESTION_SOURCE_ID": INGESTION_SOURCE_ID or "",
                "INGESTION_REGISTRY_PATH": INGESTION_REGISTRY_PATH,
                "INGESTION_MAX_PAGES_PER_SOURCE": str(INGESTION_MAX_PAGES_PER_SOURCE),
            },
        )
        crawl_tasks.append(crawl_task)

    pdf_summary = fetch_pdf_sources()
    manifest = build_manifest_task(source_summary, pdf_summary)
    quality_command = (
        "python /opt/project/scripts/quality_check.py "
        f"--manifest-path '{INGESTION_MANIFEST_PATH}' "
        f"--quality-report-path '{INGESTION_QUALITY_REPORT_PATH}' "
        + " ".join(
            f"--feed-path '{_feed_output_path(run_index)}'"
            for run_index in range(1, INGESTION_DEMO_ITERATIONS + 1)
        )
        + f" --min-title-ratio {QUALITY_MIN_TITLE_RATIO}"
        + f" --min-text-preview-ratio {QUALITY_MIN_TEXT_PREVIEW_RATIO}"
        + f" --min-metadata-completeness-ratio {QUALITY_MIN_METADATA_COMPLETENESS_RATIO}"
        + f" --min-object-match-ratio {QUALITY_MIN_OBJECT_MATCH_RATIO}"
        + f" --max-error-count {QUALITY_MAX_ERROR_COUNT}"
    )
    quality = BashOperator(
        task_id="quality_check_task",
        bash_command=quality_command,
        append_env=True,
        env={
            "MINIO_ENDPOINT": os.getenv("MINIO_ENDPOINT", "minio:9000"),
            "MINIO_ROOT_USER": os.getenv("MINIO_ROOT_USER", "minioadmin"),
            "MINIO_ROOT_PASSWORD": os.getenv("MINIO_ROOT_PASSWORD", "change-me"),
            "MINIO_BUCKET_RAW": os.getenv("MINIO_BUCKET_RAW", "uet-raw"),
            "QUALITY_MIN_TITLE_RATIO": str(QUALITY_MIN_TITLE_RATIO),
            "QUALITY_MIN_TEXT_PREVIEW_RATIO": str(QUALITY_MIN_TEXT_PREVIEW_RATIO),
            "QUALITY_MIN_METADATA_COMPLETENESS_RATIO": str(QUALITY_MIN_METADATA_COMPLETENESS_RATIO),
            "QUALITY_MIN_OBJECT_MATCH_RATIO": str(QUALITY_MIN_OBJECT_MATCH_RATIO),
            "QUALITY_MAX_ERROR_COUNT": str(QUALITY_MAX_ERROR_COUNT),
        },
    )

    if crawl_tasks:
        source_summary >> crawl_tasks[0]
        for previous, current in zip(crawl_tasks, crawl_tasks[1:]):
            previous >> current
        crawl_tasks[-1] >> pdf_summary >> manifest >> quality
    else:
        source_summary >> pdf_summary >> manifest >> quality


phase1_ingestion_dag = build_phase1_ingestion_dag()
