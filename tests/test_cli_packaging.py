from __future__ import annotations

import sys
from importlib.metadata import metadata
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import release_pypi
from reindex_cli import __version__


def test_runtime_and_project_versions_match() -> None:
    project = tomllib.loads(release_pypi.PYPROJECT.read_text(encoding="utf-8"))[
        "project"
    ]
    assert __version__ == project["version"]
    assert metadata("reindex")["Version"] == project["version"]


def test_public_python_package() -> None:
    import reindex

    assert reindex.__version__ == __version__
    assert reindex.ApiClient.__name__ == "ApiClient"


def test_release_version_bumps() -> None:
    assert release_pypi.bump_version("1.2.3", "patch") == "1.2.4"
    assert release_pypi.bump_version("1.2.3", "minor") == "1.3.0"
    assert release_pypi.bump_version("1.2.3", "major") == "2.0.0"
    assert release_pypi.bump_version("1.2.3", "4.5.6") == "4.5.6"


def test_release_version_replacement_is_scoped() -> None:
    original = '[project]\nversion = "1.2.3"\nname = "example"\n'
    updated = release_pypi.replace_version(original, "1.2.4")
    assert updated == '[project]\nversion = "1.2.4"\nname = "example"\n'
