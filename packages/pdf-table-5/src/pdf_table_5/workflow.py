from __future__ import annotations

import traceback
from pathlib import Path

from .context import DEFAULT_AGENT_MODEL, DEFAULT_REASONING_EFFORT, Context, Paths
from .io import read_json, sha256, write_json
from .state import load_state, recorded_step, save_state
from .table_workflow import ensure_parser, review_with_repairs
from .taskListTables import run as list_tables
from .taskPaperFindTables import run as find_tables
from .taskPaperMergeTables import run as merge_tables
from .taskPaperTable import run as prepare_table
from .taskReportTable import final_item, refresh_metrics, run as report_tables


class Workflow:
    def __init__(
        self,
        project: Path,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ):
        paths = Paths(project.resolve())
        params = read_json(paths.params, {})
        self.context = Context(
            paths,
            codex_model=model or params.get("agentModel", DEFAULT_AGENT_MODEL),
            reasoning_effort=reasoning_effort or params.get("agentReasoningEffort", DEFAULT_REASONING_EFFORT),
        )
        self.context.max_repairs = int(self.context.params.get("maxRepairAttempts", 3))

    def run(self) -> dict:
        try:
            return self._run()
        except BaseException as exc:
            state = load_state(self.context)
            state.update(
                status="failed",
                currentStep=None,
                lastError={"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
            )
            save_state(self.context, state)
            raise

    def _run(self) -> dict:
        self.validate_job()
        with recorded_step(self.context, "find-tables") as record:
            found, usage = find_tables(self.context)
            record["tokenUsage"] = usage
            record["details"]["segments"] = len(found["tables"])
        with recorded_step(self.context, "merge-tables") as record:
            merged, usage = merge_tables(self.context, found)
            record["tokenUsage"] = usage
            record["details"]["groups"] = len(merged["tables"])
        with recorded_step(self.context, "list-tables") as record:
            listed = list_tables(self.context, found, merged)
            record["details"]["tables"] = len(listed["tables"])
        table_ids = []
        reviews = []
        for index, item in enumerate(listed["tables"]):
            table_id = item["parseTableId"]
            table_ids.append(table_id)
            self.set_table_index(index)
            try:
                with recorded_step(self.context, f"prepare-{table_id}"):
                    packet = prepare_table(self.context, item)
                with recorded_step(self.context, f"parse-{table_id}") as record:
                    usage = ensure_parser(self.context, table_id, packet)
                    record["tokenUsage"] = usage
                review = review_with_repairs(self.context, table_id)
            except Exception as exc:
                review = self.failed_review(table_id, item, exc)
            reviews.append(review)
            self.record_progress(review)
        with recorded_step(self.context, "final-report") as record:
            report = report_tables(self.context, table_ids)
            record["details"].update(accepted=report["accepted"], tableCount=len(table_ids))
        report = refresh_metrics(self.context, report)
        state = load_state(self.context)
        state.update(status="completed" if report["accepted"] else "failed", currentStep=None)
        save_state(self.context, state)
        return report

    def validate_job(self) -> None:
        if not self.context.paths.job.is_file():
            raise FileNotFoundError("parse/helper/job.json is missing; initialize the project first")
        if not self.context.pdf.is_file():
            raise FileNotFoundError(self.context.pdf)
        expected = self.context.job.get("pdfInfo", {}).get("sha256")
        if expected != sha256(self.context.pdf):
            raise ValueError("Source PDF hash differs from job.json; reinitialize explicitly")

    def record_progress(self, review: dict) -> None:
        path = self.context.paths.helper_json("finalTable.json")
        value = read_json(path, {"version": "pdf-table-5/final-table@1.0", "tables": []})
        item = final_item(self.context, review)
        value["tables"] = [entry for entry in value["tables"] if entry["parseTableId"] != item["parseTableId"]]
        value["tables"].append(item)
        write_json(path, value)

    def set_table_index(self, index: int) -> None:
        state = load_state(self.context)
        state["currentTableIndex"] = index
        save_state(self.context, state)

    @staticmethod
    def failed_review(table_id: str, item: dict, error: Exception) -> dict:
        return {
            "version": "pdf-table-5/review@1.0",
            "parseTableId": table_id,
            "title": item.get("title", ""),
            "status": "failed",
            "accepted": False,
            "errors": [f"{type(error).__name__}: {error}"],
            "outputPath": None,
            "rowCount": 0,
        }
