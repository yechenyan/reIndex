from __future__ import annotations

import time
from pathlib import Path

from .candidates import discover
from .io import sha256, write_json, write_text
from .liteparse_runner import parse_pdf
from .paths import Paths
from .placements import placement_records
from .reporting import failure_errors, failure_stage, status_counts, verified_statuses
from .replacement import apply_replacements
from .sample_agent import run_samples
from .sample_compare import compare
from .screenshots import render_candidates
from .specialist import run_specialist


RUNTIME_GUIDANCE = """# PDF to Markdown Runtime Workspace

This directory contains generated conversion artifacts. Follow the supplied agent prompt and attached
PDF table crops. Do not inspect or modify repository implementation, task notes, or unrelated files.
"""


class Workflow:
    def __init__(
        self,
        pdf: Path,
        output: Path,
        project: Path,
        *,
        model: str,
        reasoning_effort: str,
        workers: int | None = None,
    ):
        self.pdf = pdf.resolve()
        self.output = output.resolve()
        self.paths = Paths(project.resolve())
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.workers = workers
        self.timings: dict[str, int] = {}

    def run(self) -> dict:
        self.prepare()
        source_hash = sha256(self.pdf)
        write_json(
            self.paths.manifest,
            {
                "version": "pdf-to-markdown/job@1.0",
                "inputPath": str(self.pdf),
                "outputPath": str(self.output),
                "sha256": source_hash,
                "model": self.model,
                "reasoningEffort": self.reasoning_effort,
            },
        )
        liteparse = self.timed(
            "liteparse",
            lambda: parse_pdf(
                self.pdf,
                image_output_dir=self.output.parent / "assets",
                workers=self.workers,
            ),
        )
        write_json(self.paths.liteparse, liteparse)
        candidates = self.timed("candidateDiscovery", lambda: discover(liteparse))
        images = self.timed(
            "screenshots",
            lambda: render_candidates(self.pdf, candidates, self.paths.screenshots),
        )
        for candidate in candidates:
            candidate["screenshots"] = [str(path) for path in images.get(candidate["tableId"], [])]
        samples, sample_usage, sample_error = self.sample(candidates, images)
        write_json(self.paths.samples, {"samples": samples, "error": sample_error, "tokenUsage": sample_usage})
        self.apply_sample_results(candidates, samples, sample_error)
        specialist = self.timed(
            "specialist",
            lambda: run_specialist(
                self.pdf,
                self.paths.specialist,
                candidates,
                model=self.model,
                reasoning_effort=self.reasoning_effort,
            ),
        )
        write_json(self.paths.candidates, {"version": "pdf-to-markdown/candidates@1.0", "tables": candidates})
        failed = [candidate for candidate in candidates if candidate["status"] not in verified_statuses()]
        report = self.build_report(candidates, sample_usage, specialist, failed)
        write_json(self.paths.report, report)
        unmatched = specialist.get("unmatched", [])
        specialist_failed = specialist.get("failed", [])
        markdown = self.timed(
            "replacement",
            lambda: apply_replacements(liteparse["markdown"], specialist.get("replacements", [])),
        )
        write_text(self.output, markdown)
        report["outputPath"] = str(self.output)
        report["outputSha256"] = sha256(self.output)
        report["accepted"] = not (failed or unmatched or specialist_failed)
        report["specialistPlacements"] = placement_records(specialist.get("replacements", []))
        report["durationMs"] = sum(self.timings.values())
        report["timingsMs"] = self.timings
        write_json(self.paths.report, report)
        if not report["accepted"]:
            raise RuntimeError(f"Conversion completed with unverified tables; inspect {self.paths.report}")
        return report

    def prepare(self) -> None:
        if not self.pdf.is_file():
            raise FileNotFoundError(self.pdf)
        if self.pdf.suffix.lower() != ".pdf":
            raise ValueError(f"Input is not a PDF path: {self.pdf}")
        self.paths.project.mkdir(parents=True, exist_ok=True)
        guidance = self.paths.project / "AGENTS.md"
        if not guidance.exists():
            guidance.write_text(RUNTIME_GUIDANCE, encoding="utf-8")

    def sample(self, candidates, images):
        if not any(candidate["route"] == "sample" for candidate in candidates):
            return {}, {}, None
        try:
            started = time.monotonic()
            samples, usage = run_samples(
                self.paths.project,
                candidates,
                images,
                model=self.model,
                reasoning_effort=self.reasoning_effort,
            )
            self.timings["sampling"] = round((time.monotonic() - started) * 1000)
            return samples, usage, None
        except Exception as exc:
            return {}, {}, f"{type(exc).__name__}: {exc}"

    def apply_sample_results(self, candidates, samples, sample_error) -> None:
        for candidate in candidates:
            if candidate["route"] != "sample":
                continue
            if sample_error:
                candidate["route"] = "specialist"
                candidate["routeReasons"].append(f"sample agent failed: {sample_error}")
                continue
            result = compare(candidate["matrix"], samples[candidate["tableId"]])
            candidate["sampleComparison"] = result
            if result["passed"]:
                candidate["status"] = "liteparse_verified"
            else:
                candidate["route"] = "specialist"
                candidate["routeReasons"].extend(result["errors"])

    def timed(self, name: str, operation):
        started = time.monotonic()
        try:
            return operation()
        finally:
            self.timings[name] = round((time.monotonic() - started) * 1000)

    def build_report(self, candidates, sample_usage, specialist, failed) -> dict:
        specialist_report = specialist.get("report") or {}
        unmatched = specialist.get("unmatched", [])
        specialist_failed = specialist.get("failed", [])
        return {
            "version": "pdf-to-markdown/report@1.0",
            "accepted": False,
            "inputPath": str(self.pdf),
            "outputPath": None,
            "tableCount": len(candidates),
            "statusCounts": status_counts(candidates),
            "failedTableIds": [candidate["tableId"] for candidate in failed],
            "specialistPages": specialist.get("pages", []),
            "unmatchedSpecialistTables": unmatched,
            "failedSpecialistTables": specialist_failed,
            "blockedSpecialistTables": specialist.get("blocked", []),
            "blockedSpecialistPages": specialist.get("blockedPages", []),
            "failedStage": failure_stage(failed, specialist),
            "errors": failure_errors(failed, specialist),
            "tokenUsage": {"sample": sample_usage, "specialist": specialist_report.get("tokenUsage", {})},
            "durationMs": sum(self.timings.values()),
            "timingsMs": self.timings,
        }
