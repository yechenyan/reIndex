from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def parse(self) -> Path:
        return self.root / "parse"

    @property
    def helper(self) -> Path:
        return self.parse / "helper"

    @property
    def blocks(self) -> Path:
        return self.parse / "blocks"

    @property
    def report(self) -> Path:
        return self.parse / "report"

    @property
    def scratch(self) -> Path:
        return self.parse / "scratch"

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def assets(self) -> Path:
        return self.output / "assets"

    @property
    def job(self) -> Path:
        return self.helper / "job.json"

    @property
    def params(self) -> Path:
        return self.helper / "params.json"

    @property
    def states(self) -> Path:
        return self.helper / "states.json"

    @property
    def steps(self) -> Path:
        return self.helper / "steps.jsonl"

    def create_directories(self) -> None:
        for path in (
            self.helper,
            self.blocks,
            self.report,
            self.scratch,
            self.assets,
            self.helper / "native-geometry",
            self.helper / "screenshots",
        ):
            path.mkdir(parents=True, exist_ok=True)
