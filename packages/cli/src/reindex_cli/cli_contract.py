from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

CONTRACT_RESOURCE = "contract/reindex-cli-v1.yaml"


@lru_cache(maxsize=1)
def load_contract() -> dict[str, Any]:
    package = resources.files("reindex_cli")
    text = package.joinpath(CONTRACT_RESOURCE).read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    validate_contract(document)
    return document


def validate_contract(document: object) -> None:
    if not isinstance(document, dict):
        raise ValueError("CLI contract must be an object")
    if document.get("spec") != "reindex/cli@1.0":
        raise ValueError("unsupported CLI contract spec")
    program = document.get("program")
    commands = document.get("commands")
    if not isinstance(program, dict) or not isinstance(commands, list):
        raise ValueError("CLI contract requires program and commands")
    _validate_unique(commands, "id")
    paths = [tuple(command.get("path", [])) for command in commands]
    if any(not path for path in paths) or len(paths) != len(set(paths)):
        raise ValueError("CLI command paths must be present and unique")
    for command in commands:
        parameters = command.get("parameters", [])
        _validate_unique(parameters, "name")
        for parameter in parameters:
            if parameter.get("kind") not in {"argument", "option"}:
                raise ValueError(f"invalid parameter kind in {command['id']}")
            if parameter.get("kind") == "option" and not parameter.get("flags"):
                raise ValueError(f"option without flags in {command['id']}")
        _validate_constraints(command, {item["name"] for item in parameters})
        if "output_schema" not in command:
            raise ValueError(f"command without output_schema: {command['id']}")
        Draft202012Validator.check_schema(_schema(document, command["output_schema"]))
    Draft202012Validator.check_schema(document["error_schema"])


def validate_output(command_id: str, output: object) -> None:
    contract = load_contract()
    command = next(item for item in contract["commands"] if item["id"] == command_id)
    _validator(contract, command["output_schema"]).validate(output)


def public_contract() -> dict[str, Any]:
    return json.loads(json.dumps(load_contract(), ensure_ascii=False))


def write_public_contract(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(public_contract(), ensure_ascii=False, indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")


def _validate_unique(items: list[dict[str, Any]], key: str) -> None:
    values = [item.get(key) for item in items]
    if any(not value for value in values) or len(values) != len(set(values)):
        raise ValueError(f"CLI contract {key} values must be present and unique")


def _schema(contract: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    return {"$defs": contract["$defs"], **schema}


def _validator(
    contract: dict[str, Any], schema: dict[str, Any]
) -> Draft202012Validator:
    return Draft202012Validator(_schema(contract, schema))


def _validate_constraints(command: dict[str, Any], names: set[str]) -> None:
    kinds = {"requires", "conflicts", "mutually_exclusive", "any_present", "all_or_none", "range"}
    for constraint in command.get("constraints", []):
        if constraint.get("kind") not in kinds:
            raise ValueError(f"unsupported constraint in {command['id']}")
        if constraint.get("error") not in {"usage", "business"}:
            raise ValueError(f"constraint without error class in {command['id']}")
        referenced = set(constraint.get("parameters", []))
        if constraint.get("parameter"):
            referenced.add(constraint["parameter"])
        if not constraint.get("message") or not referenced <= names:
            raise ValueError(f"invalid constraint parameters in {command['id']}")
        if constraint["kind"] == "range" and not {
            "minimum",
            "maximum",
        } <= constraint.keys():
            raise ValueError(f"range without bounds in {command['id']}")
