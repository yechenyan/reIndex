from __future__ import annotations

import json
import hashlib
from pathlib import Path

from click.testing import CliRunner
from jsonschema import ValidationError

from reindex_cli.cli_builder import build_cli
from reindex_cli.cli import main
from reindex_cli.cli_contract import load_contract, validate_output
from reindex_cli.cli_dispatch import HANDLERS, validate_handler_coverage

ROOT = Path(__file__).resolve().parents[1]
WEB_CONTRACT = ROOT / "packages" / "web-app" / "public" / "doc" / "cli-v1.json"
V1_SURFACE_SHA256 = "bf4ac7c4a7711a0e883a1a38492645b3058009b3057b47db771fc45818ea8e2a"


def test_contract_is_authoritative_for_commands_and_handlers() -> None:
    contract = load_contract()
    validate_handler_coverage()
    contract_ids = {command["id"] for command in contract["commands"]}
    assert contract_ids == set(HANDLERS)
    assert len(contract_ids) == 18


def test_click_tree_preserves_v1_command_paths() -> None:
    runner = CliRunner()
    root = runner.invoke(build_cli(), ["--help"])
    skills = runner.invoke(build_cli(), ["skills", "--help"])
    assert root.exit_code == 0
    for name in (
        "init create rename inspect scan check skills set-api config push fetch pull "
        "history diff rollback search get"
    ).split():
        assert name in root.output
    assert "install" in skills.output
    assert "update" in skills.output


def test_contract_preserves_important_defaults_and_choices() -> None:
    commands = {item["id"]: item for item in load_contract()["commands"]}
    search = {item["name"]: item for item in commands["search"]["parameters"]}
    history = {item["name"]: item for item in commands["history"]["parameters"]}
    assert search["mode"]["choices"] == ["lexical", "semantic", "hybrid"]
    assert search["mode"]["default"] == "lexical"
    assert search["limit"]["default"] == 10
    assert history["limit"]["default"] == 20
    assert (history["limit"]["minimum"], history["limit"]["maximum"]) == (1, 100)


def test_web_cli_document_is_generated_from_same_contract() -> None:
    assert json.loads(WEB_CONTRACT.read_text(encoding="utf-8")) == load_contract()


def test_complete_v1_interface_fingerprint_is_stable() -> None:
    contract = load_contract()
    commands = []
    keys = ("name", "kind", "flags", "type", "required", "default", "choices")
    for command in contract["commands"]:
        commands.append(
            {
                "id": command["id"],
                "path": command["path"],
                "parameters": [
                    {key: item[key] for key in keys if key in item}
                    for item in command.get("parameters", [])
                ],
                "constraints": command.get("constraints", []),
                "output_schema": command["output_schema"],
            }
        )
    surface = {
        "program": contract["program"],
        "groups": contract.get("groups", []),
        "commands": commands,
    }
    payload = json.dumps(
        surface, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(payload).hexdigest() == V1_SURFACE_SHA256


def test_contract_constraints_preserve_usage_and_business_exit_codes(capsys) -> None:
    assert main(["pull", "--output", "/tmp/a", "--path", "/tmp/b"]) == 2
    assert "only one" in capsys.readouterr().err
    assert main(["history", "--limit", "101"]) == 1
    assert "between 1 and 100" in capsys.readouterr().err
    assert main(["diff", ".", "--from", "one"]) == 1
    assert "requires both" in capsys.readouterr().err


def test_each_command_has_a_rejecting_success_schema() -> None:
    for command in load_contract()["commands"]:
        try:
            validate_output(command["id"], {})
        except ValidationError:
            continue
        raise AssertionError(f"empty output passed schema for {command['id']}")
