from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .sample_contract import normalize_sample_rows


FORBIDDEN = ("parse.py", "review.json", "finaltable.json", "sampleconfirmation.json")


def load_sample(table_dir: Path) -> tuple[list[str], dict]:
    path = table_dir / "sample.py"
    if not path.is_file():
        return ["sample.py is missing"], {}
    return load_sample_path(path, table_dir)


def load_sample_source(table_dir: Path, source: str) -> tuple[list[str], dict]:
    table_dir.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".py", prefix="sample-candidate-",
        dir=table_dir, delete=False,
    )
    path = Path(handle.name)
    try:
        with handle:
            handle.write(source)
        return load_sample_path(path, table_dir)
    finally:
        path.unlink(missing_ok=True)


def load_sample_path(path: Path, table_dir: Path) -> tuple[list[str], dict]:
    source = path.read_text(encoding="utf-8", errors="replace").lower()
    errors = [f"sample.py contains forbidden reference: {name}" for name in FORBIDDEN if name in source]
    if errors:
        return errors, {}
    completed = subprocess.run(
        [sys.executable, str(path), "--table-json", str(table_dir / "table.json")],
        cwd=table_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        return [f"sample.py exited {completed.returncode}: {completed.stderr[-1200:]}"], {}
    try:
        value = json.loads(completed.stdout)
    except Exception as exc:
        return [f"sample.py stdout is not one JSON object: {exc}; stdout={completed.stdout[-1200:]!r}"], {}
    if not isinstance(value, dict):
        return ["sample.py output must be a JSON object"], {}
    return [], normalize_sample_rows(value)
