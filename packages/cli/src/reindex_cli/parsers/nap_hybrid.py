from __future__ import annotations

import re
from functools import lru_cache

MAX_TOKENS = 700


def split_markdown_section(text: str) -> list[str]:
    tokenizer = _tokenizer()
    blocks = [value.strip() for value in re.split(r"\n\s*\n", text) if value.strip()]
    chunks, pending, size = [], [], 0
    for block in blocks:
        for unit in _fit(block, tokenizer):
            count = _count(unit, tokenizer)
            if pending and size + count > MAX_TOKENS:
                chunks.append("\n\n".join(pending))
                pending, size = [], 0
            pending.append(unit)
            size += count
    if pending:
        chunks.append("\n\n".join(pending))
    return chunks or [text]


def _fit(text: str, tokenizer) -> list[str]:
    if _count(text, tokenizer) <= MAX_TOKENS:
        return [text]
    sentences = [value.strip() for value in re.split(r"(?<=[.!?])\s+", text) if value.strip()]
    if len(sentences) == 1:
        sentences = [value.strip() for value in re.split(r"(?<=[,;:])\s+", text) if value.strip()]
    result, pending = [], []
    for sentence in sentences:
        if _count(sentence, tokenizer) > MAX_TOKENS:
            words = sentence.split()
            for index in range(0, len(words), 120):
                result.extend(_fit(" ".join(words[index : index + 120]), tokenizer))
            continue
        candidate = " ".join([*pending, sentence])
        if pending and _count(candidate, tokenizer) > MAX_TOKENS:
            result.append(" ".join(pending))
            pending = [sentence]
        else:
            pending.append(sentence)
    if pending:
        result.append(" ".join(pending))
    return result


def _count(text: str, tokenizer) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))


@lru_cache(maxsize=1)
def _tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained("Qwen/Qwen3-Embedding-0.6B", local_files_only=True)
