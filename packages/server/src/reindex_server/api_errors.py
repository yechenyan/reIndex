from __future__ import annotations

import re
from contextvars import ContextVar
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from reindex_server.errors import ConflictError, StaleBaseError

_REQUEST_ID = ContextVar[str]("reindex_request_id", default="")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def install_api_error_handling(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _VALID_REQUEST_ID.fullmatch(supplied) else uuid4().hex
        token = _REQUEST_ID.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _REQUEST_ID.reset(token)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, error: HTTPException):
        detail = error.detail if isinstance(error.detail, dict) else {}
        return _error_response(
            error.status_code,
            detail.get("code", "http_error"),
            detail.get("message", str(error.detail)),
            detail.get("details"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, error: RequestValidationError
    ):
        return _error_response(
            422,
            "invalid_request",
            "request validation failed",
            _validation_details(error),
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(_request: Request, _error: Exception):
        return _error_response(500, "internal_error", "internal server error")


def http_error(error: Exception) -> HTTPException:
    message = _message(error)
    if isinstance(error, StaleBaseError):
        return HTTPException(
            409,
            {
                "code": "stale_base",
                "message": message,
                "details": [
                    {
                        "base_version_id": error.base_version_id,
                        "head_version_id": error.head_version_id,
                    }
                ],
            },
        )
    if isinstance(error, ConflictError):
        return HTTPException(409, {"code": "conflict", "message": message})
    if isinstance(error, KeyError):
        return HTTPException(404, {"code": "not_found", "message": message})
    if isinstance(error, RuntimeError):
        return HTTPException(409, {"code": "conflict", "message": message})
    if isinstance(error, ValueError):
        return HTTPException(400, {"code": "invalid_request", "message": message})
    return HTTPException(
        500, {"code": "internal_error", "message": "internal server error"}
    )


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict] | None = None,
) -> JSONResponse:
    error = {
        "code": code,
        "message": message,
        "request_id": _REQUEST_ID.get(),
    }
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


def _message(error: Exception) -> str:
    if isinstance(error, KeyError) and error.args:
        return str(error.args[0])
    return str(error)


def _validation_details(error: RequestValidationError) -> list[dict]:
    details = []
    for value in error.errors():
        item = {key: current for key, current in value.items() if key != "input"}
        if "ctx" in item:
            item["ctx"] = {key: str(current) for key, current in item["ctx"].items()}
        details.append(jsonable_encoder(item))
    return details
