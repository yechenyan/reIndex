from __future__ import annotations

from importlib.resources import files
from typing import Any
import json


def load_prompt(name: str) -> str:
    return files("pdf_parse").joinpath("prompts", name).read_text(encoding="utf-8")


def compose(*parts: str, context: Any | None = None) -> str:
    values = [part.strip() for part in parts if part.strip()]
    prompt = "\n\n".join(values)
    if context is not None:
        payload = "## Runtime context\n```json\n" + json.dumps(
            context, ensure_ascii=False, separators=(",", ":")
        ) + "\n```"
        prompt = prompt.replace("{{RUNTIME_CONTEXT}}", payload)
        if "{{RUNTIME_CONTEXT}}" not in "\n\n".join(values):
            prompt += "\n\n" + payload
    return prompt + "\n"
