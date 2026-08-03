from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from scalar_fastapi import AgentScalarConfig, get_scalar_api_reference

API_DESCRIPTION = """ReIndex 1.0 package storage, versioning, retrieval, and search API.

The HTTP v1 contract is backward compatible within the v1 path namespace. The
three-stage publish flow is start upload, upload missing blobs, then commit.
"""

OPENAPI_TAGS = [
    {"name": "System", "description": "Service health and runtime metadata."},
    {"name": "Collections", "description": "Collection discovery and Node browsing."},
    {
        "name": "Versions",
        "description": "Version upload, commit, history, and download.",
    },
    {"name": "Resources", "description": "Exact resource retrieval."},
    {"name": "Search", "description": "Search, grep, and table queries."},
]


def binary_response(description: str, media_types: tuple[str, ...]) -> dict[int, Any]:
    return {
        200: {
            "description": description,
            "content": {
                media_type: {"schema": {"type": "string", "format": "binary"}}
                for media_type in media_types
            },
        }
    }


PULL_RESPONSES = binary_response(
    "Node-only ZIP for the selected Collection version.", ("application/zip",)
)
PULL_RESPONSES[200]["headers"] = {
    "Content-Disposition": {"schema": {"type": "string"}},
    "Content-Length": {"schema": {"type": "string"}},
    "X-ReIndex-Package-Hash": {"schema": {"type": "string"}},
    "X-ReIndex-Version-ID": {"schema": {"type": "string", "format": "uuid"}},
}

RESOURCE_RESPONSES = binary_response(
    "Exact resource bytes. Content-Type is the stored resource media type.",
    ("*/*",),
)
RESOURCE_RESPONSES[200]["headers"] = {
    "Content-Disposition": {"schema": {"type": "string"}},
    "Content-Length": {"schema": {"type": "string"}},
    "ETag": {"schema": {"type": "string"}},
    "X-ReIndex-SHA256": {"schema": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
}


def install_api_docs(app: FastAPI) -> None:
    @app.get("/docs", include_in_schema=False)
    async def scalar_api_reference():
        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=f"{app.title} — API Reference",
            scalar_js_url=("https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.63.0"),
            scalar_proxy_url="",
            show_developer_tools="never",
            telemetry=False,
            agent=AgentScalarConfig(disabled=True),
        )
