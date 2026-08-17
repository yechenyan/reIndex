from __future__ import annotations

from pathlib import Path
from typing import Any

from .classification import classify_blocks
from .finalize import finalize_project
from .io_utils import atomic_json, read_json, sha256_file
from .liteparse_task import parse_document
from .paths import ProjectPaths
from .state import StateStore
from .table_agent_task import process_table
from .table_prep import merge_candidates, table_items


def execute_project(paths: ProjectPaths) -> dict[str, Any]:
    job = read_json(paths.job)
    pdf_path = Path(job["demand"]["inputPath"])
    _validate_source(job, pdf_path)
    store = StateStore(paths)
    state = store.load()
    if state["pdfHash"] != job["pdfInfo"]["sha256"]:
        raise ValueError("Project state belongs to a different PDF")
    if not store.completed("liteparse"):
        with store.step("liteparse", executor="runtime") as event:
            document = parse_document(paths, pdf_path)
            event["pages"] = document["totalPages"]
            event["pageErrors"] = len(document["pageErrors"])
            job["pdfInfo"]["totalPages"] = document["totalPages"]
            job["pdfInfo"]["pages"] = [
                {"page": page["page"], "widthPt": page["widthPt"], "heightPt": page["heightPt"]}
                for page in document["pages"]
            ]
            atomic_json(paths.job, job)
    if not store.completed("classify"):
        with store.step("classify", executor="classify-agent") as event:
            classified = classify_blocks(paths, pdf_path)
            event["tokenUsage"] = classified["usage"]
    _process_tables(paths, pdf_path, store)
    with store.step("finalize", executor="runtime") as event:
        report = finalize_project(paths)
        event["tables"] = report["tables"]
        event["problemTables"] = report["problemTables"]
    state = store.load()
    state["status"] = "completed_with_warnings" if report["problemTables"] else "completed"
    store.save(state)
    return report


def _process_tables(paths: ProjectPaths, pdf_path: Path, store: StateStore) -> None:
    classified = read_json(paths.helper / "classifiedBlocks.json")
    items = table_items(classified)
    parsed = read_json(paths.helper / "parsedBlocks.json", [])
    consumed = {identifier for item in parsed for identifier in item["classifyBlockIds"]}
    for index, item in enumerate(items):
        if item["classifyBlockId"] in consumed:
            continue
        table_id = f"table-{index + 1:04d}"
        existing = next((value for value in parsed if value["parseBlockId"] == table_id), None)
        if existing:
            consumed.update(existing["classifyBlockIds"])
            continue
        candidates = [candidate for candidate in merge_candidates(items, index) if candidate["classifyBlockId"] not in consumed]
        with store.step(f"table:{table_id}", executor="table-agent") as event:
            result = process_table(paths, pdf_path, table_id, candidates)
            event["tableStatus"] = result["status"]
            event["tokenUsage"] = result["usage"]
            event["repairs"] = result["repairs"]
        parsed.append(result)
        atomic_json(paths.helper / "parsedBlocks.json", parsed)
        consumed.update(result["classifyBlockIds"])


def _validate_source(job: dict[str, Any], pdf_path: Path) -> None:
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    if sha256_file(pdf_path) != job["pdfInfo"]["sha256"]:
        raise ValueError("Source PDF changed after project initialization")
