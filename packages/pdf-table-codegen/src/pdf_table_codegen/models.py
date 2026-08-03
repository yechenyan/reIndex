from __future__ import annotations

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
