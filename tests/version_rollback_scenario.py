import json
import shutil
from pathlib import Path

from version_flow_support import (
    RESOLVED_MARKER,
    TECHNOLOGY_CARD,
    V2_MARKER,
    assert_complete_downloads,
    assert_node_only,
    card,
    history,
    run_cli,
)


def exercise_resolution_and_rollback(
    capsys,
    tmp_path: Path,
    api_url: str,
    client_a: Path,
    client_b: Path,
    original_raw: bytes,
    v1: str,
    v2: str,
    package_v1: str,
    embeddings,
) -> None:
    versions = history(capsys, api_url)
    assert [item["version_id"] for item in versions["versions"]] == [v2, v1]
    shown = run_cli(
        capsys,
        "history",
        "test4-all",
        "--version",
        v1,
        "--api-url",
        api_url,
    )
    assert shown["version_id"] == v1
    compared = run_cli(
        capsys,
        "diff",
        "test4-all",
        "--from",
        v1,
        "--to",
        v2,
        "--api-url",
        api_url,
    )
    assert "costs_2020.csv" in json.dumps(compared)

    old_raw = tmp_path / "old-costs.csv"
    historical_get = run_cli(
        capsys,
        "get",
        "raw://costs_2020.csv",
        "--path",
        str(client_a),
        "--version",
        v1,
        "--output",
        str(old_raw),
    )
    assert historical_get["source"] == "download"
    assert old_raw.read_bytes() == original_raw
    historical_checkout = tmp_path / "historical-checkout"
    old_pull = run_cli(
        capsys,
        "pull",
        "test4-all",
        "--output",
        str(historical_checkout),
        "--version",
        v1,
        "--api-url",
        api_url,
    )
    assert old_pull["version_id"] == v1
    assert_node_only(historical_checkout)
    assert V2_MARKER not in card(historical_checkout, TECHNOLOGY_CARD).read_text()

    shutil.copy2(client_a / "costs_2020.csv", client_b / "costs_2020.csv")
    run_cli(capsys, "scan", str(client_b))
    resolved_card = card(client_b, TECHNOLOGY_CARD)
    resolved_card.write_text(
        resolved_card.read_text() + f"\n{RESOLVED_MARKER}.\n", encoding="utf-8"
    )
    continued = run_cli(capsys, "pull", "--path", str(client_b), "--continue")
    assert continued["base_version_id"] == v2
    assert not (client_b / ".rei" / "conflicts.json").exists()
    resolved = run_cli(
        capsys,
        "push",
        str(client_b),
        "--api-url",
        api_url,
        "--message",
        "Resolve local conflict",
    )
    v3 = resolved["version_id"]
    assert resolved["parent_version_id"] == v2

    current_checkout = tmp_path / "current-checkout"
    run_cli(
        capsys,
        "pull",
        "test4-all",
        "--output",
        str(current_checkout),
        "--api-url",
        api_url,
    )
    assert_complete_downloads(capsys, current_checkout, client_a)

    embedded_before_rollback = embeddings.document_count if embeddings else None
    rolled_back = run_cli(
        capsys,
        "rollback",
        "test4-all",
        v1,
        "--api-url",
        api_url,
        "--message",
        "Restore initial import",
    )
    v4 = rolled_back["version_id"]
    assert v4 not in {v1, v2, v3}
    assert rolled_back["parent_version_id"] == v3
    assert rolled_back["source_version_id"] == v1
    assert rolled_back["package_hash"] == package_v1
    assert rolled_back["uploaded_blobs"] == 0
    if embeddings:
        assert embeddings.document_count == embedded_before_rollback

    active = tmp_path / "after-rollback"
    run_cli(
        capsys,
        "pull",
        "test4-all",
        "--output",
        str(active),
        "--api-url",
        api_url,
    )
    marker_search = run_cli(capsys, "search", V2_MARKER, "--path", str(active))
    assert V2_MARKER not in json.dumps(marker_search)
    assert run_cli(capsys, "search", "Ammonia cracker", "--path", str(active))[
        "results"
    ]
    restored_raw = tmp_path / "restored-costs.csv"
    run_cli(
        capsys,
        "get",
        "raw://costs_2020.csv",
        "--path",
        str(active),
        "--output",
        str(restored_raw),
    )
    assert restored_raw.read_bytes() == original_raw

    retained_v2 = tmp_path / "retained-v2.csv"
    run_cli(
        capsys,
        "get",
        "raw://costs_2020.csv",
        "--path",
        str(active),
        "--version",
        v2,
        "--output",
        str(retained_v2),
    )
    assert V2_MARKER.encode() in retained_v2.read_bytes()
    assert len(history(capsys, api_url)["versions"]) == 4
