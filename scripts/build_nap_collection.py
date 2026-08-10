"""Create a ReIndex input Collection from NAP PDF-to-Markdown runs."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--source-name", default="nap-pdf")
    args = parser.parse_args()
    source, target = args.source.resolve(), args.target.resolve()
    if target.exists():
        unexpected = [path for path in target.iterdir() if path.name not in {".rei", "reIndex"}]
        if unexpected:
            raise SystemExit(f"Target is not an empty Collection: {target}")
    else:
        target.mkdir(parents=True)
    items: dict[str, dict] = {}
    single_document = bool(list(source.glob("*.pdf")))
    operators = [source] if single_document else sorted(
        path for path in source.iterdir() if path.is_dir()
    )
    for operator in operators:
        pdfs = sorted(operator.glob("*.pdf"))
        outputs = sorted(operator.glob("*/output.md"))
        if len(pdfs) != 1 or not outputs:
            raise SystemExit(f"Expected one PDF and an output.md: {operator}")
        output = next(
            (path for path in outputs if path.parent.name.endswith("-run")), outputs[0]
        )
        if single_document:
            pdf_target = target / args.source_name / pdfs[0].name
            markdown_target = target / ".nap-markdown.md"
        else:
            pdf_target = target / "sources" / operator.name / pdfs[0].name
            markdown_target = target / "documents" / operator.name / output.parent.name / "output.md"
        _link_or_copy(pdfs[0], pdf_target)
        _link_or_copy(output, markdown_target)
        pdf_key = pdf_target.relative_to(target).as_posix()
        markdown_key = markdown_target.relative_to(target).as_posix()
        items[pdf_key] = {"parse": {"text": "off", "images": "off", "tables": "off"}}
        items[markdown_key] = {
            "derived_from": pdf_key,
            "title": pdfs[0].stem.replace("_", " ").replace("pdf", "PDF"),
        }
    manifest = {
        "spec": "reindex/input@1.0",
        "collection": {
            "title": "NAP PDF",
            "description": "Netzausbauplan PDFs with Markdown-derived text and tables.",
        },
        "items": items,
    }
    target.joinpath("reIndex.md").write_text(
        "---\n" + yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False).rstrip() + "\n---\n",
        encoding="utf-8",
        newline="\n",
    )


def _link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


if __name__ == "__main__":
    main()
