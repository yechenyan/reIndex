import json
import shutil
from pathlib import Path

from version_flow_support import (
    B_MARKER,
    EXPECTED_NODES,
    TECHNOLOGY_CARD,
    V2_MARKER,
    assert_node_only,
    card,
    history,
    json_file,
    replace_marker,
    run_cli,
    run_cli_error,
    worktree_files,
)


def exercise_conflict_flow(
    capsys,
    tmp_path: Path,
    api_url: str,
    client_a: Path,
    v1: str,
    first: dict,
    embeddings,
    embedded_v1: int | None,
) -> tuple[Path, str]:
    client_b = tmp_path / "client-b"
    shutil.copytree(client_a, client_b)
    clean_authoring = tmp_path / "clean-authoring"
    shutil.copytree(client_a, clean_authoring)
    clean_checkout = tmp_path / "clean-checkout"
    pulled_v1 = run_cli(
        capsys,
        "pull",
        "test4-all",
        "--output",
        str(clean_checkout),
        "--api-url",
        api_url,
    )
    assert pulled_v1["version_id"] == v1
    assert pulled_v1["nodes"] == EXPECTED_NODES
    assert_node_only(clean_checkout)

    replace_marker(client_a, "Ammonia cracker", V2_MARKER)
    run_cli(capsys, "scan", str(client_a))
    second = run_cli(
        capsys,
        "push",
        str(client_a),
        "--api-url",
        api_url,
        "--message",
        "Publish version two marker",
    )
    v2 = second["version_id"]
    assert second["parent_version_id"] == v1
    assert v2 != v1
    assert 0 < second["uploaded_blobs"] < first["uploaded_blobs"]
    if embeddings:
        assert embedded_v1 < embeddings.document_count < embedded_v1 * 2

    fast_forward = run_cli(capsys, "pull", "--path", str(clean_checkout))
    assert fast_forward["version_id"] == v2
    assert V2_MARKER in card(clean_checkout, TECHNOLOGY_CARD).read_text()

    authoring_before = worktree_files(clean_authoring)
    authoring_pull = run_cli_error(capsys, "pull", "--path", str(clean_authoring))
    assert "not replaced" in authoring_pull["error"].lower()
    assert worktree_files(clean_authoring) == authoring_before

    replace_marker(client_b, "Ammonia cracker", B_MARKER)
    run_cli(capsys, "scan", str(client_b))
    stale = run_cli_error(capsys, "push", str(client_b), "--api-url", api_url)
    assert "409" in stale["error"]
    assert "advanced" in stale["error"].lower()

    before_pull = worktree_files(client_b)
    fetched = run_cli(capsys, "fetch", str(client_b), "--api-url", api_url)
    assert fetched["base_version_id"] == v1
    assert fetched["head_version_id"] == v2
    conflict = run_cli_error(capsys, "pull", "--path", str(client_b))
    assert "conflict" in conflict["error"].lower()
    assert worktree_files(client_b) == before_pull
    remote = json_file(client_b / ".rei" / "remote.json")
    assert remote["base_version_id"] == v1
    assert remote["head_version_id"] == v2
    conflicts = json_file(client_b / ".rei" / "conflicts.json")
    assert conflicts["spec"] == "reindex/conflicts@1.0"
    assert "costs_2020.csv" in json.dumps(conflicts)
    blocked = run_cli_error(capsys, "push", str(client_b), "--api-url", api_url)
    assert "conflict" in blocked["error"].lower()
    assert len(history(capsys, api_url)["versions"]) == 2
    return client_b, v2
