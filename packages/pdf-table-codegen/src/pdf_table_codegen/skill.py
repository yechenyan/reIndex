from __future__ import annotations

import hashlib
import shutil
from importlib.resources import as_file, files
from pathlib import Path


def bundled_skill_path():
    return files("pdf_table_codegen").joinpath("bundled_skill", "pdf-table-codegen")


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def install_skill(workspace: Path, *, force: bool = False) -> tuple[Path, str]:
    target = workspace.resolve() / ".agents" / "skills" / "pdf-table-codegen"
    with as_file(bundled_skill_path()) as source:
        if target.exists():
            if _tree_digest(source) == _tree_digest(target):
                return target, "unchanged"
            if not force:
                raise FileExistsError(f"skill has local changes: {target}")
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    return target, "installed"
