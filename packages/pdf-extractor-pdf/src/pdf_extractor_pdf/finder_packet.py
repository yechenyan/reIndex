from __future__ import annotations

import re
from pathlib import Path

import fitz

from pdf_extractor_pdf.artifacts import artifact_hash, write_json
from pdf_extractor_pdf.job import Job

TABLE_TERM = re.compile(r"\b(?:table|tableau|tabelle|tabella|tabla)\b", re.IGNORECASE)


def build_finder_packet(job: Job, document: fitz.Document, contacts: list[dict]) -> dict:
    dpi = int(job.evidence.get("finder_candidate_dpi", 150))
    target = job.evidence_dir / "pages-candidate"
    target.mkdir(parents=True, exist_ok=True)
    pages, candidate_pages, images = [], [], []
    for number, page in enumerate(document, 1):
        text = page.get_text("text")
        lines = _grid_lines(page)
        title_hits = TABLE_TERM.findall(text)
        reasons = []
        if title_hits:
            reasons.append("table_term")
        if lines >= 20:
            reasons.append("grid_geometry")
        candidate = bool(reasons)
        image = None
        if candidate:
            candidate_pages.append(number)
            path = target / f"page-{number:04d}-{dpi}dpi.png"
            if not path.is_file():
                page.get_pixmap(dpi=dpi, alpha=False).save(path)
            image = str(path)
            images.append({"path": image, "sha256": artifact_hash(path)})
        pages.append({
            "page": number, "candidate": candidate, "reasons": reasons,
            "table_term_hits": len(title_hits), "grid_line_count": lines,
            "width": round(page.rect.width, 3), "height": round(page.rect.height, 3),
            "rotation": page.rotation, "word_count": len(page.get_text("words")),
            "candidate_image": image,
        })
    value = {
        "spec": "pdf-extractor-pdf/finder-packet@1.0",
        "instructions": (
            "Review every contact-window page; freeze positional column_count without assuming a header, "
            "use candidate images first, and escalate only uncertain pages."
        ),
        "contact_windows": contacts, "candidate_pages": candidate_pages,
        "candidate_images": images, "pages": pages,
    }
    path = write_json(job.evidence_dir / "finder-packet.json", value)
    return {"path": str(path), "sha256": artifact_hash(path), **value}


def valid_finder_packet(value: dict) -> bool:
    path = Path(value.get("path", ""))
    if not path.is_file() or artifact_hash(path) != value.get("sha256"):
        return False
    return all(
        Path(item["path"]).is_file() and artifact_hash(Path(item["path"])) == item["sha256"]
        for item in value.get("candidate_images", [])
    )


def _grid_lines(page: fitz.Page) -> int:
    count = 0
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "l":
                start, end = item[1], item[2]
                if abs(start.x - end.x) < 1 or abs(start.y - end.y) < 1:
                    count += 1
            elif item[0] == "re":
                count += 4
    return count
