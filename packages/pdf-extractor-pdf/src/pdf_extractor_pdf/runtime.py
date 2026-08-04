from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from pdf_extractor_pdf.models import ExtractionResult


def project_entry(extract: Callable[[Path, dict], ExtractionResult | dict]) -> None:
    parser = argparse.ArgumentParser(description="Run or structurally check this PDF-specific extractor.")
    parser.add_argument("action", choices=["run", "check"])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    value = extract(args.source, inventory)
    result = value.to_dict() if isinstance(value, ExtractionResult) else value
    _check_result(result)
    if args.action == "run":
        if not args.result:
            parser.error("--result is required for run")
        args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps({"ok": True, "tables": len(result["tables"])}, ensure_ascii=False))


def _check_result(result: dict) -> None:
    if not isinstance(result, dict) or not isinstance(result.get("tables"), list):
        raise ValueError("extractor must return a result object with tables")
    ids = []
    for table in result["tables"]:
        ids.append(table.get("id"))
        columns, rows = table.get("columns"), table.get("rows")
        provenance = table.get("provenance")
        if not isinstance(columns, list) or not columns or len(set(columns)) != len(columns):
            raise ValueError(f"invalid columns for table {table.get('id')}")
        if not isinstance(rows, list) or any(len(row) != len(columns) for row in rows):
            raise ValueError(f"inconsistent rows for table {table.get('id')}")
        if not isinstance(provenance, list) or len(provenance) != len(rows):
            raise ValueError(f"provenance must align with rows for table {table.get('id')}")
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError("table IDs must be non-empty and unique")
