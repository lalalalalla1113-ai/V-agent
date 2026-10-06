"""Текст через Cloudflare Workers AI.

Модель: @cf/meta/llama-3.1-8b-instruct
"""

import time
from typing import Optional

import requests

from services import cf_config, image_providers


CF_TEXT_URL = (
    "https://api.cloudflare.com/client/v4/accounts/"
    "{account}/ai/run/@cf/meta/llama-3.1-8b-instruct"
)

# Последняя причина неудачи (показывается пользователю)
last_error: str = ""

TIMEOUT = 90
RETRIES = 2
RETRY_DELAY = 5


def ask(
    prompt: str,
    system: str = "",
    max_tokens: int = 800,
) -> Optional[str]:
    """Спрашивает модель через Cloudflare.

    Возвращает текст ответа или None.
    """
    global last_error
    last_error = ""
    account, token = cf_config.get_cf_credentials()
    if not account or not token:
        last_error = cf_config.last_error or "Ключ Cloudflare не задан."
        return None

    url = CF_TEXT_URL.format(account=account)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
    }

    for attempt in range(1, RETRIES + 1):
        try:
            r = image_providers._post_with_fallback(
                url, headers=headers, json=payload, timeout=TIMEOUT,
            )

            if r.status_code == 200:
                data = r.json()
                result = data.get("result") or {}
                out = (result.get("response") or "").strip()
                if out:
                    print(f"[CF TEXT] OK ({len(out)} симв.)")
                    return out

            if r.status_code == 401:
                print("[CF TEXT] 401 — токен неверный")
                last_error = "Токен Cloudflare неверный или отозван."
                return None
            if r.status_code == 403:
                print("[CF TEXT] 403 — нет прав")
                last_error = "У токена нет прав на Workers AI (или Account ID от другого аккаунта)."
                return None
            if r.status_code == 429:
                print("[CF TEXT] 429 — лимит исчерпан")
                last_error = "Лимит Cloudflare исчерпан. Попробуй позже."
                return None

            print(f"[CF TEXT] {r.status_code}: {r.text[:150]}")
            last_error = f"Cloudflare вернул ошибку {r.status_code}."
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY)

        except requests.exceptions.Timeout:
            print(f"[CF TEXT] таймаут (попытка {attempt})")
            last_error = "Cloudflare не ответил вовремя."
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as ex:
            print(f"[CF TEXT] {ex}")
            last_error = "Нет связи с Cloudflare. Проверь интернет или VPN/прокси."
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY)

    return None