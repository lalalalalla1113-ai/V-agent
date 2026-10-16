"""Заглушка фильтра. Не фильтрует ничего."""

from typing import List, Tuple


def check_text(text: str) -> Tuple[bool, List[str]]:
    """Всегда пропускает текст."""
    return True, []


def forbidden_message(hits: List[str]) -> str:
    return ""