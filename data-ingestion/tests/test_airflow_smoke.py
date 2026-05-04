import json

import pytest

from data_ingestion.airflow_smoke import run_runtime_smoke


def test_run_runtime_smoke_writes_report(tmp_path) -> None:
    config_dir = tmp_path / "config"
    scripts_dir = tmp_path / "scripts"
    dags_dir = tmp_path / "dags"
    metadata_dir = tmp_path / "metadata"

    for directory in (config_dir, scripts_dir, dags_dir, metadata_dir):
        directory.mkdir()

    config_path = config_dir / "airflow_smoke_config.json"
    script_path = scripts_dir / "airflow_runtime_smoke.py"
    dag_path = dags_dir / "airflow_smoke_dag.py"
    report_path = metadata_dir / "airflow_smoke_report.json"

    script_path.write_text("# smoke script\n", encoding="utf-8")
    dag_path.write_text("# smoke dag\n", encoding="utf-8")

    config = {
        "required_env": ["AIRFLOW_HOME", "MINIO_ENDPOINT", "MINIO_BUCKET_RAW"],
        "required_mounts": {
            "config_dir": str(config_dir),
            "scripts_dir": str(scripts_dir),
            "dags_dir": str(dags_dir),
            "metadata_dir": str(metadata_dir),
        },
        "sample_files": {
            "config_file": str(config_path),
            "script_file": str(script_path),
            "dag_file": str(dag_path),
        },
        "required_modules": ["json", "pathlib"],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    summary = run_runtime_smoke(
        config_path,
        environ={
            "AIRFLOW_HOME": "/opt/airflow",
            "MINIO_ENDPOINT": "minio:9000",
            "MINIO_BUCKET_RAW": "uet-raw",
        },
        report_path=report_path,
    )

    assert summary["required_env"]["AIRFLOW_HOME"] == "/opt/airflow"
    assert report_path.exists()


def test_run_runtime_smoke_requires_env_values(tmp_path) -> None:
    config_dir = tmp_path / "config"
    scripts_dir = tmp_path / "scripts"
    dags_dir = tmp_path / "dags"

    for directory in (config_dir, scripts_dir, dags_dir):
        directory.mkdir()

    config_path = config_dir / "airflow_smoke_config.json"
    script_path = scripts_dir / "airflow_runtime_smoke.py"
    dag_path = dags_dir / "airflow_smoke_dag.py"

    script_path.write_text("# smoke script\n", encoding="utf-8")
    dag_path.write_text("# smoke dag\n", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "required_env": ["AIRFLOW_HOME"],
                "required_mounts": {
                    "config_dir": str(config_dir),
                    "scripts_dir": str(scripts_dir),
                    "dags_dir": str(dags_dir),
                },
                "sample_files": {
                    "config_file": str(config_path),
                    "script_file": str(script_path),
                    "dag_file": str(dag_path),
                },
                "required_modules": ["json"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(KeyError):
        run_runtime_smoke(config_path, environ={})
