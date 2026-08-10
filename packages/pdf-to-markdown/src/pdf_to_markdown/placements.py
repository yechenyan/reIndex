from __future__ import annotations


def placement_records(replacements: list[dict]) -> list[dict]:
    return [
        {
            "replacementId": item["replacementId"],
            "pages": item["specialist"]["pages"],
            "parseTableIds": item["specialist"]["parseTableIds"],
            "affectedTableIds": item["affectedTableIds"],
        }
        for item in replacements
    ]
