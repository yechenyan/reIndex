from __future__ import annotations

import re


WORD = re.compile(r"\w+", re.UNICODE)


def apply_replacements(document: str, replacements: list[dict]) -> str:
    operations: list[tuple[int, int, str, str]] = []
    for replacement_plan in replacements:
        replacement_id = replacement_plan["replacementId"]
        spans = [tuple(span) for span in replacement_plan.get("spans", [])]
        if not spans:
            derived = anchor_span(document, replacement_plan)
            if derived:
                spans = [derived]
        if not spans:
            raise ValueError(f"No safe replacement span for {replacement_id}")
        spans.sort()
        for index, (start, end) in enumerate(spans):
            markdown = marked_payload(replacement_plan) if index == 0 else ""
            operations.append((start, end, markdown, replacement_id))
    validate_operations(operations, len(document))
    result = document
    for start, end, replacement, _ in sorted(operations, reverse=True):
        result = result[:start] + replacement + result[end:]
    return verify_and_remove_markers(result, replacements)


def marked_payload(replacement: dict) -> str:
    replacement_id = replacement["replacementId"]
    start = f"<!-- pdf-to-markdown:{replacement_id}:start -->"
    end = f"<!-- pdf-to-markdown:{replacement_id}:end -->"
    return f"{start}\n{replacement['replacementMarkdown']}\n{end}\n"


def verify_and_remove_markers(document: str, replacements: list[dict]) -> str:
    result = document
    for replacement in replacements:
        replacement_id = replacement["replacementId"]
        start = f"<!-- pdf-to-markdown:{replacement_id}:start -->"
        end = f"<!-- pdf-to-markdown:{replacement_id}:end -->"
        if result.count(start) != 1 or result.count(end) != 1:
            raise ValueError(f"Specialist replacement was not inserted exactly once: {replacement_id}")
        if result.index(start) >= result.index(end):
            raise ValueError(f"Specialist replacement markers are out of order: {replacement_id}")
        result = result.replace(start + "\n", "", 1).replace("\n" + end, "", 1)
    return result


def validate_operations(operations: list[tuple[int, int, str, str]], length: int) -> None:
    ordered = sorted(operations)
    previous_end = 0
    for start, end, _, table_id in ordered:
        if not 0 <= start < end <= length:
            raise ValueError(f"Invalid replacement span for {table_id}: {start}..{end}")
        if start < previous_end:
            raise ValueError(f"Overlapping replacement span at {table_id}")
        previous_end = end


def anchor_span(document: str, replacement_plan: dict) -> tuple[int, int] | None:
    specialist = replacement_plan.get("specialist", {})
    before, after = specialist.get("textBefore", ""), specialist.get("textAfter", "")
    bounds = replacement_plan.get("pageBounds", [])
    if not bounds or not (before or after):
        return None
    search_start, search_end = bounds[0][0], bounds[-1][1]
    segment = document[search_start:search_end]
    tokens = [(match.group(0).casefold(), match.start(), match.end()) for match in WORD.finditer(segment)]
    start = boundary_from_before(tokens, before)
    end = boundary_from_after(tokens, after)
    if start is None:
        start = 0
    if end is None:
        end = len(segment)
    return (search_start + start, search_start + end) if start < end else None


def boundary_from_before(tokens: list[tuple[str, int, int]], value: str) -> int | None:
    needle = words(value)[-8:]
    matches = token_matches(tokens, needle)
    return matches[-1][1] if len(matches) == 1 else None


def boundary_from_after(tokens: list[tuple[str, int, int]], value: str) -> int | None:
    needle = words(value)[:8]
    matches = token_matches(tokens, needle)
    return matches[0][0] if len(matches) == 1 else None


def token_matches(tokens: list[tuple[str, int, int]], needle: list[str]) -> list[tuple[int, int]]:
    if not needle:
        return []
    values = [token[0] for token in tokens]
    result = []
    for index in range(len(values) - len(needle) + 1):
        if values[index : index + len(needle)] == needle:
            result.append((tokens[index][1], tokens[index + len(needle) - 1][2]))
    return result


def words(value: str) -> list[str]:
    return [match.group(0).casefold() for match in WORD.finditer(str(value))]
