from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from reindex_cli.errors import ReIndexError
from reindex_cli.package.cards import parse_card
from reindex_cli.util import sha256_file


def build_push_archives(context) -> tuple[Path, Path, tempfile.TemporaryDirectory]:
    temporary = tempfile.TemporaryDirectory(prefix="rei-push-")
    root = Path(temporary.name)
    package_zip = root / "package.zip"
    source_zip = root / "sources.zip"
    with zipfile.ZipFile(package_zip, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(context.output_dir.rglob("*")):
            if file.is_file():
                relative = Path(context.output_dir.name) / file.relative_to(
                    context.output_dir
                )
                bundle.write(file, relative.as_posix())
    references = raw_references(context.output_dir)
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as bundle:
        for relative, expected in sorted(references.items()):
            source = context.root / relative
            if not source.is_file() or sha256_file(source) != expected:
                temporary.cleanup()
                raise ReIndexError(f"Missing or changed source: {relative}")
            bundle.write(source, relative)
    return package_zip, source_zip, temporary


def raw_references(package: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for card_path in package.rglob("*.node.md"):
        metadata, _body = parse_card(card_path)
        values = [
            metadata.get("source"),
            metadata.get("content"),
            *metadata.get("assets", []),
        ]
        for value in values:
            if not isinstance(value, dict):
                continue
            uri = str(value.get("uri", ""))
            if not uri.startswith("raw://"):
                continue
            relative = _safe(uri.removeprefix("raw://"))
            digest = str(value.get("sha256", ""))
            if relative in result and result[relative] != digest:
                raise ReIndexError(f"Conflicting source hashes: {relative}")
            result[relative] = digest
    return result


def extract_node_archive(content: bytes, target: Path) -> int:
    target.mkdir(parents=True, exist_ok=True)
    archive_path = target / ".download.zip"
    archive_path.write_bytes(content)
    count = 0
    try:
        with zipfile.ZipFile(archive_path) as bundle:
            names: set[str] = set()
            for item in bundle.infolist():
                path = PurePosixPath(item.filename)
                if (
                    item.filename in names
                    or path.is_absolute()
                    or ".." in path.parts
                    or not item.filename.endswith(".node.md")
                    or (item.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise ReIndexError(
                        f"Unsafe or non-Node pull entry: {item.filename}"
                    )
                names.add(item.filename)
                if item.is_dir():
                    continue
                destination = target.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(bundle.read(item))
                parse_card(destination)
                count += 1
    finally:
        archive_path.unlink(missing_ok=True)
    if not (target / "index.node.md").is_file():
        raise ReIndexError("Pulled Node tree has no root index.node.md")
    return count


def _safe(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ReIndexError(f"Unsafe raw path: {value}")
    return path.as_posix()
