from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
class RowProvenance:
    page: int
    bbox: tuple[float, float, float, float]
    segment_id: str


@dataclass(frozen=True)
class ExtractedTable:
    id: str
    title: str
    column_count: int
    rows: list[list[str]]
    provenance: list[RowProvenance]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExtractionResult:
    source_sha256: str
    tables: list[ExtractedTable]
    extractor_version: str = "1.0.0"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": "pdf-extractor-pdf/result@2.0",
            "source_sha256": self.source_sha256,
            "extractor_version": self.extractor_version,
            "tables": [table.to_dict() for table in self.tables],
            "warnings": self.warnings,
        }
