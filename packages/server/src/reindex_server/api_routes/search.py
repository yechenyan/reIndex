from __future__ import annotations

from fastapi import FastAPI

from reindex_server.api_errors import http_error
from reindex_server.api_models import SearchApiResponse, TableQueryResponse
from reindex_server.api_serialization import search_response
from reindex_server.contracts import GrepRequest, SearchRequest, TableQueryRequest
from reindex_server.table_query import query_csv


def install_search_routes(app: FastAPI) -> None:
    def collection_id(name: str) -> str:
        return app.state.service.resolve_collection(name).id

    @app.post("/v1/search", response_model=SearchApiResponse, tags=["Search"])
    def search(request: SearchRequest) -> dict:
        try:
            response = app.state.service.search(
                collection_id(request.collection_key), request.options()
            )
            return search_response(
                app.state.service,
                collection_id(request.collection_key),
                response,
                request,
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/grep", response_model=SearchApiResponse, tags=["Search"])
    def grep(request: GrepRequest) -> dict:
        try:
            response = app.state.service.grep(
                collection_id(request.collection_key),
                request.pattern,
                request.limit,
                request.regex,
                request.case_sensitive,
            )
            return search_response(
                app.state.service, collection_id(request.collection_key), response
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/tables/query", response_model=TableQueryResponse, tags=["Search"])
    def query_table(request: TableQueryRequest) -> dict:
        try:
            node = app.state.service.get_node(
                collection_id(request.collection_key), request.node_key
            )
            content = node.link("content")
            if node.kind != "table" or not content:
                raise ValueError("node is not a queryable table")
            with app.state.service.store.materialize(
                content.resource.object_key
            ) as path:
                return query_csv(path, request.sql, request.params)
        except Exception as error:
            raise http_error(error) from error
