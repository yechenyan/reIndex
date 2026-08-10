from __future__ import annotations


def verified_statuses() -> set[str]:
    return {"liteparse_verified", "specialist_verified", "specialist_no_table"}


def status_counts(candidates: list[dict]) -> dict[str, int]:
    result: dict[str, int] = {}
    for candidate in candidates:
        status = candidate["status"]
        result[status] = result.get(status, 0) + 1
    return result


def failure_stage(failed: list[dict], specialist: dict) -> str | None:
    if specialist.get("failed") or specialist.get("error"):
        return "specialist"
    return "verification" if failed or specialist.get("unmatched") else None


def failure_errors(failed: list[dict], specialist: dict) -> list[str]:
    errors = []
    if specialist.get("error"):
        errors.append(str(specialist["error"]))
    for candidate in failed:
        errors.extend(str(item) for item in candidate.get("routeReasons", []))
    return list(dict.fromkeys(errors))
