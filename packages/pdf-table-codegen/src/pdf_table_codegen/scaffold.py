from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pdf_table_codegen.job import Job
from pdf_table_codegen.models import source_sha256


def build_assertion_hints(job: Job) -> dict[str, Any]:
    reference = json.loads(job.reference.read_text(encoding="utf-8"))
    inventory_hash = source_sha256(job.inventory)
    if reference.get("inventory_sha256") != inventory_hash:
        raise ValueError("reference does not match the current inventory")
    tables = []
    for table in reference.get("tables", []):
        tables.append({
            "id": table["id"],
            "required_shape": [int(table["row_count"]), int(table["column_count"])],
            "required_header": table["header"],
            "source_sample_anchors": [
                {"row_index": int(sample["row_index"]), "values": sample["values"]}
                for sample in table.get("samples", [])
            ],
            "agent_action": "Select stable, table-specific anchors and add drift checks; do not use these values to construct extracted rows.",
        })
    value = {
        "spec": "pdf-table-codegen/assertion-hints@1.0",
        "source_sha256": source_sha256(job.source),
        "inventory_sha256": inventory_hash,
        "table_order": [table["id"] for table in reference.get("tables", [])],
        "tables": tables,
    }
    target = job.evidence_dir / "assertion-hints.json"
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return value
