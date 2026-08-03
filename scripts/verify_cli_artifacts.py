from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SKILLS = ("reindex-create", "reindex-data", "reindex-scan")


class ArtifactError(RuntimeError):
    """Raised when a built CLI distribution is incomplete or unusable."""


def inspect_wheel(wheel: Path, expected_version: str) -> None:
    if not wheel.is_file():
        raise ArtifactError(f"Wheel does not exist: {wheel}")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        if "reindex/__init__.py" not in names:
            raise ArtifactError("Wheel is missing the public reindex Python package")
        for skill in SKILLS:
            expected = f"reindex_cli/bundled_skills/{skill}/SKILL.md"
            if expected not in names:
                raise ArtifactError(f"Wheel is missing bundled skill: {expected}")
        metadata_names = [
            name for name in names if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ArtifactError("Wheel must contain exactly one METADATA file")
        metadata = archive.read(metadata_names[0]).decode("utf-8")
    if f"Version: {expected_version}\n" not in metadata:
        raise ArtifactError(
            f"Wheel metadata does not report version {expected_version}"
        )


def smoke_install(wheel: Path, expected_version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="reindex-release-") as temp:
        root = Path(temp)
        environment = root / "venv"
        run(["uv", "venv", "--python", sys.executable, str(environment)])
        python = environment / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        scripts = python.parent
        run(["uv", "pip", "install", "--python", str(python), str(wheel)])
        api_version = run(
            [str(python), "-c", "import reindex; print(reindex.__version__)"],
            capture=True,
        ).strip()
        if api_version != expected_version:
            raise ArtifactError(
                f"reindex.__version__ returned {api_version!r}, expected {expected_version!r}"
            )
        for command in ("rei",):
            executable = scripts / (
                f"{command}.exe" if sys.platform == "win32" else command
            )
            version_output = run([str(executable), "--version"], capture=True).strip()
            if version_output != expected_version:
                raise ArtifactError(
                    f"{command} --version returned {version_output!r}, expected {expected_version!r}"
                )
            run([str(executable), "--help"], capture=True)
        collection = root / "collection"
        collection.mkdir()
        output = run(
            [
                str(scripts / ("rei.exe" if sys.platform == "win32" else "rei")),
                "init",
                str(collection),
                "--name",
                "release-smoke",
                "--agent",
                "codex",
                "--codex-home",
                str(root / "codex-home"),
            ],
            capture=True,
        )
        result = json.loads(output)
        if result.get("status") != "ready" or len(result.get("skills", [])) != 6:
            raise ArtifactError(
                "Installed wheel failed the init and bundled-skills smoke test"
            )


def run(command: list[str], *, capture: bool = False) -> str:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a built reindex wheel.")
    parser.add_argument("wheel", type=Path)
    parser.add_argument("version")
    args = parser.parse_args()
    try:
        inspect_wheel(args.wheel, args.version)
        smoke_install(args.wheel.resolve(), args.version)
    except (ArtifactError, OSError, subprocess.CalledProcessError) as error:
        print(f"Artifact verification failed: {error}", file=sys.stderr)
        return 1
    print(f"Verified installable reindex {args.version}: {args.wheel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
