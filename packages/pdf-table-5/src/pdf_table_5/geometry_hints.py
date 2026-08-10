from __future__ import annotations


def line_evidence(words: list[dict]) -> list[list[object]]:
    """Losslessly pack repeated visual-line y coordinates for prompt transport."""
    lines: dict[tuple[float, float], list[list[object]]] = {}
    for word in words:
        box = word["bbox"]
        key = (round(float(box[1]), 2), round(float(box[3]), 2))
        lines.setdefault(key, []).append(
            [round(float(box[0]), 2), round(float(box[2]), 2), str(word["text"]),
             word.get("block", 0), word.get("line", 0), word.get("word", 0)]
        )
    return [
        [y0, y1, sorted(line_words, key=lambda item: (item[0], item[3], item[4], item[5]))]
        for (y0, y1), line_words in sorted(lines.items())
    ]


def left_edge_hints(segment: dict, words: list[dict]) -> dict:
    source = segment.get("sourceBbox") or segment.get("bbox") or [0, 0, 0, 0]
    x0, y0, x1, y1 = (float(value) for value in source)
    band_right = x0 + min(120.0, max(36.0, (x1 - x0) * 0.12))
    lines: dict[float, list[list[object]]] = {}
    for word in words:
        box = word.get("bbox", [])
        if len(box) != 4 or not (x0 <= float(box[0]) <= band_right and y0 <= float(box[1]) <= y1):
            continue
        key = round(float(box[1]), 2)
        lines.setdefault(key, []).append([round(float(box[0]), 2), str(word.get("text", ""))])
    compact_lines = []
    for y, line_words in sorted(lines.items()):
        ordered = sorted(line_words, key=lambda item: item[0])
        compact_lines.append({"y": y, "words": ordered[:8], "wordCount": len(ordered)})
    return {
        "page": segment.get("page"),
        "sourceBbox": list(source),
        "leftBand": [round(x0, 2), round(band_right, 2)],
        "lineCount": len(compact_lines),
        "lines": compact_lines,
    }
