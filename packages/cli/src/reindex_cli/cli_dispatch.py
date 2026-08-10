from __future__ import annotations

from collections.abc import Callable
from typing import Any

from reindex_cli import cli_handlers_local as local
from reindex_cli import cli_handlers_package as package
from reindex_cli import cli_handlers_remote as remote
from reindex_cli.cli_contract import load_contract, validate_output

Handler = Callable[[dict[str, Any]], dict[str, Any]]

HANDLERS: dict[str, Handler] = {
    "init": local.init,
    "create": local.create,
    "rename": local.rename,
    "inspect": package.inspect,
    "scan": package.scan,
    "check": package.check,
    "skills_install": local.skills_install,
    "skills_update": local.skills_update,
    "set_api": local.set_api,
    "config": local.config,
    "push": remote.push,
    "fetch": remote.fetch,
    "pull": remote.pull,
    "history": remote.history,
    "diff": remote.diff,
    "rollback": remote.rollback,
    "search": remote.search,
    "get": remote.get,
}


def dispatch(command_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    result = HANDLERS[command_id](parameters)
    validate_output(command_id, result)
    return result


def validate_handler_coverage() -> None:
    contract_ids = {command["id"] for command in load_contract()["commands"]}
    handler_ids = set(HANDLERS)
    if contract_ids != handler_ids:
        missing = sorted(contract_ids - handler_ids)
        extra = sorted(handler_ids - contract_ids)
        raise ValueError(f"CLI handler mismatch: missing={missing}, extra={extra}")
