from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict

from reindex_server.domain import SearchHit, SearchOptions


def paginate_hits(
    hits: list[SearchHit],
    options: SearchOptions,
    revision_id: str,
) -> tuple[list[SearchHit], int, int, str | None]:
    diversified = _limit_per_node(hits, options.max_per_node)
    fingerprint = _fingerprint(options)
    offset = _decode_cursor(options.cursor, revision_id, fingerprint)
    if offset > len(diversified):
        raise ValueError("search cursor is beyond the candidate set")
    end = min(offset + options.limit, len(diversified))
    next_cursor = (
        _encode_cursor(revision_id, fingerprint, end)
        if end < len(diversified)
        else None
    )
    return diversified[offset:end], offset, len(diversified), next_cursor


def _limit_per_node(hits: list[SearchHit], maximum: int) -> list[SearchHit]:
    counts: dict[str, int] = defaultdict(int)
    results: list[SearchHit] = []
    for hit in hits:
        if counts[hit.unit.node_id] >= maximum:
            continue
        counts[hit.unit.node_id] += 1
        results.append(hit)
    return results


def _fingerprint(options: SearchOptions) -> str:
    value = asdict(options)
    value.pop("cursor")
    value.pop("limit")
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def _encode_cursor(revision_id: str, fingerprint: str, offset: int) -> str:
    payload = json.dumps(
        {"v": 1, "revision": revision_id, "query": fingerprint, "offset": offset},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(
    cursor: str | None,
    revision_id: str,
    fingerprint: str,
) -> int:
    if cursor is None:
        return 0
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        if (
            payload["v"] != 1
            or payload["revision"] != revision_id
            or payload["query"] != fingerprint
            or not isinstance(payload["offset"], int)
            or payload["offset"] < 0
        ):
            raise ValueError
        return payload["offset"]
    except (
        binascii.Error,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            "invalid search cursor for this query or active revision"
        ) from error
