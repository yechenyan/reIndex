from __future__ import annotations

import json
from copy import deepcopy
from difflib import unified_diff
from importlib.resources import files
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

CONTRACT_RESOURCE = "openapi/reindex-http-v1.yaml"


def load_openapi_contract() -> dict[str, Any]:
    resource = files("reindex_server").joinpath(CONTRACT_RESOURCE)
    value = yaml.safe_load(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Invalid OpenAPI contract: {CONTRACT_RESOURCE}")
    return value


def implementation_openapi(app: FastAPI) -> dict[str, Any]:
    return get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        summary=app.summary,
        description=app.description,
        routes=app.routes,
        webhooks=app.webhooks.routes,
        tags=app.openapi_tags,
        servers=app.servers,
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
        separate_input_output_schemas=app.separate_input_output_schemas,
        external_docs=app.openapi_external_docs,
    )


def install_openapi_contract(app: FastAPI) -> None:
    contract = load_openapi_contract()
    app.openapi_schema = deepcopy(contract)

    def contract_openapi() -> dict[str, Any]:
        return app.openapi_schema

    app.openapi = contract_openapi


def openapi_diff(expected: dict[str, Any], actual: dict[str, Any]) -> str:
    expected_json = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True)
    actual_json = json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True)
    return "\n".join(
        unified_diff(
            expected_json.splitlines(),
            actual_json.splitlines(),
            fromfile="authoritative contract",
            tofile="FastAPI implementation",
            lineterm="",
        )
    )
