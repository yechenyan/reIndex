from __future__ import annotations

import json
from pathlib import Path

import httpx

from reindex_cli.errors import ReIndexError


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 1800.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict:
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            return self._json(client.get("/health"))

    def upload_blob(self, upload_id: str, sha256: str, path: Path) -> dict:
        with (
            path.open("rb") as stream,
            httpx.Client(base_url=self.base_url, timeout=self.timeout) as client,
        ):
            return self._json(
                client.post(
                    "/v1/push/blob",
                    data={"upload_id": upload_id, "sha256": sha256},
                    files={"blob": (path.name, stream, "application/octet-stream")},
                )
            )

    def json(self, path: str, payload: dict, timeout: float | None = None) -> dict:
        with httpx.Client(base_url=self.base_url, timeout=timeout or self.timeout) as client:
            return self._json(client.post(path, json=payload))

    def bytes(self, path: str, payload: dict) -> tuple[bytes, dict[str, str]]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.post(path, json=payload)
            self._raise(response)
            return response.content, dict(response.headers)

    def _json(self, response: httpx.Response) -> dict:
        self._raise(response)
        try:
            value = response.json()
        except json.JSONDecodeError as error:
            raise ReIndexError("Server returned invalid JSON") from error
        if not isinstance(value, dict):
            raise ReIndexError("Server returned an invalid response")
        return value

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            body = response.json()
            detail = body.get("error", body)
            message = detail.get("message") if isinstance(detail, dict) else None
            code = detail.get("code") if isinstance(detail, dict) else None
        except (json.JSONDecodeError, AttributeError):
            message = None
            code = None
        raise ReIndexError(
            f"Server request failed ({response.status_code}): "
            f"{f'{code}: ' if code else ''}"
            f"{message or response.text or response.reason_phrase}"
        )
