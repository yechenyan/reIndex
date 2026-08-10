from __future__ import annotations

import pytest

from pdf_table_5.agents import build_command, has_terminal_event
from pdf_table_5.context import Context, Paths
from pdf_table_5.contracts import validate_find_tables, validate_merge_tables
from pdf_table_5.taskPaperTable import expanded_bbox


PAGES = [{"page": 1, "width": 100.0, "height": 200.0}]


def test_find_table_contract_normalizes_ids() -> None:
    value = {"tables": [{"page": 1, "bbox": [1, 2, 90, 180], "mergeWithPrevious": "no"}]}
    result = validate_find_tables(value, PAGES)
    assert result["tables"][0]["findTableId"] == "find_0001"
    assert result["tables"][0]["preFindTableId"] is None


def test_find_table_contract_rejects_visual_bbox_outside_page() -> None:
    with pytest.raises(ValueError, match="outside page"):
        validate_find_tables({"tables": [{"page": 1, "bbox": [0, 0, 101, 20]}]}, PAGES)


def test_find_table_contract_clips_rounded_edge_on_rotated_visual_page() -> None:
    rotated_page = [{"page": 1, "width": 841.92, "height": 595.32, "sourceRotation": 90}]
    result = validate_find_tables(
        {"tables": [{"page": 1, "bbox": [0, 35, 842, 595], "mergeWithPrevious": "no"}]}, rotated_page
    )
    assert result["tables"][0]["bbox"] == [0.0, 35.0, 841.92, 595.0]


def test_find_table_contract_rejects_merge_across_missing_pages() -> None:
    pages = [
        {"page": number, "width": 100.0, "height": 200.0}
        for number in (39, 40, 43)
    ]
    value = {"tables": [
        {"page": 40, "bbox": [1, 2, 90, 180], "mergeWithPrevious": "no"},
        {"page": 43, "bbox": [1, 2, 90, 180], "mergeWithPrevious": "possible"},
    ]}
    with pytest.raises(ValueError, match="nonconsecutive pages 40 and 43"):
        validate_find_tables(value, pages)


def test_merge_contract_requires_every_finder_item_once() -> None:
    with pytest.raises(ValueError, match="omitted"):
        validate_merge_tables({"tables": [{"tables": [{"findTableId": "a"}]}]}, {"a", "b"})


def test_table_bbox_expands_and_clips_to_visual_page() -> None:
    assert expanded_bbox((5, 10, 90, 180), PAGES[0], 20) == (0.0, 0.0, 100.0, 200.0)


def test_agent_terminal_event_requires_finished_turn() -> None:
    assert has_terminal_event([{"type": "turn.started"}]) is False
    assert has_terminal_event([{"type": "turn.completed"}]) is True


def test_codex_command_uses_project_workspace_and_terra_medium(tmp_path) -> None:
    context = Context(Paths(tmp_path))
    command = build_command(context, tmp_path / "last.json", None, [])
    assert command[:2] == ["codex", "exec"]
    assert "--ignore-user-config" in command
    assert "--skip-git-repo-check" in command
    assert command[command.index("--model") + 1] == "gpt-5.6-terra"
    assert 'model_reasoning_effort="medium"' in command
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert command[command.index("--cd") + 1] == str(tmp_path.resolve())
    assert "--ephemeral" not in command


def test_codex_repair_command_resumes_parser_session(tmp_path) -> None:
    context = Context(Paths(tmp_path))
    command = build_command(context, tmp_path / "last.json", None, [], session_id="session-123")
    assert command[:3] == ["codex", "exec", "resume"]
    assert "session-123" in command
    assert "--sandbox" not in command
    assert "--ephemeral" not in command
