from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from liteparse import LiteParse


def load_context() -> dict[str, Any]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    args = parser.parse_args()
    value = json.loads(Path(args.context).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Runtime context must be a JSON object")
    return value


def load_sample_args() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-json")
    parser.parse_args()


def liteparse_page(context: dict[str, Any], page_number: int) -> Any:
    result = LiteParse(
        ocr_enabled=False,
        target_pages=str(page_number),
        extract_blocks=True,
        emit_word_boxes=True,
        extract_vector_graphics=True,
        quiet=True,
    ).parse(context["pdfPath"])
    for page in result.pages:
        value = page.get("page_num") if isinstance(page, dict) else getattr(page, "page_num", None)
        if int(value) == int(page_number):
            return page
    raise ValueError(f"LiteParse did not return page {page_number}")


def emit_sample(sample: dict[str, Any]) -> None:
    print(json.dumps(sample, ensure_ascii=False, separators=(",", ":")))


def emit_table(rows: list[list[Any]]) -> None:
    print(json.dumps({"rows": rows}, ensure_ascii=False, separators=(",", ":")))
