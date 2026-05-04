#!/usr/bin/env python3
"""Manual Phase 2 pipeline orchestrator.

Defaults are intentionally small:
- ingest 10 raw docs
- run_extraction 100 requests
- run_concept_generation 100 requests
- compute_embeddings 100 requests
- skip export_graph
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.common.config_loader import load_yaml


STEP_ORDER = [
    "ingest_documents",
    "clean_documents",
    "chunk_documents",
    "build_extraction_requests",
    "run_extraction",
    "validate_extraction",
    "build_graph_base",
    "build_node_context",
    "build_concept_requests",
    "run_concept_generation",
    "validate_concepts",
    "merge_concepts",
    "compute_embeddings",
]

STEP_TO_JOB = {
    "ingest_documents": "01_ingest_documents.py",
    "clean_documents": "02_clean_documents.py",
    "chunk_documents": "03_chunk_documents.py",
    "build_extraction_requests": "04_build_extraction_requests.py",
    "run_extraction": "05_run_extraction.py",
    "validate_extraction": "06_validate_extraction.py",
    "build_graph_base": "07_build_graph_base.py",
    "build_node_context": "08_build_node_context.py",
    "build_concept_requests": "09_build_concept_requests.py",
    "run_concept_generation": "10_run_concept_generation.py",
    "validate_concepts": "11_validate_concepts.py",
    "merge_concepts": "12_merge_concepts.py",
    "compute_embeddings": "14_compute_embeddings.py",
}

RUN_ID_KEYS = {
    "INGEST_RUN_ID",
    "CLEAN_RUN_ID",
    "CHUNK_RUN_ID",
    "EXTRACTION_REQUEST_RUN_ID",
    "EXTRACTION_RAW_RUN_ID",
    "VALIDATE_EXTRACTION_RUN_ID",
    "GRAPH_BASE_RUN_ID",
    "NODE_CONTEXT_RUN_ID",
    "CONCEPT_REQUEST_RUN_ID",
    "CONCEPT_RAW_RUN_ID",
    "VALIDATE_CONCEPT_RUN_ID",
    "MERGE_CONCEPT_RUN_ID",
    "EMBEDDING_RUN_ID",
}

STEP_RUN_ID_KEY = {
    "ingest_documents": "INGEST_RUN_ID",
    "clean_documents": "CLEAN_RUN_ID",
    "chunk_documents": "CHUNK_RUN_ID",
    "build_extraction_requests": "EXTRACTION_REQUEST_RUN_ID",
    "run_extraction": "EXTRACTION_RAW_RUN_ID",
    "validate_extraction": "VALIDATE_EXTRACTION_RUN_ID",
    "build_graph_base": "GRAPH_BASE_RUN_ID",
    "build_node_context": "NODE_CONTEXT_RUN_ID",
    "build_concept_requests": "CONCEPT_REQUEST_RUN_ID",
    "run_concept_generation": "CONCEPT_RAW_RUN_ID",
    "validate_concepts": "VALIDATE_CONCEPT_RUN_ID",
    "merge_concepts": "MERGE_CONCEPT_RUN_ID",
    "compute_embeddings": "EMBEDDING_RUN_ID",
}


@dataclass
class StepResult:
    step: str
    job: str
    command: list[str]
    started_ts: str
    ended_ts: str
    wall_seconds: float
    returncode: int
    metrics: dict[str, str] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(repo_root))
    parser.add_argument("--run-label", default=None)
    parser.add_argument("--start-step", choices=STEP_ORDER, default=None)
    parser.add_argument("--end-step", choices=STEP_ORDER, default=None)
    parser.add_argument("--ingest-limit", default=None, help="Integer limit or 'all'")
    parser.add_argument("--extraction-limit", default=None, help="Integer limit or 'all'")
    parser.add_argument("--concept-limit", default=None, help="Integer limit or 'all'")
    parser.add_argument("--embedding-limit", default=None, help="Integer limit or 'all'")
    parser.add_argument("--full", action="store_true", help="Shortcut for all limits = all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-path", default=None)
    parser.add_argument("--markdown-report-path", default=None)
    parser.add_argument(
        "--state-path",
        default=None,
        help="Optional previous orchestration JSON report used to seed run ids for resume.",
    )
    parser.add_argument("--source-run-id", default=None, help="Raw normalized source run for ingest")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_limit(value: str | None, default_value: int | None, *, full: bool) -> int | None:
    if full:
        return None
    if value is None:
        return default_value
    clean = str(value).strip().lower()
    if clean in {"", "none", "all", "full"}:
        return None
    parsed = int(clean)
    if parsed < 0:
        raise ValueError(f"Limit must be non-negative or all, got {value}")
    return parsed


def selected_steps(start_step: str, end_step: str) -> list[str]:
    start_idx = STEP_ORDER.index(start_step)
    end_idx = STEP_ORDER.index(end_step)
    if start_idx > end_idx:
        raise ValueError(f"start-step must be before end-step: {start_step} > {end_step}")
    return STEP_ORDER[start_idx : end_idx + 1]


def spark_job_command(job_name: str, job_args: list[str]) -> list[str]:
    inner = "/bin/bash /workspace/scripts/spark_submit_phase2.sh " + " ".join(
        [f"/workspace/pipeline/jobs/{job_name}", *job_args]
    )
    return [
        "docker",
        "compose",
        "-f",
        "docker-compose.phase2.yml",
        "run",
        "--rm",
        "--no-deps",
        "spark-submit",
        "/bin/bash",
        "-lc",
        inner,
    ]


def parse_metrics(output: str) -> dict[str, str]:
    metrics: dict[str, str] = {}
    pattern = re.compile(r"^([A-Z][A-Z0-9_]+)=(.*)$")
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if match:
            metrics[match.group(1)] = match.group(2)
    return metrics


def run_step(repo_root: Path, step: str, job_args: list[str], *, dry_run: bool) -> StepResult:
    job_name = STEP_TO_JOB[step]
    command = spark_job_command(job_name, job_args)
    started = utc_now()
    started_monotonic = time.monotonic()
    if dry_run:
        print("DRY_RUN_STEP=" + step)
        print("DRY_RUN_COMMAND=" + " ".join(command))
        metric_key = STEP_RUN_ID_KEY.get(step)
        metrics = {metric_key: f"dryrun-{step}"} if metric_key else {}
        return StepResult(
            step=step,
            job=job_name,
            command=command,
            started_ts=started,
            ended_ts=utc_now(),
            wall_seconds=0.0,
            returncode=0,
            metrics=metrics,
        )

    print(f"\n=== RUNNING {step} ({job_name}) ===", flush=True)
    print("COMMAND=" + " ".join(command), flush=True)
    completed = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    ended = utc_now()
    wall_seconds = time.monotonic() - started_monotonic
    print(completed.stdout, flush=True)
    metrics = parse_metrics(completed.stdout)
    result = StepResult(
        step=step,
        job=job_name,
        command=command,
        started_ts=started,
        ended_ts=ended,
        wall_seconds=wall_seconds,
        returncode=completed.returncode,
        metrics=metrics,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Step failed: {step} returncode={completed.returncode}")
    return result


def add_limit_arg(args: list[str], name: str, value: int | None) -> None:
    if value is not None:
        args.extend([name, str(value)])


def args_for_step(step: str, state: dict[str, str], limits: dict[str, int | None], source_run_id: str | None) -> list[str]:
    if step == "ingest_documents":
        args: list[str] = []
        if source_run_id:
            args.extend(["--source-run-id", source_run_id])
        add_limit_arg(args, "--limit", limits["ingest"])
        return args
    if step == "clean_documents":
        return ["--source-run-id", state["INGEST_RUN_ID"]]
    if step == "chunk_documents":
        return ["--source-run-id", state["CLEAN_RUN_ID"]]
    if step == "build_extraction_requests":
        return ["--source-run-id", state["CHUNK_RUN_ID"]]
    if step == "run_extraction":
        args = ["--source-run-id", state["EXTRACTION_REQUEST_RUN_ID"]]
        add_limit_arg(args, "--limit", limits["extraction"])
        return args
    if step == "validate_extraction":
        return [
            "--source-run-id",
            state["EXTRACTION_RAW_RUN_ID"],
            "--chunk-run-id",
            state["CHUNK_RUN_ID"],
        ]
    if step == "build_graph_base":
        return ["--source-run-id", state["VALIDATE_EXTRACTION_RUN_ID"]]
    if step == "build_node_context":
        return ["--source-run-id", state["GRAPH_BASE_RUN_ID"]]
    if step == "build_concept_requests":
        return [
            "--graph-base-run-id",
            state["GRAPH_BASE_RUN_ID"],
            "--node-context-run-id",
            state["NODE_CONTEXT_RUN_ID"],
        ]
    if step == "run_concept_generation":
        args = [
            "--source-run-id",
            state["CONCEPT_REQUEST_RUN_ID"],
            "--graph-base-run-id",
            state["GRAPH_BASE_RUN_ID"],
            "--selection-strategy",
            "priority",
        ]
        add_limit_arg(args, "--limit", limits["concept"])
        return args
    if step == "validate_concepts":
        return [
            "--concept-request-run-id",
            state["CONCEPT_REQUEST_RUN_ID"],
            "--missing-concepts-run-id",
            state["GRAPH_BASE_RUN_ID"],
            "--raw-run-ids",
            state["CONCEPT_RAW_RUN_ID"],
        ]
    if step == "merge_concepts":
        return [
            "--graph-base-run-id",
            state["GRAPH_BASE_RUN_ID"],
            "--concept-run-id",
            state["VALIDATE_CONCEPT_RUN_ID"],
        ]
    if step == "compute_embeddings":
        args = [
            "--graph-base-run-id",
            state["GRAPH_BASE_RUN_ID"],
            "--node-context-run-id",
            state["NODE_CONTEXT_RUN_ID"],
            "--merge-run-id",
            state["MERGE_CONCEPT_RUN_ID"],
        ]
        add_limit_arg(args, "--limit", limits["embedding"])
        return args
    raise ValueError(f"Unknown step: {step}")


def update_state_from_metrics(state: dict[str, str], metrics: dict[str, str]) -> None:
    for key in RUN_ID_KEYS:
        value = metrics.get(key)
        if value:
            state[key] = value


def load_initial_state(state_path: str | None) -> dict[str, str]:
    if not state_path:
        return {}
    path = Path(state_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_state = payload.get("final_state", payload)
    if not isinstance(raw_state, dict):
        raise ValueError(f"State file must contain an object or final_state object: {path}")
    state: dict[str, str] = {}
    for key, value in raw_state.items():
        if key in RUN_ID_KEYS and value:
            state[key] = str(value)
    return state


def write_reports(
    *,
    report_path: Path,
    markdown_report_path: Path,
    payload: dict[str, Any],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Phase 2 Orchestration Default Run Report",
        "",
        f"- Run label: `{payload['run_label']}`",
        f"- Started: `{payload['started_ts']}`",
        f"- Ended: `{payload['ended_ts']}`",
        f"- Wall seconds: `{payload['wall_seconds']:.2f}`",
        f"- Steps: `{payload['start_step']} -> {payload['end_step']}`",
        "",
        "## Runtime Defaults",
        "",
        "| Setting | Value |",
        "|---|---:|",
        f"| ingest limit | {payload['limits']['ingest'] if payload['limits']['ingest'] is not None else 'all'} |",
        f"| extraction limit | {payload['limits']['extraction'] if payload['limits']['extraction'] is not None else 'all'} |",
        f"| concept limit | {payload['limits']['concept'] if payload['limits']['concept'] is not None else 'all'} |",
        f"| embedding limit | {payload['limits']['embedding'] if payload['limits']['embedding'] is not None else 'all'} |",
        "",
        "## Step Summary",
        "",
        "| Step | Run id | Wall seconds | Key counts |",
        "|---|---|---:|---|",
    ]
    preferred_counts = [
        "INPUT_RECORD_COUNT",
        "OUTPUT_RECORD_COUNT",
        "OUTPUT_CHUNK_COUNT",
        "OUTPUT_REQUEST_COUNT",
        "FINAL_REQUEST_COUNT",
        "RAW_RECORD_COUNT",
        "STRUCTURED_RECORD_COUNT",
        "TRIPLE_EDGE_COUNT",
        "TRIPLE_NODE_COUNT",
        "OUTPUT_NODE_CONTEXT_COUNT",
        "OUTPUT_CONCEPT_REQUEST_COUNT",
        "MAPPING_RECORD_COUNT",
        "CONCEPT_NODE_COUNT",
        "CONCEPT_EDGE_COUNT",
        "SUCCESS_COUNT",
        "COVERAGE_STATUS_EMBEDDED",
    ]
    for step in payload["steps"]:
        metrics = step["metrics"]
        run_id_key = STEP_RUN_ID_KEY.get(step["step"])
        run_id = metrics.get(run_id_key, "") if run_id_key else ""
        counts = ", ".join(
            f"{key}={metrics[key]}" for key in preferred_counts if key in metrics
        )
        lines.append(f"| `{step['step']}` | `{run_id}` | {step['wall_seconds']:.2f} | {counts} |")

    lines.extend(
        [
            "",
            "## Final Run IDs",
            "",
            "| Key | Value |",
            "|---|---|",
        ]
    )
    for key, value in sorted(payload["final_state"].items()):
        lines.append(f"| `{key}` | `{value}` |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `export_graph` is intentionally skipped in this orchestration profile.")
    lines.append("- API-heavy stages are capped by default and can be set to `all` from CLI.")
    lines.append("- Intermediate tables are materialized on MinIO by run id, so reruns can resume from a chosen stage with `--state-path logs/<previous-run>.json --start-step <step>`.")
    lines.append("")
    lines.append("## Manual Trigger")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 scripts/run_phase2_pipeline.py")
    lines.append("python3 scripts/run_phase2_pipeline.py --ingest-limit all --extraction-limit all --concept-limit all --embedding-limit all")
    lines.append("python3 scripts/run_phase2_pipeline.py --state-path logs/phase2-default-20260427132044.json --start-step merge_concepts --end-step compute_embeddings")
    lines.append("```")
    markdown_report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    pipeline_cfg = load_yaml(repo_root / "config/pipeline_phase2.yaml")
    orchestration_cfg = pipeline_cfg.get("orchestration", {})

    start_step = args.start_step or str(orchestration_cfg.get("default_start_step", "ingest_documents"))
    end_step = args.end_step or str(orchestration_cfg.get("default_end_step", "compute_embeddings"))
    run_label = args.run_label or datetime.now(timezone.utc).strftime("phase2-default-%Y%m%d%H%M%S")

    limits = {
        "ingest": parse_limit(args.ingest_limit, int(orchestration_cfg.get("default_ingest_limit", 10)), full=args.full),
        "extraction": parse_limit(args.extraction_limit, int(orchestration_cfg.get("default_extraction_limit", 100)), full=args.full),
        "concept": parse_limit(args.concept_limit, int(orchestration_cfg.get("default_concept_limit", 100)), full=args.full),
        "embedding": parse_limit(args.embedding_limit, int(orchestration_cfg.get("default_embedding_limit", 100)), full=args.full),
    }

    report_path = Path(args.report_path or repo_root / "logs" / f"{run_label}.json")
    markdown_report_path = Path(
        args.markdown_report_path or repo_root / "docs" / "phase2_orchestration_default_run.md"
    )

    state = load_initial_state(args.state_path)
    results: list[StepResult] = []
    started_ts = utc_now()
    started_monotonic = time.monotonic()
    for step in selected_steps(start_step, end_step):
        job_args = args_for_step(step, state, limits, args.source_run_id)
        result = run_step(repo_root, step, job_args, dry_run=args.dry_run)
        update_state_from_metrics(state, result.metrics)
        results.append(result)

    payload = {
        "run_label": run_label,
        "started_ts": started_ts,
        "ended_ts": utc_now(),
        "wall_seconds": time.monotonic() - started_monotonic,
        "start_step": start_step,
        "end_step": end_step,
        "limits": limits,
        "dry_run": bool(args.dry_run),
        "final_state": state,
        "steps": [
            {
                "step": item.step,
                "job": item.job,
                "command": item.command,
                "started_ts": item.started_ts,
                "ended_ts": item.ended_ts,
                "wall_seconds": item.wall_seconds,
                "returncode": item.returncode,
                "metrics": item.metrics,
            }
            for item in results
        ],
    }
    write_reports(report_path=report_path, markdown_report_path=markdown_report_path, payload=payload)
    print(f"ORCHESTRATION_RUN_LABEL={run_label}")
    print(f"ORCHESTRATION_REPORT_PATH={report_path}")
    print(f"ORCHESTRATION_MARKDOWN_REPORT_PATH={markdown_report_path}")
    print(f"ORCHESTRATION_WALL_SECONDS={payload['wall_seconds']}")


if __name__ == "__main__":
    main()
