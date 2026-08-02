from __future__ import annotations

import json
import os
from pathlib import Path

from reindex_cli.util import atomic_json

DEFAULT_API_URL = "http://127.0.0.1:8000"


def config_dir() -> Path:
    if value := os.getenv("REINDEX_CONFIG_HOME"):
        return Path(value).expanduser().resolve()
    base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base.expanduser().resolve() / "reindex"


def cache_dir() -> Path:
    if value := os.getenv("REINDEX_CACHE_HOME"):
        return Path(value).expanduser().resolve()
    base = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base.expanduser().resolve() / "reindex"


def get_api_url(explicit: str | None = None) -> str:
    if explicit:
        return normalize_url(explicit)
    if value := os.getenv("REINDEX_API_URL"):
        return normalize_url(value)
    path = config_dir() / "config.json"
    if path.is_file():
        value = json.loads(path.read_text(encoding="utf-8")).get("api_url")
        if isinstance(value, str) and value.strip():
            return normalize_url(value)
    return DEFAULT_API_URL


def set_api_url(value: str) -> str:
    url = normalize_url(value)
    atomic_json(config_dir() / "config.json", {"api_url": url})
    return url


def normalize_url(value: str) -> str:
    result = value.strip().rstrip("/")
    if not result.startswith(("http://", "https://")):
        raise ValueError("API URL must start with http:// or https://")
    return result
