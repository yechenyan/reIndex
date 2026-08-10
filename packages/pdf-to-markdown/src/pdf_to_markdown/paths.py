from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    project: Path

    @property
    def artifacts(self) -> Path:
        return self.project / "artifacts"

    @property
    def screenshots(self) -> Path:
        return self.artifacts / "screenshots"

    @property
    def agents(self) -> Path:
        return self.artifacts / "agents"

    @property
    def specialist(self) -> Path:
        return self.project / "specialist"

    @property
    def manifest(self) -> Path:
        return self.project / "job.json"

    @property
    def liteparse(self) -> Path:
        return self.artifacts / "liteparse.json"

    @property
    def candidates(self) -> Path:
        return self.artifacts / "candidates.json"

    @property
    def samples(self) -> Path:
        return self.artifacts / "samples.json"

    @property
    def report(self) -> Path:
        return self.project / "report.json"
