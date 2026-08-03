from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient
from reindex_server.app import create_app
from reindex_server.openapi_contract import (
    implementation_openapi,
    load_openapi_contract,
)


def test_authoritative_contract_matches_fastapi_implementation() -> None:
    app = create_app(object())
    assert implementation_openapi(app) == load_openapi_contract()


def test_runtime_serves_the_authoritative_contract() -> None:
    app = create_app(object())

    async def request_schema():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/openapi.json")

    response = asyncio.run(request_schema())
    assert response.status_code == 200
    assert response.json() == load_openapi_contract()


def test_docs_use_scalar_and_the_authoritative_contract_url() -> None:
    app = create_app(object())

    async def request_docs():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/docs")

    response = asyncio.run(request_docs())
    assert response.status_code == 200
    assert "@scalar/api-reference@1.63.0" in response.text
    assert '"url": "/openapi.json"' in response.text
    assert '"showDeveloperTools": "never"' in response.text
    assert '"telemetry": false' in response.text


def test_swagger_routes_are_not_exposed() -> None:
    app = create_app(object())

    async def request_removed_routes():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return (
                await client.get("/docs/swagger"),
                await client.get("/docs/oauth2-redirect"),
            )

    swagger, redirect = asyncio.run(request_removed_routes())
    assert swagger.status_code == 404
    assert redirect.status_code == 404


def test_binary_responses_are_described_without_changing_handlers() -> None:
    paths = load_openapi_contract()["paths"]
    pull = paths["/v1/pull"]["post"]["responses"]["200"]
    resource = paths["/v1/get"]["post"]["responses"]["200"]
    assert set(pull["content"]) == {"application/zip"}
    assert set(resource["content"]) == {"*/*"}
    assert "X-ReIndex-Package-Hash" in pull["headers"]
    assert "X-ReIndex-SHA256" in resource["headers"]
