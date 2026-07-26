from __future__ import annotations

import json
from pathlib import Path

import pytest
from reindex_server.evaluation import _metrics, load_dataset


def test_evaluation_metrics() -> None:
    metrics = _metrics([0, 1, 0, 1], relevant_count=2)
    assert metrics["recall"] == 1
    assert metrics["mrr"] == 0.5
    assert metrics["ndcg"] == pytest.approx(
        (1 / 1.584962500721156 + 1 / 2.321928094887362) / (1 + 1 / 1.584962500721156)
    )


def test_load_evaluation_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "search-eval.jsonl"
    path.write_text(
        json.dumps(
            {
                "query": "solar capacity",
                "relevant_node_ids": ["00000000-0000-0000-0000-000000000001"],
            }
        ),
        encoding="utf-8",
    )
    cases = load_dataset(path)
    assert cases[0].query == "solar capacity"
    assert cases[0].relevant_count == 1
