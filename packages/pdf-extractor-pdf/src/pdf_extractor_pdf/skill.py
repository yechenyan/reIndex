from __future__ import annotations

import hashlib
import shutil
from importlib.resources import as_file, files
from pathlib import Path


def bundled_skill_path() -> Path:
    return Path(str(files("pdf_extractor_pdf").joinpath("bundled_skill/pdf-extractor-pdf")))


def _digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def install_skill(workspace: Path, force: bool = False) -> tuple[Path, str]:
    target = workspace.resolve() / ".agents" / "skills" / "pdf-extractor-pdf"
    with as_file(files("pdf_extractor_pdf").joinpath("bundled_skill/pdf-extractor-pdf")) as source:
        source_path = Path(source)
        if target.exists() and _digest(target) == _digest(source_path):
            return target, "unchanged"
        if target.exists() and not force:
            raise FileExistsError(f"skill has local changes: {target}")
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_path, target)
    return target, "installed"
