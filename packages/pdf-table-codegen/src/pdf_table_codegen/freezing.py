from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pdf_table_codegen.job import Job
from pdf_table_codegen.models import source_sha256
from pdf_table_codegen.reference import sample_indices

_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")
    temporary.replace(path)


def _ids(value: dict[str, Any]) -> list[str]:
    tables = value.get("tables")
    if not isinstance(tables, list):
        raise ValueError("tables must be a list")
    ids = [str(table.get("id", "")) for table in tables]
    if any(not _ID.fullmatch(table_id) for table_id in ids):
        raise ValueError("table IDs must use lowercase letters, digits, dot, dash, or underscore")
    if len(ids) != len(set(ids)):
        raise ValueError("table IDs must be unique")
    return ids


def _validate_inventory(value: dict[str, Any], page_count: int) -> None:
    _ids(value)
    for table in value["tables"]:
        pages = table.get("pages")
        if not isinstance(pages, list) or not pages:
            raise ValueError(f"table {table['id']!r} must list pages")
        if any(not isinstance(page, int) or not 1 <= page <= page_count for page in pages):
            raise ValueError(f"table {table['id']!r} has an invalid page")
        for segment in table.get("segments", []):
            bbox = segment.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise ValueError(f"table {table['id']!r} segment bbox must have four numbers")
            if not all(isinstance(item, (int, float)) for item in bbox):
                raise ValueError(f"table {table['id']!r} segment bbox must be numeric")
            if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                raise ValueError(f"table {table['id']!r} segment bbox is empty")


def freeze_inventory(job: Job, draft: Path) -> dict[str, Any]:
    manifest_path = job.evidence_dir / "manifest.json"
    manifest = _read(manifest_path)
    current_source = source_sha256(job.source)
    if manifest.get("source_sha256") != current_source:
        raise ValueError("evidence manifest does not match the current source")
    body = _read(draft)
    _validate_inventory(body, int(manifest["page_count"]))
    frozen = {
        "spec": "pdf-table-codegen/inventory@1.0",
        "status": "frozen",
        "scope": body.get("scope", "full_document"),
        "source_sha256": current_source,
        "evidence_manifest_sha256": source_sha256(manifest_path),
        **{key: value for key, value in body.items() if key not in {"spec", "status", "scope", "source_sha256", "evidence_manifest_sha256"}},
    }
    _write(job.inventory, frozen)
    return frozen


def _required_samples(table: dict[str, Any], inventory_table: dict[str, Any]) -> set[int]:
    required = set(sample_indices(int(table["row_count"])))
    segments = inventory_table.get("segments", [])
    for before, after in zip(segments, segments[1:]):
        left = before.get("data_rows")
        right = after.get("data_rows")
        if isinstance(left, list) and len(left) == 2:
            required.add(int(left[1]) - 1)
        if isinstance(right, list) and len(right) == 2:
            required.add(int(right[0]) - 1)
    return required


def freeze_reference(job: Job, draft: Path) -> dict[str, Any]:
    inventory = _read(job.inventory)
    current_source = source_sha256(job.source)
    if inventory.get("source_sha256") != current_source:
        raise ValueError("frozen inventory does not match the current source")
    body = _read(draft)
    if _ids(body) != _ids(inventory):
        raise ValueError("reference table IDs and order must match the inventory")
    inventory_tables = {table["id"]: table for table in inventory["tables"]}
    for table in body["tables"]:
        columns = int(table["column_count"])
        rows = int(table["row_count"])
        if len(table.get("header", [])) != columns:
            raise ValueError(f"reference {table['id']!r} header width mismatch")
        samples = {int(sample["row_index"]): sample for sample in table.get("samples", [])}
        if not _required_samples(table, inventory_tables[table["id"]]).issubset(samples):
            raise ValueError(f"reference {table['id']!r} is missing required source samples")
        if any(index < 0 or index >= rows for index in samples):
            raise ValueError(f"reference {table['id']!r} has an invalid sample index")
        if any(len(sample.get("values", [])) != columns for sample in samples.values()):
            raise ValueError(f"reference {table['id']!r} sample width mismatch")
    frozen = {
        "spec": "pdf-table-codegen/reference@1.0",
        "status": "frozen_before_extractor_output",
        "scope": inventory.get("scope", "full_document"),
        "source_sha256": current_source,
        "inventory_sha256": source_sha256(job.inventory),
        **{key: value for key, value in body.items() if key not in {"spec", "status", "scope", "source_sha256", "inventory_sha256"}},
    }
    _write(job.reference, frozen)
    return frozen
