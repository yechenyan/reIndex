from __future__ import annotations

import re


def merge_candidates(result: dict, inventory: dict, threshold: float, decisions: dict) -> list[dict]:
    actual = {item["id"]: item for item in result.get("tables", [])}
    findings = {item["page"]: item for item in inventory.get("page_findings", [])}
    ordered = sorted(inventory["tables"], key=lambda item: min(x["page"] for x in item["segments"]))
    candidates = []
    for left, right in zip(ordered, ordered[1:]):
        if left["id"] not in actual or right["id"] not in actual:
            continue
        left_page = max(item["page"] for item in left["segments"])
        right_page = min(item["page"] for item in right["segments"])
        if right_page != left_page + 1:
            continue
        signals, contradictions = _continuity_signals(left, right, actual, findings.get(right_page, {}))
        confidence = _confidence(signals, contradictions)
        if confidence < 0.55:
            continue
        candidate = {
            "left": left["id"], "right": right["id"], "confidence": confidence,
            "threshold": threshold, "signals": signals, "contradictions": contradictions,
            "route": "main_agent", "question": "Are these two Inventory entries one continued logical table?",
            "evidence_pages": [left_page, right_page],
            "boundary_rows": {
                "left_last": (actual[left["id"]].get("rows") or [None])[-1],
                "right_first": (actual[right["id"]].get("rows") or [None])[0],
            },
        }
        decision = decisions.get((left["id"], right["id"]))
        if decision:
            candidate.update({"resolved": True, "decision": "keep_separate", "reason": decision["reason"]})
        candidates.append(candidate)
    return candidates


def _continuity_signals(left: dict, right: dict, actual: dict, finding: dict) -> tuple[list[dict], list[dict]]:
    left_title, right_title = left.get("title", ""), right.get("title", "")
    left_number, right_number = _table_number(left_title), _table_number(right_title)
    signals = [{"code": "adjacent_pages", "weight": 0.1}]
    contradictions = []
    if finding.get("label") == "continuation":
        signals.append({"code": "finder_marked_continuation", "weight": 0.55})
    if _normalized_title(left_title) == _normalized_title(right_title):
        signals.append({"code": "same_normalized_title", "weight": 0.25})
    elif left_title and right_title:
        contradictions.append({"code": "different_titles", "weight": -0.2})
    if actual[left["id"]].get("columns") == actual[right["id"]].get("columns"):
        signals.append({"code": "same_headers", "weight": 0.15})
    if _looks_like_split_row(actual[left["id"]], actual[right["id"]]):
        signals.append({"code": "boundary_row_may_continue", "weight": 0.2})
    if left_number and right_number and left_number != right_number:
        contradictions.append({"code": "distinct_table_numbers", "weight": -0.65})
    return signals, contradictions


def _confidence(signals: list[dict], contradictions: list[dict]) -> float:
    value = sum(item["weight"] for item in signals + contradictions)
    return round(max(0.0, min(1.0, value)), 3)


def _table_number(value: str) -> str | None:
    match = re.search(r"\b(?:table|tabelle|tab\.)\s*([0-9]+[a-z]?)\b", value, re.IGNORECASE)
    return match.group(1).lower() if match else None


def _normalized_title(value: str) -> str:
    value = re.sub(r"\b(?:continued|continuation|fortsetzung|fortgefuehrt|fortgeführt)\b", "", value, flags=re.I)
    return re.sub(r"[^a-z0-9äöüß]+", " ", value.lower()).strip()


def _looks_like_split_row(left: dict, right: dict) -> bool:
    left_rows, right_rows = left.get("rows", []), right.get("rows", [])
    if not left_rows or not right_rows:
        return False
    left_last, right_first = left_rows[-1], right_rows[0]
    left_blank = sum(not str(value).strip() for value in left_last)
    right_blank = sum(not str(value).strip() for value in right_first)
    return left_blank > 0 and right_blank > 0 and left_blank + right_blank >= len(left_last)
