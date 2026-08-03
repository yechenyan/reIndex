#!/usr/bin/env python3
"""Start ParadeDB, the ReIndex API, and React for local development."""

from __future__ import annotations

import argparse
import signal
import subprocess
import time
import urllib.request

from dev_support import (
    ROOT,
    WEB,
    database_has_schema,
    development_environment,
    ensure_database,
    ensure_dependencies,
    run,
)


def wait_for_api(process: subprocess.Popen, timeout: int = 900) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("ReIndex API stopped during startup.")
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2):
                return
        except OSError:
            time.sleep(2)
    raise RuntimeError("ReIndex API did not become ready.")


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.terminate()


def start_api(env: dict[str, str]) -> subprocess.Popen:
    return subprocess.Popen(
        [
            "uv",
            "run",
            "--no-sync",
            "--package",
            "reindex-server",
            "reindex-server",
            "run",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=ROOT,
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    ensure_dependencies()
    ensure_database()
    env = development_environment()
    if not database_has_schema():
        run(
            [
                "uv",
                "run",
                "--no-sync",
                "--package",
                "reindex-server",
                "reindex-server",
                "init-db",
            ],
            env=env,
        )
    api = start_api(env)
    web = subprocess.Popen(["pnpm", "dev"], cwd=WEB)
    try:
        print("→ Loading Qwen embeddings; first run downloads the model.", flush=True)
        wait_for_api(api)
        print("\nReIndex local development is ready:", flush=True)
        print("  Web: http://127.0.0.1:5173/#/explore", flush=True)
        print("  API: http://127.0.0.1:8000/docs", flush=True)
        while api.poll() is None and web.poll() is None:
            time.sleep(1)
        return api.returncode or web.returncode or 1
    except KeyboardInterrupt:
        return 0
    finally:
        stop_process(web)
        stop_process(api)


if __name__ == "__main__":
    raise SystemExit(main())
