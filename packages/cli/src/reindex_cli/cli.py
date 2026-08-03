from __future__ import annotations

import json
import sys

import click
import httpx
from jsonschema import ValidationError

from reindex_cli.cli_builder import build_cli
from reindex_cli.cli_dispatch import validate_handler_coverage
from reindex_cli.errors import ReIndexError


def main(argv: list[str] | None = None) -> int:
    try:
        validate_handler_coverage()
        output = build_cli().main(args=argv, prog_name="rei", standalone_mode=False)
        if output is not None:
            click.echo(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except click.exceptions.Exit as error:
        return error.exit_code
    except click.ClickException as error:
        error.show(file=sys.stderr)
        return error.exit_code
    except (ReIndexError, OSError, ValueError, httpx.HTTPError, ValidationError) as error:
        payload = {"status": "error", "error": str(error)}
        click.echo(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 1
