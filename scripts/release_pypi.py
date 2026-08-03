from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "packages" / "cli" / "pyproject.toml"
LOCK = ROOT / "uv.lock"
DIST = ROOT / "dist" / "reindex"
DEFAULT_CONFIG = ROOT / "config" / "local.toml"
VERSION_RE = re.compile(r'(?m)^(version\s*=\s*")(\d+\.\d+\.\d+)(")$')
TESTS = [
    "tests/test_cli_packaging.py",
    "tests/test_cli_skills.py",
    "tests/test_cli.py",
    "tests/test_cli_workspace.py",
    "tests/test_cli_remote.py",
    "tests/test_cli_http_flow.py",
]


class ReleaseError(RuntimeError):
    """Raised when the release cannot continue safely."""


def bump_version(current: str, target: str) -> str:
    major, minor, patch = (int(part) for part in current.split("."))
    if target == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if target == "minor":
        return f"{major}.{minor + 1}.0"
    if target == "major":
        return f"{major + 1}.0.0"
    if re.fullmatch(r"\d+\.\d+\.\d+", target):
        return target
    raise ReleaseError("target must be patch, minor, major, or X.Y.Z")


def read_version(text: str) -> str:
    match = VERSION_RE.search(text)
    if match is None:
        raise ReleaseError(f"Missing static project version in {PYPROJECT}")
    return match.group(2)


def replace_version(text: str, version: str) -> str:
    updated, count = VERSION_RE.subn(rf"\g<1>{version}\g<3>", text, count=1)
    if count != 1:
        raise ReleaseError(f"Could not update version in {PYPROJECT}")
    return updated


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def require_clean_worktree() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    if result.stdout.strip():
        raise ReleaseError("Git worktree is not clean; commit or stash changes first")


def resolve_token(config_path: Path) -> str:
    for name in ("UV_PUBLISH_TOKEN", "PYPI_TOKEN"):
        if value := os.environ.get(name, "").strip():
            return value
    if config_path.is_file():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        token = data.get("pypi", {}).get("token", "")
        if isinstance(token, str) and token.strip():
            return token.strip()
    raise ReleaseError(
        "Missing token: set UV_PUBLISH_TOKEN/PYPI_TOKEN or [pypi].token in "
        f"{config_path}"
    )


def artifacts() -> tuple[list[Path], Path]:
    files = sorted(
        path
        for path in DIST.glob("*")
        if path.suffix == ".whl" or path.name.endswith(".tar.gz")
    )
    wheels = [path for path in files if path.suffix == ".whl"]
    if (
        len(files) != 2
        or len(wheels) != 1
        or not any(path.name.endswith(".tar.gz") for path in files)
    ):
        raise ReleaseError(f"Expected one wheel and one sdist in {DIST}")
    return files, wheels[0]


def release(args: argparse.Namespace, original: str) -> None:
    if not args.allow_dirty:
        require_clean_worktree()
    current = read_version(original)
    target = bump_version(current, args.target)
    if target != current:
        PYPROJECT.write_text(replace_version(original, target), encoding="utf-8")
        print(f"Bumped reindex: {current} -> {target}")
        run(["uv", "lock"])

    if not args.skip_lint:
        run(["uvx", "ruff", "check", "packages/cli", "scripts", *TESTS[:2]])
        run(["uvx", "ruff", "format", "--check", "packages/cli", "scripts", *TESTS[:2]])
    if not args.skip_test:
        run(["uv", "run", "pytest", "-q", *TESTS])
    if DIST.exists():
        shutil.rmtree(DIST)
    run(["uv", "build", "--package", "reindex", "--out-dir", str(DIST)])
    built, wheel = artifacts()
    run(["uvx", "twine", "check", *[str(path) for path in built]])
    run(["uv", "run", "python", "scripts/verify_cli_artifacts.py", str(wheel), target])

    if args.skip_publish:
        print(f"Release candidate ready: reindex {target}")
        return
    env = os.environ.copy()
    env["UV_PUBLISH_TOKEN"] = resolve_token(Path(args.config).expanduser())
    command = ["uv", "publish", *[str(path) for path in built]]
    if args.dry_run:
        command.append("--dry-run")
    if args.test_pypi:
        command.extend(["--publish-url", "https://test.pypi.org/legacy/"])
    run(command, env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bump, check, build, verify, and publish reindex."
    )
    parser.add_argument("target", help="patch, minor, major, or X.Y.Z")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-pypi", action="store_true")
    parser.add_argument("--skip-lint", action="store_true")
    parser.add_argument("--skip-test", action="store_true")
    parser.add_argument("--skip-publish", action="store_true")
    parser.add_argument("--keep-version-on-failure", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    original = PYPROJECT.read_text(encoding="utf-8")
    original_lock = LOCK.read_bytes()
    try:
        release(args, original)
    except (
        ReleaseError,
        OSError,
        subprocess.CalledProcessError,
        tomllib.TOMLDecodeError,
    ) as error:
        if (
            not args.keep_version_on_failure
            and PYPROJECT.read_text(encoding="utf-8") != original
        ):
            PYPROJECT.write_text(original, encoding="utf-8")
            print(f"Restored reindex {read_version(original)}", flush=True)
        if LOCK.read_bytes() != original_lock:
            LOCK.write_bytes(original_lock)
            print("Restored uv.lock", flush=True)
        print(f"Release failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
