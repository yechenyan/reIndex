from __future__ import annotations

from .context import Context
from .state import load_state, save_state


def table_snapshot(context: Context, table_id: str) -> dict:
    state = load_state(context)
    tables = state.setdefault("tables", {})
    value = tables.setdefault(table_id, defaults(context, table_id))
    save_state(context, state)
    return dict(value)


def record_parser(context: Context, table_id: str, session_id: str | None) -> dict:
    state, value = mutable(context, table_id)
    value.update(parserSessionId=session_id, artifactRevision=max(1, int(value["artifactRevision"])))
    save_state(context, state)
    return dict(value)


def begin_repair(context: Context, table_id: str, limit: int) -> tuple[int, dict] | None:
    state, value = mutable(context, table_id)
    in_flight = value.get("inFlightAttempt")
    if isinstance(in_flight, int):
        return in_flight, dict(value)
    started = int(value.get("repairAttemptsStarted", 0))
    if started >= limit:
        return None
    attempt = started + 1
    value.update(repairAttemptsStarted=attempt, inFlightAttempt=attempt)
    save_state(context, state)
    return attempt, dict(value)


def complete_repair(context: Context, table_id: str, session_id: str | None) -> dict:
    state, value = mutable(context, table_id)
    attempt = int(value.get("inFlightAttempt") or value.get("repairAttemptsStarted", 0))
    value.update(
        parserSessionId=session_id or value.get("parserSessionId"),
        repairAttemptsCompleted=max(int(value.get("repairAttemptsCompleted", 0)), attempt),
        inFlightAttempt=None,
        artifactRevision=int(value.get("artifactRevision", 0)) + 1,
    )
    save_state(context, state)
    return dict(value)


def record_fallback(context: Context, table_id: str, reason: str) -> None:
    state, value = mutable(context, table_id)
    value["sessionFallbacks"] = int(value.get("sessionFallbacks", 0)) + 1
    value["lastSessionFallback"] = reason[-1000:]
    save_state(context, state)


def mutable(context: Context, table_id: str) -> tuple[dict, dict]:
    state = load_state(context)
    tables = state.setdefault("tables", {})
    return state, tables.setdefault(table_id, defaults(context, table_id))


def defaults(context: Context, table_id: str) -> dict:
    table_dir = context.paths.table_dir(table_id)
    has_artifacts = all((table_dir / name).is_file() for name in ("sample.py", "summary.json", "parse.py"))
    return {
        "parserSessionId": None,
        "repairAttemptsStarted": 0,
        "repairAttemptsCompleted": 0,
        "inFlightAttempt": None,
        "artifactRevision": 1 if has_artifacts else 0,
        "sessionFallbacks": 0,
        "lastSessionFallback": None,
    }
