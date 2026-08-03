from __future__ import annotations

import json
import shutil
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageChops, ImageDraw, ImageOps

from pdf_table_codegen.job import Job
from pdf_table_codegen.models import source_sha256

EVIDENCE_VERSION = "1.1"


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if hasattr(value, "x") and hasattr(value, "y"):
        return [float(value.x), float(value.y)]
    if hasattr(value, "x0"):
        return [float(value.x0), float(value.y0), float(value.x1), float(value.y1)]
    return str(value)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(value), ensure_ascii=False, indent=2) + "\n", "utf-8"
    )


def _render(page: fitz.Page, dpi: int) -> Image.Image:
    scale = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")


def _contact(images: list[tuple[int, Path]], target: Path, columns: int = 4) -> None:
    thumb = (360, 280)
    cell = (380, 320)
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * cell[0], rows * cell[1]), "white")
    draw = ImageDraw.Draw(canvas)
    has_page_content = False
    for position, (page_number, path) in enumerate(images):
        with Image.open(path) as source:
            image = ImageOps.contain(source.convert("RGB"), thumb)
        white = Image.new("RGB", image.size, "white")
        has_page_content = has_page_content or ImageChops.difference(image, white).getbbox() is not None
        x = (position % columns) * cell[0] + (cell[0] - image.width) // 2
        y = (position // columns) * cell[1] + 24
        if x < 0 or y < 0 or x + image.width > canvas.width or y + image.height > canvas.height:
            raise ValueError(f"contact thumbnail outside canvas: page {page_number}")
        canvas.paste(image, (x, y))
        draw.text((x, 5 + (position // columns) * cell[1]), f"page {page_number}", fill="black")
    if not has_page_content:
        raise ValueError("contact group contains no visible page content")
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, quality=88)


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _cache_key(source_hash: str, page_dpi: int, contact_size: int) -> str:
    value = json.dumps(
        {
            "version": EVIDENCE_VERSION,
            "source_sha256": source_hash,
            "page_dpi": page_dpi,
            "contact_pages": contact_size,
        },
        sort_keys=True,
    ).encode()
    return sha256(value).hexdigest()


def _cached(job: Job, key: str) -> dict[str, Any] | None:
    manifest_path = job.evidence_dir / "manifest.json"
    hashes_path = job.evidence_dir / "hashes.json"
    if not manifest_path.is_file() or not hashes_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("cache_key") != key or not isinstance(hashes, dict):
        return None
    for relative, expected in hashes.items():
        path = job.evidence_dir / relative
        if not path.is_file() or _file_hash(path) != expected:
            return None
    return {**manifest, "cache_hit": True}


def prepare_evidence(job: Job) -> dict[str, Any]:
    page_dpi = int(job.evidence.get("page_dpi", 144))
    contact_size = int(job.evidence.get("contact_pages", 12))
    source_hash = source_sha256(job.source)
    key = _cache_key(source_hash, page_dpi, contact_size)
    cached = _cached(job, key)
    if cached is not None:
        return cached
    pages_dir = job.evidence_dir / "pages"
    geometry_dir = job.evidence_dir / "geometry"
    contacts_dir = job.evidence_dir / "contacts"
    for directory in (pages_dir, geometry_dir, contacts_dir):
        if directory.exists():
            shutil.rmtree(directory)
    pages_dir.mkdir(parents=True, exist_ok=True)
    geometry_dir.mkdir(parents=True, exist_ok=True)
    page_files: list[tuple[int, Path]] = []
    page_meta = []
    with fitz.open(job.source) as document:
        for page_index, page in enumerate(document, start=1):
            image_path = pages_dir / f"page-{page_index:04d}.png"
            _render(page, page_dpi).save(image_path)
            page_files.append((page_index, image_path))
            words = page.get_text("words", sort=False)
            drawings = page.get_drawings()
            metadata = {
                "page": page_index,
                "rotation": page.rotation,
                "rect": _jsonable(page.rect),
                "mediabox": _jsonable(page.mediabox),
                "cropbox": _jsonable(page.cropbox),
                "word_count": len(words),
                "drawing_count": len(drawings),
            }
            page_meta.append(metadata)
            _write_json(geometry_dir / f"page-{page_index:04d}-words.json", words)
            _write_json(geometry_dir / f"page-{page_index:04d}-drawings.json", drawings)
    contacts = []
    for offset in range(0, len(page_files), contact_size):
        group = page_files[offset : offset + contact_size]
        target = contacts_dir / f"contact-{offset // contact_size + 1:03d}.jpg"
        _contact(group, target)
        contacts.append(target)
    manifest = {
        "spec": "pdf-table-codegen/evidence@1.1",
        "source": job.source.name,
        "source_sha256": source_hash,
        "cache_key": key,
        "page_count": len(page_meta),
        "page_dpi": page_dpi,
        "table_detector_run": False,
        "pages": page_meta,
        "contacts": [path.relative_to(job.evidence_dir).as_posix() for path in contacts],
    }
    _write_json(job.evidence_dir / "manifest.json", manifest)
    files = [job.evidence_dir / "manifest.json"]
    for directory in (pages_dir, geometry_dir, contacts_dir):
        files.extend(sorted(path for path in directory.rglob("*") if path.is_file()))
    hashes = {path.relative_to(job.evidence_dir).as_posix(): _file_hash(path) for path in files}
    _write_json(job.evidence_dir / "hashes.json", hashes)
    return {**manifest, "cache_hit": False}
