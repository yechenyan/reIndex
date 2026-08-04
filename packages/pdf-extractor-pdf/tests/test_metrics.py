from __future__ import annotations

import pytest

from pdf_extractor_pdf.metrics import cancel_stage, finish_stage, metrics_report, record_agent, start_stage


def test_parallel_stage_metrics_are_automatically_aggregated(tmp_path) -> None:
    evidence = tmp_path / "evidence"
    extraction = start_stage(evidence, "extraction", "extraction_agent", "gpt-test", "extract-1", "agent-extract")
    qa = start_stage(evidence, "qa", "qa_agent", "gpt-test", "qa-1", "agent-qa")
    assert extraction["run_id"] != qa["run_id"]
    finish_stage(
        evidence, "qa-1", "completed", conversation_turns=1, repair_rounds=0,
        token_usage=None, notes="host token telemetry unavailable",
    )
    finish_stage(
        evidence, "extract-1", "completed", conversation_turns=99, repair_rounds=99,
        token_usage={"input": 10, "output": 5, "total": 15},
    )
    start_stage(evidence, "extraction", "extraction_agent", "gpt-test", "extract-2", "agent-extract", dispatch_kind="followup")
    finish_stage(evidence, "extract-2", "completed")
    start_stage(evidence, "review", "main_agent", "gpt-test", "main-1", "agent-main", dispatch_kind="orchestrator")
    finish_stage(evidence, "main-1", "completed")
    report = metrics_report(evidence)
    assert report["spec"] == "pdf-extractor-pdf/metrics-summary@2.0"
    assert report["stage_totals"]["runs"] == 4
    assert report["dispatch_totals"]["child_agent_conversations"] == 3
    assert report["dispatch_totals"]["child_followup_dispatches"] == 1
    assert report["dispatch_totals"]["main_orchestration_steps"] == 1
    assert "all_agent_conversations" not in report["dispatch_totals"]
    assert report["stage_totals"]["parallel_envelope_seconds"] >= max(
        item["wall_seconds"] for item in report["stages"]
    )
    assert report["token_usage"] == {
            "available_runs": 1, "unavailable_runs": 3,
        "totals": {"input": 10, "output": 5, "total": 15},
    }
    assert (evidence / "metrics" / "summary.json").is_file()


def test_legacy_agent_records_are_deduplicated_by_run_identity(tmp_path) -> None:
    evidence = tmp_path / "evidence"
    base = {
        "role": "qa_agent", "model": "gpt-test",
        "started_at": "2026-01-01T00:00:00Z", "ended_at": "2026-01-01T00:00:01Z",
        "conversation_turns": 1, "token_usage": None,
    }
    record_agent(evidence, base)
    record_agent(evidence, {**base, "ended_at": "2026-01-01T00:00:02Z", "notes": "supersedes"})
    report = metrics_report(evidence)
    assert len(report["agent_runs"]) == 1
    assert report["agent_runs"][0]["notes"] == "supersedes"


def test_cancelled_pre_dispatch_stage_is_not_a_conversation(tmp_path) -> None:
    evidence = tmp_path / "evidence"
    start_stage(evidence, "extraction", "extraction_agent", "gpt-test", "never-sent", "agent-x")
    cancel_stage(evidence, "never-sent", "followup was not dispatched")
    report = metrics_report(evidence)
    assert report["dispatch_totals"]["child_agent_conversations"] == 0


def test_same_agent_cannot_start_overlapping_stage(tmp_path) -> None:
    evidence = tmp_path / "evidence"
    start_stage(evidence, "extraction", "extraction_agent", "gpt-test", "one", "agent-x")
    with pytest.raises(ValueError, match="unfinished stage"):
        start_stage(evidence, "extraction", "extraction_agent", "gpt-test", "two", "agent-x")
    finish_stage(evidence, "one", "completed")
    assert start_stage(
        evidence, "extraction", "extraction_agent", "gpt-test", "two", "agent-x",
    )["run_id"] == "two"
