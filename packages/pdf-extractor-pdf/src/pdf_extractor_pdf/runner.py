from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from pdf_extractor_pdf.artifacts import read_json, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.workflow import require_phase


def execute(job: Job) -> dict:
    require_phase(job.evidence_dir, "reference_frozen")
    result = _invoke(job)
    _write_outputs(job, result)
    return result


def invoke_twice(job: Job) -> tuple[dict, dict]:
    require_phase(job.evidence_dir, "reference_frozen", "reviewed")
    return _invoke(job), _invoke(job)


def _invoke(job: Job) -> dict:
    if not job.main.is_file():
        raise FileNotFoundError(job.main)
    timeout = int(job.policy.get("extractor_timeout_seconds", 120))
    with TemporaryDirectory(prefix="pdf-extractor-pdf-") as temporary:
        result_path = Path(temporary) / "result.json"
        command = [
            sys.executable, str(job.main), "run",
            "--source", str(job.source), "--inventory", str(job.inventory),
            "--result", str(result_path),
        ]
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
        completed = subprocess.run(
            command, cwd=job.main.parent, env=environment, timeout=timeout,
            text=True, capture_output=True, check=False,
        )
        if completed.returncode:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"extractor exited {completed.returncode}: {message[-2000:]}")
        if not result_path.is_file():
            raise RuntimeError("extractor did not write result.json")
        return read_json(result_path)


def _write_outputs(job: Job, result: dict) -> None:
    job.output_dir.mkdir(parents=True, exist_ok=True)
    old_result = job.output_dir / "result.json"
    if old_result.is_file():
        for table in read_json(old_result).get("tables", []):
            (job.output_dir / f"{table.get('id')}.csv").unlink(missing_ok=True)
    for table in result["tables"]:
        path = job.output_dir / f"{table['id']}.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(table["columns"])
            writer.writerows(table["rows"])
    write_json(old_result, result)
