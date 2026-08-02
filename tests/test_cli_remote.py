import io
import json
import zipfile
from pathlib import Path

from reindex_cli.archives import build_push_archives, extract_node_archive
from reindex_cli.cli import main
from reindex_cli.collection import resolve_collection
from reindex_cli.collection.state import identity_path
from reindex_cli.errors import ReIndexError
from reindex_cli.get_ops import get_resource
from reindex_cli.remote_state import write_remote
from reindex_cli.util import sha256_bytes

ROOT = Path(__file__).resolve().parents[1]


def output(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_init_installs_and_safely_updates_skills(tmp_path: Path, capsys) -> None:
    project = tmp_path / "My Data"
    project.mkdir()
    codex_home = tmp_path / "codex"
    assert (
        main(
            [
                "init",
                str(project),
                "--name",
                "energy-data",
                "--agent",
                "codex",
                "--codex-home",
                str(codex_home),
            ]
        )
        == 0
    )
    result = output(capsys)
    assert result["name"] == "energy-data"
    assert result["created"] is True
    assert {item["name"] for item in result["skills"]} == {
        "reindex-create",
        "reindex-scan",
        "reindex-data",
    }
    skill = codex_home / "skills" / "reindex-data" / "SKILL.md"
    skill.write_text("custom\n", encoding="utf-8")
    assert (
        main(
            [
                "init",
                str(project),
                "--agent",
                "codex",
                "--codex-home",
                str(codex_home),
            ]
        )
        == 0
    )
    repeated = output(capsys)
    conflict = next(item for item in repeated["skills"] if item["path"] == str(skill))
    assert conflict["status"] == "conflict"
    assert skill.read_text(encoding="utf-8") == "custom\n"


def test_set_api_uses_xdg_config(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("REINDEX_CONFIG_HOME", str(tmp_path / "config"))
    assert main(["set-api", "https://example.test/"]) == 0
    assert output(capsys)["api_url"] == "https://example.test"
    saved = json.loads((tmp_path / "config" / "config.json").read_text())
    assert saved == {"api_url": "https://example.test"}


def test_init_migrates_name_and_rename_keeps_identity(tmp_path: Path, capsys) -> None:
    project = tmp_path / "Legacy Name"
    project.mkdir()
    assert main(["create", str(project), "--name", "first-name"]) == 0
    created = output(capsys)
    state_path = project / ".rei" / "collection.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.pop("name")
    state_path.write_text(json.dumps(state), encoding="utf-8")

    assert main(["init", str(project), "--codex-home", str(tmp_path / "codex")]) == 0
    migrated = output(capsys)
    assert migrated["name"] == "legacy-name"
    assert migrated["collection_id"] == created["collection_id"]
    assert json.loads(state_path.read_text(encoding="utf-8"))["name"] == "legacy-name"

    assert main(["rename", str(project), "new-name"]) == 0
    renamed = output(capsys)
    assert renamed["name"] == "new-name"
    assert renamed["collection_id"] == created["collection_id"]


def test_legacy_identity_filename_remains_readable(tmp_path: Path, capsys) -> None:
    project = tmp_path / "legacy-identities"
    project.mkdir()
    assert main(["create", str(project)]) == 0
    output(capsys)
    current = project / ".rei" / "node-identities.json"
    legacy = project / ".rei" / "identities.json"
    current.replace(legacy)
    assert identity_path(project) == legacy


def test_push_archives_contain_only_referenced_test2_sources() -> None:
    context = resolve_collection(ROOT / "testbase" / "test2")
    package, sources, temporary = build_push_archives(context)
    try:
        with zipfile.ZipFile(package) as bundle:
            assert any(name.endswith("index.node.md") for name in bundle.namelist())
        with zipfile.ZipFile(sources) as bundle:
            assert set(bundle.namelist()) == {
                "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf",
                "costs_2020.csv",
            }
    finally:
        temporary.cleanup()


def test_get_reuses_local_content_without_download(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    node_dir = root / "reIndex" / "demo"
    node_dir.mkdir(parents=True)
    content = b"name,value\na,1\n"
    digest = sha256_bytes(content)
    (node_dir / "table.csv").write_bytes(content)
    (node_dir / "table.node.md").write_text(
        "---\n"
        'spec: "reindex/node@1.0"\n'
        'id: "00000000-0000-0000-0000-000000000002"\n'
        'kind: "table"\n'
        "order: 1\n"
        'title: "Table"\n'
        'description: "A table."\n'
        "content:\n"
        '  uri: "./table.csv"\n'
        '  media_type: "text/csv"\n'
        f'  sha256: "{digest}"\n'
        "table:\n  row_count: 1\n  grain: row\n"
        "  columns:\n    - name: name\n    - name: value\n"
        "---\nTable card.\n",
        encoding="utf-8",
    )
    write_remote(
        root,
        {"name": "demo", "api_url": "http://unused", "node_dir": "reIndex/demo"},
    )
    result = get_resource(
        "table.node.md",
        root,
        target="content",
        asset_ordinal=None,
        output=None,
        remote=None,
        api_url=None,
    )
    assert result["source"] == "local"
    assert Path(result["path"]) == node_dir / "table.csv"


def test_pull_archive_accepts_only_node_cards(tmp_path: Path) -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("content.csv", "a,b\n")
    try:
        extract_node_archive(archive.getvalue(), tmp_path / "bad")
    except ReIndexError as error:
        assert "non-Node" in str(error)
    else:
        raise AssertionError("non-Node pull archive was accepted")
