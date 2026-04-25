"""Small helpers for keeping agent-facing text English-only."""

from __future__ import annotations

from typing import Any


def contains_cjk(value: Any) -> bool:
    """Return whether text contains CJK characters."""

    return any("\u3400" <= char <= "\u9fff" for char in str(value))


def english_or(value: Any, fallback: str = "") -> str:
    """Return stripped text only when it is non-empty and CJK-free."""

    text = str(value or "").strip()
    if not text or contains_cjk(text):
        return fallback
    return text


def english_items(value: Any) -> list[str]:
    """Normalize a list to English-only strings."""

    if not isinstance(value, list):
        return []
    return [text for item in value if (text := english_or(item))]
