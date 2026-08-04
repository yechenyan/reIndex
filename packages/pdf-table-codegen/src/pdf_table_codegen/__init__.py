"""Single-file implementation of the pdf-table-codegen package."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Data models and hashing
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any


def source_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ExtractionRequest:
    source: Path
    strict: bool = True
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompatibilityReport:
    supported: bool
    reason: str
    source_sha256: str | None = None


@dataclass(frozen=True)
class RowProvenance:
    page: int
    bbox: tuple[float, float, float, float] | None = None
    segment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "bbox": list(self.bbox) if self.bbox else None,
            "segment": self.segment,
        }


@dataclass(frozen=True)
class ExtractedTable:
    id: str
    title: str
    headers: list[str]
    rows: list[list[str]]
    pages: list[int]
    provenance: list[RowProvenance] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "headers": self.headers,
            "rows": self.rows,
            "pages": self.pages,
            "provenance": [item.to_dict() for item in self.provenance],
        }


@dataclass(frozen=True)
class QaFinding:
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass(frozen=True)
class QaReport:
    findings: list[QaFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "findings": [item.to_dict() for item in self.findings]}


@dataclass(frozen=True)
class ExtractionResult:
    extractor_id: str
    extractor_version: str
    source_sha256: str
    tables: list[ExtractedTable]
    qa: QaReport = field(default_factory=QaReport)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": "pdf-table-codegen/result@1.0",
            "extractor_id": self.extractor_id,
            "extractor_version": self.extractor_version,
            "source_sha256": self.source_sha256,
            "tables": [table.to_dict() for table in self.tables],
            "qa": self.qa.to_dict(),
        }
# ---------------------------------------------------------------------------
# Job loading
# ---------------------------------------------------------------------------

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Job:
    path: Path
    name: str
    source: Path
    extractor: Path
    evidence_dir: Path
    output_dir: Path
    inventory: Path
    reference: Path
    evidence: dict[str, Any]
    policy: dict[str, Any]


def load_job(path: Path) -> Job:
    path = path.resolve()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("spec") != "pdf-table-codegen/job@1.0":
        raise ValueError("job spec must be pdf-table-codegen/job@1.0")
    root = path.parent

    def resolved(key: str, default: str | None = None) -> Path:
        value = raw.get(key, default)
        if not isinstance(value, str) or not value:
            raise ValueError(f"job field {key!r} must be a path string")
        return (root / value).resolve()

    source = resolved("source")
    if not source.is_file():
        raise FileNotFoundError(source)
    evidence_dir = resolved("evidence_dir", "evidence")
    return Job(
        path=path,
        name=str(raw.get("name") or source.stem),
        source=source,
        extractor=resolved("extractor", "extractor.py"),
        evidence_dir=evidence_dir,
        output_dir=resolved("output_dir", "output"),
        inventory=resolved("inventory", "evidence/inventory.frozen.json"),
        reference=resolved("reference", "evidence/visual-reference.json"),
        evidence=dict(raw.get("evidence") or {}),
        policy=dict(raw.get("policy") or {}),
    )
# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

import csv
import json
from pathlib import Path



def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def write_result(result: ExtractionResult, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for table in result.tables:
        path = output_dir / f"{table.id}.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(table.headers)
            writer.writerows(table.rows)
        written.append(path)
    result_path = output_dir / "result.json"
    _json(result_path, result.to_dict())
    written.append(result_path)
    return written


def write_verification(report: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "verification.json"
    _json(path, report)
    return path
# ---------------------------------------------------------------------------
# Reference verification
# ---------------------------------------------------------------------------

import json
import re
import unicodedata
from pathlib import Path
from typing import Any



def sample_indices(row_count: int) -> list[int]:
    if row_count < 0:
        raise ValueError("row_count cannot be negative")
    if row_count <= 3:
        return list(range(row_count))
    return [0, 1, row_count - 2, row_count - 1]


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def load_reference(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("spec") != "pdf-table-codegen/reference@1.0":
        raise ValueError("unsupported visual reference spec")
    return value


def verify_reference(result: ExtractionResult, reference: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, expected: Any, actual: Any) -> None:
        checks.append({"name": name, "ok": ok, "expected": expected, "actual": actual})

    check(
        "source_sha256",
        result.source_sha256 == reference.get("source_sha256"),
        reference.get("source_sha256"),
        result.source_sha256,
    )
    actual_tables = {table.id: table for table in result.tables}
    expected_tables = reference.get("tables") or []
    check("table_count", len(actual_tables) == len(expected_tables), len(expected_tables), len(actual_tables))
    for expected in expected_tables:
        table_id = expected["id"]
        table = actual_tables.get(table_id)
        check(f"{table_id}.present", table is not None, True, table is not None)
        if table is None:
            continue
        check(f"{table_id}.columns", len(table.headers) == expected["column_count"], expected["column_count"], len(table.headers))
        check(f"{table_id}.rows", len(table.rows) == expected["row_count"], expected["row_count"], len(table.rows))
        expected_header = [_normalized(value) for value in expected["header"]]
        actual_header = [_normalized(value) for value in table.headers]
        check(f"{table_id}.header", actual_header == expected_header, expected_header, actual_header)
        for sample in expected.get("samples", []):
            index = int(sample["row_index"])
            actual = table.rows[index] if 0 <= index < len(table.rows) else None
            expected_row = [_normalized(value) for value in sample["values"]]
            actual_row = None if actual is None else [_normalized(value) for value in actual]
            check(f"{table_id}.row[{index}]", actual_row == expected_row, expected_row, actual_row)
    return {
        "spec": "pdf-table-codegen/verification@1.0",
        "ok": all(item["ok"] for item in checks) and result.qa.ok,
        "extractor_qa": result.qa.to_dict(),
        "checks": checks,
    }
# ---------------------------------------------------------------------------
# PDF evidence preparation
# ---------------------------------------------------------------------------

import json
import shutil
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageChops, ImageDraw, ImageOps


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
# ---------------------------------------------------------------------------
# Inventory and reference freezing
# ---------------------------------------------------------------------------

import json
import re
from pathlib import Path
from typing import Any


_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write_atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")
    temporary.replace(path)


def _ids(value: dict[str, Any]) -> list[str]:
    tables = value.get("tables")
    if not isinstance(tables, list):
        raise ValueError("tables must be a list")
    ids = [str(table.get("id", "")) for table in tables]
    if any(not _ID.fullmatch(table_id) for table_id in ids):
        raise ValueError("table IDs must use lowercase letters, digits, dot, dash, or underscore")
    if len(ids) != len(set(ids)):
        raise ValueError("table IDs must be unique")
    return ids


def _validate_inventory(value: dict[str, Any], page_count: int) -> None:
    _ids(value)
    for table in value["tables"]:
        pages = table.get("pages")
        if not isinstance(pages, list) or not pages:
            raise ValueError(f"table {table['id']!r} must list pages")
        if any(not isinstance(page, int) or not 1 <= page <= page_count for page in pages):
            raise ValueError(f"table {table['id']!r} has an invalid page")
        for segment in table.get("segments", []):
            bbox = segment.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise ValueError(f"table {table['id']!r} segment bbox must have four numbers")
            if not all(isinstance(item, (int, float)) for item in bbox):
                raise ValueError(f"table {table['id']!r} segment bbox must be numeric")
            if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                raise ValueError(f"table {table['id']!r} segment bbox is empty")


def freeze_inventory(job: Job, draft: Path) -> dict[str, Any]:
    manifest_path = job.evidence_dir / "manifest.json"
    manifest = _read(manifest_path)
    current_source = source_sha256(job.source)
    if manifest.get("source_sha256") != current_source:
        raise ValueError("evidence manifest does not match the current source")
    body = _read(draft)
    _validate_inventory(body, int(manifest["page_count"]))
    frozen = {
        "spec": "pdf-table-codegen/inventory@1.0",
        "status": "frozen",
        "scope": body.get("scope", "full_document"),
        "source_sha256": current_source,
        "evidence_manifest_sha256": source_sha256(manifest_path),
        **{key: value for key, value in body.items() if key not in {"spec", "status", "scope", "source_sha256", "evidence_manifest_sha256"}},
    }
    _write_atomic_json(job.inventory, frozen)
    return frozen


def _required_samples(table: dict[str, Any], inventory_table: dict[str, Any]) -> set[int]:
    required = set(sample_indices(int(table["row_count"])))
    segments = inventory_table.get("segments", [])
    for before, after in zip(segments, segments[1:]):
        left = before.get("data_rows")
        right = after.get("data_rows")
        if isinstance(left, list) and len(left) == 2:
            required.add(int(left[1]) - 1)
        if isinstance(right, list) and len(right) == 2:
            required.add(int(right[0]) - 1)
    return required


def freeze_reference(job: Job, draft: Path) -> dict[str, Any]:
    inventory = _read(job.inventory)
    current_source = source_sha256(job.source)
    if inventory.get("source_sha256") != current_source:
        raise ValueError("frozen inventory does not match the current source")
    body = _read(draft)
    if _ids(body) != _ids(inventory):
        raise ValueError("reference table IDs and order must match the inventory")
    inventory_tables = {table["id"]: table for table in inventory["tables"]}
    for table in body["tables"]:
        columns = int(table["column_count"])
        rows = int(table["row_count"])
        if len(table.get("header", [])) != columns:
            raise ValueError(f"reference {table['id']!r} header width mismatch")
        samples = {int(sample["row_index"]): sample for sample in table.get("samples", [])}
        if not _required_samples(table, inventory_tables[table["id"]]).issubset(samples):
            raise ValueError(f"reference {table['id']!r} is missing required source samples")
        if any(index < 0 or index >= rows for index in samples):
            raise ValueError(f"reference {table['id']!r} has an invalid sample index")
        if any(len(sample.get("values", [])) != columns for sample in samples.values()):
            raise ValueError(f"reference {table['id']!r} sample width mismatch")
    frozen = {
        "spec": "pdf-table-codegen/reference@1.0",
        "status": "frozen_before_extractor_output",
        "scope": inventory.get("scope", "full_document"),
        "source_sha256": current_source,
        "inventory_sha256": source_sha256(job.inventory),
        **{key: value for key, value in body.items() if key not in {"spec", "status", "scope", "source_sha256", "inventory_sha256"}},
    }
    _write_atomic_json(job.reference, frozen)
    return frozen
# ---------------------------------------------------------------------------
# Frozen inventory inspection
# ---------------------------------------------------------------------------

import json
import shutil
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
from PIL import Image



def _write_inspection_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def _point(value: Any) -> tuple[float, float]:
    return float(value.x), float(value.y)


def _line(x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    delta_x, delta_y = abs(x1 - x0), abs(y1 - y0)
    orientation = "horizontal" if delta_y < 0.5 else "vertical" if delta_x < 0.5 else "other"
    return {
        "orientation": orientation,
        "points": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
        "length": round((delta_x * delta_x + delta_y * delta_y) ** 0.5, 2),
    }


def _drawing_lines(page: fitz.Page, clip: fitz.Rect) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "l":
                x0, y0 = _point(item[1])
                x1, y1 = _point(item[2])
                candidates = [_line(x0, y0, x1, y1)]
            elif item[0] == "re":
                rect = item[1]
                candidates = [
                    _line(rect.x0, rect.y0, rect.x1, rect.y0),
                    _line(rect.x1, rect.y0, rect.x1, rect.y1),
                    _line(rect.x1, rect.y1, rect.x0, rect.y1),
                    _line(rect.x0, rect.y1, rect.x0, rect.y0),
                ]
            else:
                continue
            for candidate in candidates:
                x0, y0, x1, y1 = candidate["points"]
                if fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1) + 0.1, max(y0, y1) + 0.1).intersects(clip):
                    lines.append(candidate)
    return lines


def _clusters(values: list[float], limit: int = 40) -> list[dict[str, Any]]:
    counts = Counter(round(value, 1) for value in values)
    return [{"position": key, "count": count} for key, count in counts.most_common(limit)]


def _segment_report(page: fitz.Page, bbox: list[float]) -> dict[str, Any]:
    clip = fitz.Rect(bbox)
    words = [word for word in page.get_text("words", sort=True) if clip.contains(fitz.Point((word[0] + word[2]) / 2, (word[1] + word[3]) / 2))]
    lines = _drawing_lines(page, clip)
    return {
        "bbox": [round(value, 2) for value in bbox],
        "word_count": len(words),
        "words": [[round(value, 2) if isinstance(value, float) else value for value in word] for word in words],
        "coordinate_clusters": {
            "word_x0": _clusters([word[0] for word in words]),
            "word_x1": _clusters([word[2] for word in words]),
            "word_y0": _clusters([word[1] for word in words]),
            "word_y1": _clusters([word[3] for word in words]),
        },
        "drawing_lines": lines,
        "horizontal_line_positions": _clusters([line["points"][1] for line in lines if line["orientation"] == "horizontal"]),
        "vertical_line_positions": _clusters([line["points"][0] for line in lines if line["orientation"] == "vertical"]),
        "notice": "Neutral source geometry only; choose the extraction strategy independently.",
    }


def inspect_inventory(job: Job) -> dict[str, Any]:
    inventory = json.loads(job.inventory.read_text(encoding="utf-8"))
    inventory_sha = source_sha256(job.inventory)
    if inventory.get("source_sha256") != source_sha256(job.source):
        raise ValueError("inventory does not match the current source")
    target_root = job.evidence_dir / "tables"
    if target_root.exists():
        shutil.rmtree(target_root)
    outputs: list[dict[str, Any]] = []
    dpi = int(job.evidence.get("table_dpi", max(180, int(job.evidence.get("page_dpi", 144)))))
    with fitz.open(job.source) as document:
        for table in inventory.get("tables", []):
            table_dir = target_root / table["id"]
            table_dir.mkdir(parents=True, exist_ok=True)
            segments = table.get("segments") or [{"page": page, "bbox": list(document[page - 1].rect)} for page in table["pages"]]
            for index, segment in enumerate(segments, start=1):
                page_number = int(segment["page"])
                bbox = [float(value) for value in segment["bbox"]]
                page = document[page_number - 1]
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), clip=fitz.Rect(bbox), alpha=False)
                image_name = f"segment-{index:02d}-page-{page_number:04d}.png"
                Image.open(BytesIO(pix.tobytes("png"))).convert("RGB").save(table_dir / image_name)
                report_name = f"segment-{index:02d}-page-{page_number:04d}.json"
                _write_inspection_json(table_dir / report_name, _segment_report(page, bbox))
                outputs.append({"table_id": table["id"], "page": page_number, "image": image_name, "geometry": report_name})
    manifest = {
        "spec": "pdf-table-codegen/table-evidence@1.0",
        "source_sha256": source_sha256(job.source),
        "inventory_sha256": inventory_sha,
        "dpi": dpi,
        "segments": outputs,
    }
    _write_inspection_json(target_root / "manifest.json", manifest)
    return manifest
# ---------------------------------------------------------------------------
# Assertion-hint scaffolding
# ---------------------------------------------------------------------------

import json
from pathlib import Path
from typing import Any



def build_assertion_hints(job: Job) -> dict[str, Any]:
    reference = json.loads(job.reference.read_text(encoding="utf-8"))
    inventory_hash = source_sha256(job.inventory)
    if reference.get("inventory_sha256") != inventory_hash:
        raise ValueError("reference does not match the current inventory")
    tables = []
    for table in reference.get("tables", []):
        tables.append({
            "id": table["id"],
            "required_shape": [int(table["row_count"]), int(table["column_count"])],
            "required_header": table["header"],
            "source_sample_anchors": [
                {"row_index": int(sample["row_index"]), "values": sample["values"]}
                for sample in table.get("samples", [])
            ],
            "agent_action": "Select stable, table-specific anchors and add drift checks; do not use these values to construct extracted rows.",
        })
    value = {
        "spec": "pdf-table-codegen/assertion-hints@1.0",
        "source_sha256": source_sha256(job.source),
        "inventory_sha256": inventory_hash,
        "table_order": [table["id"] for table in reference.get("tables", [])],
        "tables": tables,
    }
    target = job.evidence_dir / "assertion-hints.json"
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return value
# ---------------------------------------------------------------------------
# Bundled skill installation
# ---------------------------------------------------------------------------

import hashlib
import shutil
from importlib.resources import as_file, files
from pathlib import Path


def bundled_skill_path():
    return files("pdf_table_codegen").joinpath("bundled_skill", "pdf-table-codegen")


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def install_skill(workspace: Path, *, force: bool = False) -> tuple[Path, str]:
    target = workspace.resolve() / ".agents" / "skills" / "pdf-table-codegen"
    with as_file(bundled_skill_path()) as source:
        if target.exists():
            if _tree_digest(source) == _tree_digest(target):
                return target, "unchanged"
            if not force:
                raise FileExistsError(f"skill has local changes: {target}")
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    return target, "installed"
# ---------------------------------------------------------------------------
# Extractor loading and job execution
# ---------------------------------------------------------------------------

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType



def _module(path: Path) -> ModuleType:
    if not path.is_file():
        raise FileNotFoundError(f"extractor not found: {path}")
    spec = importlib.util.spec_from_file_location(f"pdf_table_extractor_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load extractor: {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _extract(job: Job) -> ExtractionResult:
    module = _module(job.extractor)
    request = ExtractionRequest(source=job.source, strict=True, parameters=job.policy)
    if hasattr(module, "can_handle"):
        compatibility = module.can_handle(job.source)
        if not compatibility.supported:
            raise ValueError(f"extractor rejected source: {compatibility.reason}")
    result = module.extract_tables(request)
    if not isinstance(result, ExtractionResult):
        raise TypeError("extract_tables() must return ExtractionResult")
    table_ids = [table.id for table in result.tables]
    if len(set(table_ids)) != len(table_ids):
        raise ValueError("table IDs must be unique")
    for table in result.tables:
        if not table.rows and not job.policy.get("allow_empty_tables", False):
            raise ValueError(f"table {table.id!r} has no data rows")
        if any(len(row) != len(table.headers) for row in table.rows):
            raise ValueError(f"table {table.id!r} has inconsistent row widths")
        if table.provenance and len(table.provenance) != len(table.rows):
            raise ValueError(f"table {table.id!r} provenance must align with rows")
    if not result.qa.ok:
        raise ValueError("extractor QA failed")
    return result


def run_job(path: Path) -> ExtractionResult:
    job = load_job(path)
    result = _extract(job)
    write_result(result, job.output_dir)
    return result


def _table_ids(document: dict) -> list[str]:
    return sorted(str(table["id"]) for table in document.get("tables", []))


def verify_job(path: Path) -> dict:
    job = load_job(path)
    if not job.reference.is_file():
        raise FileNotFoundError(f"visual reference not found: {job.reference}")
    result = _extract(job)
    write_result(result, job.output_dir)
    reference = load_reference(job.reference)
    report = verify_reference(result, reference)
    expected_inventory = reference.get("inventory_sha256")
    actual_inventory = source_sha256(job.inventory) if job.inventory.is_file() else None
    inventory_check = {
        "name": "inventory_sha256",
        "ok": bool(expected_inventory) and actual_inventory == expected_inventory,
        "expected": expected_inventory,
        "actual": actual_inventory,
    }
    inventory = json.loads(job.inventory.read_text(encoding="utf-8"))
    expected_table_ids = _table_ids(inventory)
    reference_table_ids = _table_ids(reference)
    result_table_ids = sorted(table.id for table in result.tables)
    table_ids_check = {
        "name": "full_table_inventory",
        "ok": expected_table_ids == reference_table_ids == result_table_ids,
        "expected": expected_table_ids,
        "actual": {
            "reference": reference_table_ids,
            "result": result_table_ids,
        },
    }
    report["checks"].insert(1, inventory_check)
    report["checks"].insert(2, table_ids_check)
    report["ok"] = report["ok"] and inventory_check["ok"] and table_ids_check["ok"]
    write_verification(report, job.output_dir)
    return report
# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

import argparse
import json
from pathlib import Path
from time import perf_counter



def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf-table-codegen")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "run", "verify"):
        command = sub.add_parser(name)
        command.add_argument("job", type=Path)
    for name in ("freeze-inventory", "freeze-reference"):
        command = sub.add_parser(name)
        command.add_argument("job", type=Path)
        command.add_argument("draft", type=Path)
    for name in ("inspect", "scaffold"):
        command = sub.add_parser(name)
        command.add_argument("job", type=Path)
    sub.add_parser("skill-path")
    install = sub.add_parser("install-skill")
    install.add_argument("workspace", type=Path, nargs="?", default=Path.cwd())
    install.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    started = perf_counter()
    if args.command == "skill-path":
        print(bundled_skill_path())
        return 0
    if args.command == "install-skill":
        path, status = install_skill(args.workspace, force=args.force)
        print(json.dumps({"ok": True, "path": str(path), "status": status}, indent=2))
        return 0
    if args.command == "prepare":
        manifest = prepare_evidence(load_job(args.job))
        value = {
            "ok": True,
            "source_sha256": manifest["source_sha256"],
            "page_count": manifest["page_count"],
            "contacts": manifest["contacts"],
            "table_detector_run": manifest["table_detector_run"],
            "cache_hit": manifest["cache_hit"],
        }
    elif args.command == "freeze-inventory":
        job = load_job(args.job)
        inventory = freeze_inventory(job, args.draft)
        value = {
            "ok": True,
            "path": str(job.inventory),
            "sha256": source_sha256(job.inventory),
            "tables": len(inventory["tables"]),
        }
    elif args.command == "freeze-reference":
        job = load_job(args.job)
        reference = freeze_reference(job, args.draft)
        value = {
            "ok": True,
            "path": str(job.reference),
            "sha256": source_sha256(job.reference),
            "tables": len(reference["tables"]),
        }
    elif args.command == "inspect":
        manifest = inspect_inventory(load_job(args.job))
        value = {
            "ok": True,
            "tables": len({item["table_id"] for item in manifest["segments"]}),
            "segments": len(manifest["segments"]),
        }
    elif args.command == "scaffold":
        hints = build_assertion_hints(load_job(args.job))
        value = {"ok": True, "tables": len(hints["tables"]), "path": "evidence/assertion-hints.json"}
    elif args.command == "run":
        result = run_job(args.job)
        value = {
            "ok": result.qa.ok,
            "extractor_id": result.extractor_id,
            "tables": [
                {"id": table.id, "rows": len(table.rows), "columns": len(table.headers)}
                for table in result.tables
            ],
        }
    else:
        report = verify_job(args.job)
        value = {
            "ok": report["ok"],
            "checks": len(report["checks"]),
            "failed": [item["name"] for item in report["checks"] if not item["ok"]],
        }
    value["elapsed_seconds"] = round(perf_counter() - started, 3)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0 if value.get("ok", True) else 1

__all__ = [
    "CompatibilityReport",
    "ExtractedTable",
    "ExtractionRequest",
    "ExtractionResult",
    "QaFinding",
    "QaReport",
    "RowProvenance",
    "source_sha256",
    "freeze_inventory",
    "freeze_reference",
    "inspect_inventory",
    "build_assertion_hints",
    "run_job",
    "verify_job",
]

# Preserve imports from the former multi-file package, such as importing
# ExtractionRequest from pdf_table_codegen.models.
_package_module = sys.modules[__name__]
for _submodule in (
    "cli",
    "evidence",
    "freezing",
    "inspection",
    "job",
    "models",
    "output",
    "reference",
    "runner",
    "scaffold",
    "skill",
):
    sys.modules[f"{__name__}.{_submodule}"] = _package_module
del _package_module, _submodule
