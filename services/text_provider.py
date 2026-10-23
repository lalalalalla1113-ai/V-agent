"""Единая точка входа для текстовых запросов.

Основной провайдер — Cloudflare Workers AI (Llama 3.1).
"""

from typing import Optional

from services import cf_text


def ask(
    prompt: str,
    system: str = "",
    max_tokens: int = 800,
) -> Optional[str]:
    """Спрашивает LLM. Возвращает текст или None."""
    result = cf_text.ask(prompt, system=system, max_tokens=max_tokens)
    return result