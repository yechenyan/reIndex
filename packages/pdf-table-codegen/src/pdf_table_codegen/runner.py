from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

from pdf_table_codegen.job import Job, load_job
from pdf_table_codegen.models import ExtractionRequest, ExtractionResult, source_sha256
from pdf_table_codegen.output import write_result, write_verification
from pdf_table_codegen.reference import load_reference, verify_reference


def _module(path: Path) -> ModuleType:
    if not path.is_file():
        raise FileNotFoundError(f"extractor not found: {path}")
    spec = importlib.util.spec_from_file_location(f"pdf_table_extractor_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load extractor: {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _extract(job: Job) -> ExtractionResult:
    module = _module(job.extractor)
    request = ExtractionRequest(source=job.source, strict=True, parameters=job.policy)
    if hasattr(module, "can_handle"):
        compatibility = module.can_handle(job.source)
        if not compatibility.supported:
            raise ValueError(f"extractor rejected source: {compatibility.reason}")
    result = module.extract_tables(request)
    if not isinstance(result, ExtractionResult):
        raise TypeError("extract_tables() must return ExtractionResult")
    table_ids = [table.id for table in result.tables]
    if len(set(table_ids)) != len(table_ids):
        raise ValueError("table IDs must be unique")
    for table in result.tables:
        if not table.rows and not job.policy.get("allow_empty_tables", False):
            raise ValueError(f"table {table.id!r} has no data rows")
        if any(len(row) != len(table.headers) for row in table.rows):
            raise ValueError(f"table {table.id!r} has inconsistent row widths")
        if table.provenance and len(table.provenance) != len(table.rows):
            raise ValueError(f"table {table.id!r} provenance must align with rows")
    if not result.qa.ok:
        raise ValueError("extractor QA failed")
    return result


def run_job(path: Path) -> ExtractionResult:
    job = load_job(path)
    result = _extract(job)
    write_result(result, job.output_dir)
    return result


def _table_ids(document: dict) -> list[str]:
    return sorted(str(table["id"]) for table in document.get("tables", []))


def verify_job(path: Path) -> dict:
    job = load_job(path)
    if not job.reference.is_file():
        raise FileNotFoundError(f"visual reference not found: {job.reference}")
    result = _extract(job)
    write_result(result, job.output_dir)
    reference = load_reference(job.reference)
    report = verify_reference(result, reference)
    expected_inventory = reference.get("inventory_sha256")
    actual_inventory = source_sha256(job.inventory) if job.inventory.is_file() else None
    inventory_check = {
        "name": "inventory_sha256",
        "ok": bool(expected_inventory) and actual_inventory == expected_inventory,
        "expected": expected_inventory,
        "actual": actual_inventory,
    }
    inventory = json.loads(job.inventory.read_text(encoding="utf-8"))
    expected_table_ids = _table_ids(inventory)
    reference_table_ids = _table_ids(reference)
    result_table_ids = sorted(table.id for table in result.tables)
    table_ids_check = {
        "name": "full_table_inventory",
        "ok": expected_table_ids == reference_table_ids == result_table_ids,
        "expected": expected_table_ids,
        "actual": {
            "reference": reference_table_ids,
            "result": result_table_ids,
        },
    }
    report["checks"].insert(1, inventory_check)
    report["checks"].insert(2, table_ids_check)
    report["ok"] = report["ok"] and inventory_check["ok"] and table_ids_check["ok"]
    write_verification(report, job.output_dir)
    return report
