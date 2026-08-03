"""Infrastructure helpers for the local ReIndex development stack."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "packages" / "web-app"
CONTAINER = "reindex-paradedb"
DATABASE_VOLUME = "reindex-paradedb-pg18-data"
DATABASE_PORT = 55434
DATABASE_NAME = "reindex_local"
DATABASE_PASSWORD = "reindex_local"
DATABASE_URL = (
    f"postgresql://postgres:{DATABASE_PASSWORD}@127.0.0.1:"
    f"{DATABASE_PORT}/{DATABASE_NAME}"
)


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> None:
    print(f"→ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def output(command: list[str]) -> str:
    result = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def wait_for_docker(timeout: int = 180) -> None:
    if output(["docker", "info", "--format", "{{.ServerVersion}}"]):
        return
    if sys.platform == "darwin":
        print("→ Docker Desktop is not running; opening it now.", flush=True)
        subprocess.Popen(["open", "-a", "Docker"])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if output(["docker", "info", "--format", "{{.ServerVersion}}"]):
            return
        time.sleep(2)
    raise RuntimeError("Docker did not become ready. Start Docker Desktop and retry.")


def ensure_database() -> None:
    wait_for_docker()
    exists = output(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name=^{CONTAINER}$",
            "--format",
            "{{.Names}}",
        ]
    )
    if exists:
        run(["docker", "start", CONTAINER])
    else:
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                CONTAINER,
                "-e",
                f"POSTGRES_PASSWORD={DATABASE_PASSWORD}",
                "-e",
                f"POSTGRES_DB={DATABASE_NAME}",
                "-p",
                f"{DATABASE_PORT}:5432",
                "-v",
                f"{DATABASE_VOLUME}:/var/lib/postgresql",
                "paradedb/paradedb:0.24.3-pg18",
            ]
        )
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        ready = output(
            [
                "docker",
                "exec",
                CONTAINER,
                "pg_isready",
                "-U",
                "postgres",
                "-d",
                DATABASE_NAME,
            ]
        )
        if "accepting connections" in ready:
            return
        time.sleep(2)
    raise RuntimeError("ParadeDB did not become ready.")


def database_has_schema() -> bool:
    value = output(
        [
            "docker",
            "exec",
            CONTAINER,
            "psql",
            "-U",
            "postgres",
            "-d",
            DATABASE_NAME,
            "-Atqc",
            "select to_regclass('public.collections');",
        ]
    )
    return value == "collections"


def ensure_dependencies() -> None:
    if shutil.which("uv") is None or shutil.which("pnpm") is None:
        raise RuntimeError("Local development requires uv and pnpm on PATH.")
    python_ready = (
        subprocess.run(
            [
                "uv",
                "run",
                "--no-sync",
                "--package",
                "reindex-server",
                "python",
                "-c",
                "import reindex_server, sentence_transformers",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )
    if not python_ready:
        print(
            "→ Python dependencies are missing; installing workspace extras.",
            flush=True,
        )
        run(["uv", "sync", "--all-extras"])
    if not (WEB / "node_modules" / ".bin" / "vite").exists():
        print("→ Web dependencies are missing; installing them.", flush=True)
        run(["pnpm", "install", "--frozen-lockfile"], cwd=WEB)


def development_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": DATABASE_URL,
            "REINDEX_DATA_DIR": str(ROOT / ".reindex-data"),
            "REINDEX_EMBEDDINGS": "qwen",
            "REINDEX_RERANKER": "disabled",
        }
    )
    return env
