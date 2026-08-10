from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .io import read_json
from .page_selection import PageSelection

DEFAULT_AGENT_MODEL = "gpt-5.6-terra"
DEFAULT_REASONING_EFFORT = "medium"


@dataclass(frozen=True)
class Paths:
    project: Path

    @property
    def parse(self) -> Path:
        return self.project / "parse"

    @property
    def helper(self) -> Path:
        return self.parse / "helper"

    @property
    def tables(self) -> Path:
        return self.parse / "tables"

    @property
    def strategy(self) -> Path:
        return self.parse / "strategy"

    @property
    def report(self) -> Path:
        return self.parse / "report"

    @property
    def output(self) -> Path:
        return self.project / "output"

    @property
    def job(self) -> Path:
        return self.helper / "job.json"

    @property
    def params(self) -> Path:
        return self.helper / "param.json"

    @property
    def states(self) -> Path:
        return self.helper / "states.json"

    @property
    def steps(self) -> Path:
        return self.helper / "steps.jsonl"

    def helper_json(self, name: str) -> Path:
        return self.helper / name

    def table_dir(self, parse_table_id: str) -> Path:
        return self.tables / parse_table_id


@dataclass
class Context:
    paths: Paths
    codex_model: str = DEFAULT_AGENT_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    max_repairs: int = 3

    @property
    def job(self) -> dict:
        return read_json(self.paths.job, {})

    @property
    def params(self) -> dict:
        return read_json(self.paths.params, {})

    @property
    def pdf(self) -> Path:
        value = self.job.get("demand", {}).get("inputPath")
        if not value:
            raise ValueError("job.json is missing demand.inputPath")
        path = Path(value)
        return path if path.is_absolute() else self.paths.project / path

    @property
    def target_pages(self) -> PageSelection:
        return self.job.get("demand", {}).get("targetPages")
