from __future__ import annotations

from typing import Any

def push(parameters: dict[str, Any]) -> dict[str, Any]:
    from reindex_cli.remote_ops import push_collection

    return push_collection(
        parameters["path"],
        parameters["api_url"],
        message=parameters["message"],
        dry_run=parameters["dry_run"],
    )


def fetch(parameters: dict[str, Any]) -> dict[str, Any]:
    from reindex_cli.remote_ops import fetch_collection

    return fetch_collection(parameters["path"], parameters["api_url"])


def pull(parameters: dict[str, Any]) -> dict[str, Any]:
    from reindex_cli.checkout import pull_collection

    return pull_collection(
        parameters["name"],
        parameters["output"],
        parameters["api_url"],
        path=parameters["path"],
        version_id=parameters["version_id"],
        continue_pull=parameters["continue_pull"],
    )


def history(parameters: dict[str, Any]) -> dict[str, Any]:
    from reindex_cli.remote_ops import history_collection

    return history_collection(
        parameters["target"],
        parameters["api_url"],
        version_id=parameters["version_id"],
        limit=parameters["limit"],
        cursor=parameters["cursor"],
    )


def diff(parameters: dict[str, Any]) -> dict[str, Any]:
    from reindex_cli.remote_ops import diff_collection

    return diff_collection(
        parameters["target"],
        parameters["api_url"],
        remote=parameters["remote"],
        from_version=parameters["from_version"],
        to_version=parameters["to_version"],
    )


def rollback(parameters: dict[str, Any]) -> dict[str, Any]:
    from reindex_cli.remote_ops import rollback_collection

    return rollback_collection(
        parameters["name"],
        parameters["version_id"],
        parameters["api_url"],
        message=parameters["message"],
        dry_run=parameters["dry_run"],
    )


def search(parameters: dict[str, Any]) -> dict[str, Any]:
    from reindex_cli.remote_ops import search_remote

    return search_remote(
        parameters["query"],
        parameters["path"],
        parameters["remote"],
        parameters["api_url"],
        parameters["mode"],
        parameters["limit"],
    )


def get(parameters: dict[str, Any]) -> dict[str, Any]:
    from reindex_cli.get_ops import get_resource

    return get_resource(
        parameters["reference"],
        parameters["path"],
        target=parameters["target"],
        asset_ordinal=parameters["asset_ordinal"],
        output=parameters["output"],
        remote=parameters["remote"],
        api_url=parameters["api_url"],
        version_id=parameters["version_id"],
    )
