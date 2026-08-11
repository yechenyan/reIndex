"""Add selected NAP PDF-to-Markdown inputs to an existing Collection."""

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
    parser.add_argument("--prefixes", default="abcde")
    args = parser.parse_args()
    source, target = args.source.resolve(), args.target.resolve()
    manifest_path = target / "reIndex.md"
    manifest = _manifest(manifest_path)
    items = manifest.setdefault("items", {})
    selected = [
        path
        for path in sorted(source.iterdir())
        if path.is_dir() and path.name[:1].lower() in args.prefixes.lower()
    ]
    for operator in selected:
        pdf = _one(operator.glob("*.pdf"), operator, "PDF")
        output = _output(operator)
        pdf_target = target / "nap-pdf" / pdf.name
        markdown_name = ".nap-markdown.md" if operator.name == "allgaeunetz" else f".nap-markdown-{operator.name}.md"
        markdown_target = target / markdown_name
        _link_or_copy(pdf, pdf_target)
        _link_or_copy(output, markdown_target)
        pdf_key = pdf_target.relative_to(target).as_posix()
        markdown_key = markdown_target.relative_to(target).as_posix()
        items[pdf_key] = {"parse": {"text": "off", "images": "off", "tables": "off"}}
        items[markdown_key] = {
            "derived_from": pdf_key,
            "title": pdf.stem.replace("_", " ").replace("pdf", "PDF"),
        }
    manifest_path.write_text(
        "---\n" + yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False).rstrip() + "\n---\n",
        encoding="utf-8",
        newline="\n",
    )
    print({"operators": len(selected), "items": len(items)})


def _manifest(path: Path) -> dict:
    parts = path.read_text(encoding="utf-8").split("---", 2)
    if len(parts) != 3:
        raise SystemExit(f"Invalid manifest: {path}")
    value = yaml.safe_load(parts[1])
    if not isinstance(value, dict) or value.get("spec") != "reindex/input@1.0":
        raise SystemExit(f"Invalid manifest: {path}")
    return value


def _one(values, directory: Path, label: str) -> Path:
    result = list(values)
    if len(result) != 1:
        raise SystemExit(f"Expected one {label} in {directory}")
    return result[0]


def _output(directory: Path) -> Path:
    values = sorted(directory.glob("*/output.md"))
    if not values:
        raise SystemExit(f"No Markdown output in {directory}")
    return next((path for path in values if path.parent.name.endswith("-run")), values[0])


def _link_or_copy(source: Path, target: Path) -> None:
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


if __name__ == "__main__":
    main()
