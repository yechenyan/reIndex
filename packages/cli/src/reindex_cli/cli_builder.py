from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from reindex_cli import __version__
from reindex_cli.cli_constraints import validate_constraints
from reindex_cli.cli_contract import load_contract
from reindex_cli.cli_dispatch import dispatch


def build_cli() -> click.Group:
    contract = load_contract()
    root = click.Group(
        name=contract["program"]["name"],
        help=contract["program"]["summary"],
        params=[_version_option()],
    )
    groups: dict[tuple[str, ...], click.Group] = {(): root}
    for group_spec in contract.get("groups", []):
        path = tuple(group_spec["path"])
        parent = groups[path[:-1]]
        group = click.Group(name=path[-1], help=group_spec["summary"])
        parent.add_command(group)
        groups[path] = group
    for command_spec in contract["commands"]:
        path = tuple(command_spec["path"])
        command = click.Command(
            name=path[-1],
            help=command_spec["summary"],
            params=[_parameter(item) for item in command_spec.get("parameters", [])],
            callback=_callback(command_spec),
        )
        groups[path[:-1]].add_command(command)
    return root


def _parameter(spec: dict[str, Any]) -> click.Parameter:
    parameter_type = _type(spec)
    default = _default(spec.get("default"))
    if spec["kind"] == "argument":
        return click.Argument(
            [spec["name"]],
            type=parameter_type,
            required=spec.get("required", False),
            default=default,
        )
    kwargs: dict[str, Any] = {
        "type": parameter_type,
        "default": default,
        "help": spec.get("description"),
        "show_default": "cwd" if spec.get("default") == "cwd" else True,
    }
    if spec["type"] == "boolean":
        kwargs.update(is_flag=True, type=None)
    return click.Option([*spec["flags"], spec["name"]], **kwargs)


def _type(spec: dict[str, Any]) -> click.ParamType:
    if spec.get("choices"):
        return click.Choice(spec["choices"], case_sensitive=True)
    if spec["type"] == "path":
        return click.Path(path_type=Path)
    if spec["type"] == "integer":
        return click.INT
    return click.STRING


def _default(value: Any) -> Any:
    if value == "cwd":
        return Path.cwd
    return value


def _callback(command: dict[str, Any]):
    def invoke(**parameters: Any) -> dict[str, Any]:
        validate_constraints(command, parameters)
        return dispatch(command["id"], parameters)

    return invoke


def _version_option() -> click.Option:
    def show_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
        if value and not ctx.resilient_parsing:
            click.echo(__version__)
            ctx.exit()

    return click.Option(
        ["--version"],
        is_flag=True,
        is_eager=True,
        expose_value=False,
        callback=show_version,
        help="Show the version and exit.",
    )
