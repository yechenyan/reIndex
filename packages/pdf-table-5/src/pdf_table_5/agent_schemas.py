from __future__ import annotations

from copy import deepcopy


def strict_object(title: str, properties: dict, required: tuple[str, ...] | None = None) -> dict:
    return {
        "type": "object",
        "title": title,
        "properties": properties,
        "required": list(required or properties),
        "additionalProperties": False,
    }


def string_object(title: str, fields: tuple[str, ...]) -> dict:
    return root_schema(strict_object(title, {field: {"type": "string"} for field in fields}))


def root_schema(value: dict) -> dict:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **value}


SAMPLE_ROW_SCHEMA = strict_object(
    "SampleRow",
    {
        "rowIndex": {"type": "integer", "minimum": 1},
        "values": {"type": "array", "items": {"type": "string"}},
    },
)

COMPARE_RULE_SCHEMA = strict_object(
    "SampleCompareRule",
    {
        "kind": {"type": "string", "enum": ["ignore_space_hyphen"]},
        "columns": {
            "type": "array",
            "items": {"type": "integer", "minimum": 0},
            "minItems": 1,
            "uniqueItems": True,
        },
        "rowIndexes": {"type": "array", "items": {"type": "integer", "minimum": 0}},
    },
    required=("kind", "columns"),
)

SAMPLE_SCHEMA = strict_object(
    "ParserSample",
    {
        "mode": {"type": "string", "enum": ["content", "skip"]},
        "totalRows": {"type": "integer", "minimum": 0},
        "header": {"type": "array", "items": {"type": "string"}},
        "rows": {"type": "array", "items": SAMPLE_ROW_SCHEMA},
        "skipReason": {"type": "string"},
        "compareRules": {"type": "array", "items": COMPARE_RULE_SCHEMA},
    },
    required=("mode", "totalRows", "header", "rows", "skipReason"),
)

SUMMARY_SCHEMA = strict_object(
    "ParserSummary",
    {
        "title": {"type": "string"},
        "classification": {"type": "string"},
        "pages": {"type": "array", "items": {"type": "integer", "minimum": 1}},
        "bboxes": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
        },
        "surroundingText": strict_object(
            "SurroundingText", {"before": {"type": "string"}, "after": {"type": "string"}}
        ),
        "imageTable": {"type": "boolean"},
        "skipped": {"type": "boolean"},
        "skipReason": {"type": "string"},
        "strategy": {"type": "string", "pattern": "^$|^strategy_[A-Za-z0-9_]+\\.py$"},
        "sqlFriendly": {"type": "boolean"},
        "extractionDpi": {"type": "integer", "minimum": 1},
        "steps": {"type": "array", "items": {"type": "string"}},
    },
)

PARSER_FIELDS = {
    "samplePy": {"type": "string"},
    "summary": SUMMARY_SCHEMA,
    "parsePy": {"type": "string"},
    "strategyFileName": {"type": "string", "pattern": "^$|^strategy_[A-Za-z0-9_]+\\.py$"},
    "strategyPy": {"type": "string"},
}


def nullable(schema: dict) -> dict:
    value = deepcopy(schema)
    current = value.get("type")
    value["type"] = [current, "null"] if isinstance(current, str) else ["null"]
    return value


FINDER_OUTPUT_SCHEMA = string_object("FinderOutput", ("findTableJson",))
MERGE_OUTPUT_SCHEMA = string_object("MergeOutput", ("mergeDecisionsJson",))
PARSER_OUTPUT_SCHEMA = root_schema(strict_object("ParserOutput", PARSER_FIELDS))
REPAIR_OUTPUT_SCHEMA = root_schema(
    strict_object(
        "RepairOutput",
        {
            "diagnosis": {"type": "string"},
            "baseRevision": {"type": "integer", "minimum": 1},
            "changes": strict_object(
                "ArtifactChanges", {name: nullable(schema) for name, schema in PARSER_FIELDS.items()}
            ),
        },
    )
)

SAMPLE_CONFIRM_OUTPUT_SCHEMA = root_schema(
    strict_object(
        "SampleConfirmationOutput",
        {"reason": {"type": "string"}, "samplePy": {"type": "string"}},
    )
)
