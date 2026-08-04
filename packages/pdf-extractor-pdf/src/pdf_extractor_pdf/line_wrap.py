from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pdf_extractor_pdf.artifacts import read_json, write_json
from pdf_extractor_pdf.job import Job

DECISIONS = {"keep", "remove"}


def classify_line_wrap_candidate(line_end: str, next_line_start: str) -> str | None:
    """Resolve only obvious visual wraps; leave ambiguous pairs to QA."""
    if not line_end.endswith("-") or not next_line_start:
        return None
    first = next_line_start[0]
    if first.islower():
        return "remove"
    if first.isupper() or first.isdigit():
        return "keep"
    return None


def normalize_visual_line_wrap(value: object, decisions: list[dict]) -> str:
    """Apply frozen visual-wrap decisions without any language dictionary."""
    text = "" if value is None else str(value).replace("\u00ad", "")
    for item in decisions:
        left, right = item["line_end"], item["next_line_start"]
        pattern = re.escape(left) + r"\s*" + re.escape(right)
        replacement = left[:-1] + right if item["decision"] == "remove" else left + right
        text = re.sub(pattern, replacement, text)
    return text


def candidates_for_job(job: Job, selected: set[str]) -> dict[str, list[dict]]:
    manifest = read_json(job.evidence_dir / "segments" / "manifest.json")
    grouped: dict[str, dict[tuple[str, str], dict]] = {}
    for segment in manifest["segments"]:
        table_id = segment["table_id"]
        if table_id not in selected:
            continue
        geometry = read_json(Path(segment["geometry"]))
        for candidate in _geometry_candidates(segment, geometry):
            key = (candidate["line_end"], candidate["next_line_start"])
            current = grouped.setdefault(table_id, {}).setdefault(key, {
                "id": _candidate_id(table_id, *key),
                "line_end": key[0], "next_line_start": key[1],
                "decision": classify_line_wrap_candidate(*key),
                "decision_source": "code" if classify_line_wrap_candidate(*key) else None,
                "occurrences": [],
            })
            current["occurrences"].extend(candidate["occurrences"])
    return {table_id: list(values.values()) for table_id, values in grouped.items()}


def validate_decisions(candidates: list[dict], table_id: str) -> list[dict]:
    seen = set()
    for item in candidates:
        required = {"id", "line_end", "next_line_start", "decision", "occurrences"}
        if not required.issubset(item) or item["decision"] not in DECISIONS:
            raise ValueError(f"{table_id}: every line-wrap candidate needs a keep/remove decision")
        expected = _candidate_id(table_id, item["line_end"], item["next_line_start"])
        if item["id"] != expected or item["id"] in seen:
            raise ValueError(f"{table_id}: invalid or duplicate line-wrap candidate")
        automatic = classify_line_wrap_candidate(item["line_end"], item["next_line_start"])
        if automatic and (item["decision"] != automatic or item.get("decision_source") != "code"):
            raise ValueError(f"{table_id}: code-classified line-wrap decision cannot be changed")
        if not automatic:
            item["decision_source"] = "qa"
        seen.add(item["id"])
    return candidates


def apply_table_decisions(table: dict, decisions: list[dict]) -> dict:
    table = {**table}
    table["rows"] = [[normalize_visual_line_wrap(value, decisions) for value in row] for row in table.get("rows", [])]
    if "samples" in table:
        table["samples"] = [
            {**sample, "values": [normalize_visual_line_wrap(value, decisions) for value in sample.get("values", [])]}
            for sample in table["samples"]
        ]
    table["line_wrap_decisions"] = decisions
    return table


def apply_result(reference: dict, result: dict) -> dict:
    decisions = {item["id"]: item.get("line_wrap_decisions", []) for item in reference.get("tables", [])}
    return {
        **result,
        "tables": [apply_table_decisions(table, decisions.get(table.get("id"), [])) for table in result.get("tables", [])],
    }


def write_decision_artifact(job: Job, tables: list[dict]) -> Path:
    value = {
        "spec": "pdf-extractor-pdf/normalization-decisions@1.0",
        "tables": [
            {"id": table["id"], "line_wrap_decisions": table.get("line_wrap_decisions", [])}
            for table in tables
        ],
    }
    return write_json(job.evidence_dir / "normalization-decisions.json", value)


def _geometry_candidates(segment: dict, geometry: dict) -> list[dict]:
    blocks: dict[int, dict[int, list[list]]] = {}
    for word in geometry.get("words", []):
        if len(word) < 8:
            continue
        blocks.setdefault(int(word[5]), {}).setdefault(int(word[6]), []).append(word)
    line_ends = []
    line_starts = []
    same_block_next = {}
    for block_no, lines in blocks.items():
        ordered_lines = sorted(lines)
        for left_no, right_no in zip(ordered_lines, ordered_lines[1:]):
            same_block_next[(block_no, left_no)] = sorted(lines[right_no], key=lambda x: x[7])[0]
        for line_no, words in lines.items():
            ordered = sorted(words, key=lambda x: x[7])
            line_starts.append(ordered[0])
            if _candidate_token(ordered[-1][4]):
                line_ends.append((block_no, line_no, ordered[-1]))
    values = []
    for block_no, line_no, left in line_ends:
        right = same_block_next.get((block_no, line_no)) or _nearest_continuation(left, line_starts)
        if right is None:
            continue
        values.append({
            "line_end": left[4], "next_line_start": right[4],
            "occurrences": [{
                "segment_id": segment["segment_id"], "page": segment["page"],
                "block": block_no, "line": line_no, "bbox": _union_bbox(left, right),
                "image": segment["image"],
            }],
        })
    return values


def _nearest_continuation(left: list, starts: list[list]) -> list | None:
    height = max(1.0, left[3] - left[1])
    candidates = []
    for right in starts:
        gap = right[1] - left[1]
        overlap = min(left[2], right[2]) - max(left[0], right[0])
        if height * 0.5 < gap <= height * 2.5 and overlap > 0:
            candidates.append((gap, -overlap, right))
    return min(candidates, default=(0, 0, None), key=lambda item: item[:2])[2]


def _candidate_token(value: object) -> bool:
    text = str(value)
    return len(text) > 1 and text.endswith("-") and text not in {"-", "+/-"} and not text.endswith("/-")


def _candidate_id(table_id: str, left: str, right: str) -> str:
    digest = hashlib.sha256(f"{table_id}\0{left}\0{right}".encode()).hexdigest()[:12]
    return f"wrap-{digest}"


def _union_bbox(left: list, right: list) -> list[float]:
    return [min(left[0], right[0]), min(left[1], right[1]), max(left[2], right[2]), max(left[3], right[3])]
