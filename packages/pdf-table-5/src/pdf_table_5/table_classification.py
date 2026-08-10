from __future__ import annotations


IMAGE_COVERAGE_THRESHOLD = 0.5


def image_table_classification(items: list[tuple[dict, list, list]]) -> dict:
    details = [segment_image_evidence(segment, words, images) for segment, words, images in items]
    image_table = bool(details) and all(item["imageDominant"] for item in details)
    return {
        "imageTable": image_table,
        "imageCoverage": [item["coverage"] for item in details],
        "nativeWordsInImageRegions": sum(item["nativeWordsInImages"] for item in details),
    }


def segment_image_evidence(segment: dict, words: list, images: list) -> dict:
    target = segment.get("sourceBbox") or segment.get("bbox")
    if not valid_rect(target):
        return {"coverage": 0.0, "nativeWordsInImages": 0, "imageDominant": False}
    target_area = area(target)
    coverage = min(1.0, sum(intersection_area(target, image) for image in images) / target_area)
    native_words = sum(
        1 for word in words
        if any(center_in(word_rect(word), image) and center_in(word_rect(word), target) for image in images)
    )
    return {
        "coverage": round(coverage, 4),
        "nativeWordsInImages": native_words,
        "imageDominant": coverage >= IMAGE_COVERAGE_THRESHOLD and native_words == 0,
    }


def word_rect(word) -> list[float]:
    return word.get("bbox", []) if isinstance(word, dict) else list(word[:4])


def center_in(rect, target) -> bool:
    if not valid_rect(rect) or not valid_rect(target):
        return False
    x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    return target[0] <= x <= target[2] and target[1] <= y <= target[3]


def intersection_area(first, second) -> float:
    if not valid_rect(first) or not valid_rect(second):
        return 0.0
    width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    return width * height


def area(rect) -> float:
    return (rect[2] - rect[0]) * (rect[3] - rect[1])


def valid_rect(rect) -> bool:
    return isinstance(rect, (list, tuple)) and len(rect) == 4 and rect[2] > rect[0] and rect[3] > rect[1]
