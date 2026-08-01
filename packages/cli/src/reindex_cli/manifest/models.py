from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ItemConfig:
    path: str
    parse: dict[str, str] = field(
        default_factory=lambda: {"text": "auto", "images": "auto", "tables": "auto"}
    )
    title: str | None = None
    description: str | None = None
    origin_url: str | None = None
    part_of: str | None = None
    derived_from: str | None = None
    pages: tuple[int, int] | None = None
    quality: dict[str, Any] | None = None
    ignore: bool = False


@dataclass(frozen=True)
class InputManifest:
    path: Path | None
    sha256: str | None
    title: str
    description: str
    items: dict[str, ItemConfig]
    body: str = ""
