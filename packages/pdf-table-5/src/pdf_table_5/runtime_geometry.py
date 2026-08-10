from __future__ import annotations

import json
from pathlib import Path


WORD_FORMAT = ("x0", "y0", "x1", "y1", "text", "block", "line", "word")


def load_segments(table_json: str | Path) -> list[dict]:
    """Load runtime geometry in the same compact shape embedded in Parser prompts."""
    table_path = Path(table_json).resolve()
    table = _object(json.loads(table_path.read_text(encoding="utf-8")), "table.json")
    project_root = Path(table.get("projectRoot") or "")
    if not project_root.is_absolute():
        raise ValueError("table.json projectRoot must be an absolute path")
    segments = []
    for segment in table.get("tables", []):
        source = _object(segment, "table segment")
        geometry_path = _resolve(project_root, source.get("geometry"))
        geometry = _object(json.loads(geometry_path.read_text(encoding="utf-8")), str(geometry_path))
        raw_words = geometry.get("words", [])
        if not isinstance(raw_words, list):
            raise ValueError(f"geometry words must be an array: {geometry_path}")
        segments.append(
            {
                "page": source.get("page"),
                "bbox": source.get("bbox"),
                "sourceBbox": source.get("sourceBbox"),
                "words": [compact_word(word) for word in raw_words],
                "images": geometry.get("images", []),
                "geometryPath": str(geometry_path),
            }
        )
    return segments


def compact_word(word) -> list:
    if isinstance(word, dict):
        bbox = word.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("geometry word object requires bbox[4]")
        return [
            *[round(float(value), 2) for value in bbox],
            str(word.get("text", "")),
            int(word.get("block", 0)),
            int(word.get("line", 0)),
            int(word.get("word", 0)),
        ]
    if isinstance(word, list) and len(word) >= 5:
        suffix = [int(value) for value in (word[5:8] + [0, 0, 0])[:3]]
        return [*[round(float(value), 2) for value in word[:4]], str(word[4]), *suffix]
    raise ValueError("geometry word must be an object or compact array")


def join_word_text(words: list) -> str:
    """Join ordered compact words while handling common PDF line-wrap hyphens."""
    result = ""
    previous = None
    for word in words:
        part = str(word[4] if isinstance(word, list) and len(word) >= 5 else word).strip()
        if not part:
            continue
        if not result:
            result = part
        elif result.endswith("-") and len(result) > 1:
            preceding = result[-2]
            if preceding.islower() and part[0].islower() and new_visual_line(previous, word):
                result = result[:-1] + part
            elif hyphen_compound(previous, word):
                result += part
            else:
                result += " " + part
        else:
            result += " " + part
        previous = word
    return result


def new_visual_line(previous, current) -> bool:
    if not all(isinstance(word, list) and len(word) >= 4 for word in (previous, current)):
        return False
    return abs(float(current[1]) - float(previous[1])) > 0.25


def hyphen_compound(previous, current) -> bool:
    if not all(isinstance(word, list) and len(word) >= 5 for word in (previous, current)):
        return False
    stem = str(previous[4]).removesuffix("-")
    gap = float(current[0]) - float(previous[2])
    return stem in {"MS", "NS", "ONS"} or len(stem) <= 2 or (not new_visual_line(previous, current) and gap <= 0.15)


def _resolve(project_root: Path, reference) -> Path:
    if not isinstance(reference, str) or not reference:
        raise ValueError("table segment geometry path is missing")
    path = Path(reference)
    return path if path.is_absolute() else project_root / path


def _object(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value
