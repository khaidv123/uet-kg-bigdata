"""Manual Airflow smoke DAG for WBS 0.5 readiness checks."""

from __future__ import annotations

import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

from data_ingestion.airflow_smoke import run_runtime_smoke

SMOKE_CONFIG_PATH = (
    os.getenv("AIRFLOW_SMOKE_CONFIG_PATH") or "/opt/project/config/airflow_smoke_config.json"
)
SMOKE_REPORT_PATH = (
    os.getenv("AIRFLOW_SMOKE_REPORT_PATH") or "/opt/project/metadata/airflow_smoke_report.json"
)


@dag(
    dag_id="airflow_smoke_dag",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    default_args={"owner": "infra"},
    tags=["phase0", "wbs-0.5", "smoke"],
)
def build_airflow_smoke_dag():
    """Verify the mounted Airflow runtime can see project assets."""

    @task
    def inspect_airflow_runtime() -> dict[str, object]:
        path_checks = {
            "dags_dir": os.path.isdir("/opt/airflow/dags"),
            "scripts_dir": os.path.isdir("/opt/project/scripts"),
            "config_dir": os.path.isdir("/opt/project/config"),
            "metadata_dir": os.path.isdir("/opt/project/metadata"),
        }
        return {
            "cwd": os.getcwd(),
            "config_path": SMOKE_CONFIG_PATH,
            "report_path": SMOKE_REPORT_PATH,
            "path_checks": path_checks,
        }

    @task
    def verify_python_runtime() -> dict[str, object]:
        summary = run_runtime_smoke(SMOKE_CONFIG_PATH, report_path=SMOKE_REPORT_PATH)
        return {
            "report_path": SMOKE_REPORT_PATH,
            "validated_modules": sorted(summary["modules"]),
            "validated_files": sorted(summary["sample_files"]),
        }

    run_script_smoke = BashOperator(
        task_id="run_script_smoke",
        bash_command=(
            "python /opt/project/scripts/airflow_runtime_smoke.py "
            "--config \"$AIRFLOW_SMOKE_CONFIG_PATH\" "
            "--output \"$AIRFLOW_SMOKE_REPORT_PATH\""
        ),
        append_env=True,
        env={
            "AIRFLOW_SMOKE_CONFIG_PATH": SMOKE_CONFIG_PATH,
            "AIRFLOW_SMOKE_REPORT_PATH": SMOKE_REPORT_PATH,
        },
    )

    inspect_airflow_runtime() >> verify_python_runtime() >> run_script_smoke


airflow_smoke_dag = build_airflow_smoke_dag()
