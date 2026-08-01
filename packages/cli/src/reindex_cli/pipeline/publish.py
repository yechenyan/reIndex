from __future__ import annotations

import os
import shutil
from pathlib import Path

from reindex_cli.errors import ReIndexError


def publish(staging: Path, output: Path, state_root: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    backup = state_root / "staging" / "previous-package"
    if backup.exists():
        shutil.rmtree(backup)
    moved_previous = False
    try:
        if output.exists():
            os.replace(output, backup)
            moved_previous = True
        os.replace(staging, output)
    except OSError as error:
        if moved_previous and backup.exists() and not output.exists():
            os.replace(backup, output)
        raise ReIndexError(f"Could not publish package: {error}") from error
    if backup.exists():
        shutil.rmtree(backup)
