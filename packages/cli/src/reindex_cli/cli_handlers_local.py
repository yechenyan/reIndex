from __future__ import annotations

from pathlib import Path
from typing import Any

from reindex_cli.collection import create_collection
from reindex_cli.config import get_api_url, set_api_url
from reindex_cli.skills import manage_skills


def init(parameters: dict[str, Any]) -> dict[str, Any]:
    root = _resolved(parameters["path"])
    collection = create_collection(root, parameters["name"])
    skills = manage_skills(
        parameters["agent"],
        root,
        update=True,
        codex_home=parameters["codex_home"],
    )
    return {
        "status": "ready",
        **collection,
        "collection_id": collection["id"],
        "skills": [vars(item) for item in skills],
    }


def create(parameters: dict[str, Any]) -> dict[str, Any]:
    return _create_or_rename(parameters, renamed=False)


def rename(parameters: dict[str, Any]) -> dict[str, Any]:
    return _create_or_rename(parameters, renamed=True)


def skills_install(parameters: dict[str, Any]) -> dict[str, Any]:
    return _skills(parameters, update=False)


def skills_update(parameters: dict[str, Any]) -> dict[str, Any]:
    return _skills(parameters, update=True)


def set_api(parameters: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ready", "api_url": set_api_url(parameters["url"])}


def config(parameters: dict[str, Any]) -> dict[str, Any]:
    url = parameters.get("api_url")
    return {"status": "ready", "api_url": set_api_url(url) if url else get_api_url()}


def _create_or_rename(
    parameters: dict[str, Any], *, renamed: bool
) -> dict[str, Any]:
    result = create_collection(_resolved(parameters["path"]), parameters["name"])
    return {
        "status": "ready",
        **result,
        "collection_id": result["id"],
        "renamed": renamed,
    }


def _skills(parameters: dict[str, Any], *, update: bool) -> dict[str, Any]:
    results = manage_skills(
        parameters["agent"],
        _resolved(parameters["workspace_root"]),
        update=update,
        force=parameters["force"],
        codex_home=parameters["codex_home"],
    )
    return {"status": "ready", "skills": [vars(item) for item in results]}


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve()
