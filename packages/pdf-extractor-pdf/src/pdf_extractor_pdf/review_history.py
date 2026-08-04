from __future__ import annotations

import re
from pathlib import Path

from pdf_extractor_pdf.artifacts import write_json
from pdf_extractor_pdf.job import Job


def write_versioned_review(job: Job, report: dict) -> dict:
    """Write an immutable numbered Review plus the stable latest pointer."""
    root = job.evidence_dir / "reviews"
    root.mkdir(parents=True, exist_ok=True)
    sequence = _next_sequence(root)
    archive = root / f"review-{sequence:03d}.json"
    value = {
        **report,
        "review_sequence": sequence,
        "review_archive": str(archive),
    }
    write_json(archive, value)
    write_json(job.evidence_dir / "review.json", value)
    return value


def _next_sequence(root: Path) -> int:
    values = []
    for path in root.glob("review-*.json"):
        match = re.fullmatch(r"review-(\d+)\.json", path.name)
        if match:
            values.append(int(match.group(1)))
    return max(values, default=0) + 1
