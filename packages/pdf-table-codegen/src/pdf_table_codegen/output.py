from __future__ import annotations

import csv
import json
from pathlib import Path

from pdf_table_codegen.models import ExtractionResult


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def write_result(result: ExtractionResult, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for table in result.tables:
        path = output_dir / f"{table.id}.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(table.headers)
            writer.writerows(table.rows)
        written.append(path)
    result_path = output_dir / "result.json"
    _json(result_path, result.to_dict())
    written.append(result_path)
    return written


def write_verification(report: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "verification.json"
    _json(path, report)
    return path
