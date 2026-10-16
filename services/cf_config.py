"""Ключи Cloudflare Workers AI.

Работаем только по токену самого пользователя (вводится в онбординге
или в Настройках). Встроенных ключей в приложении нет.

Токен хранится ТОЛЬКО на устройстве пользователя, в файле профиля.
Автор программы его не видит и никуда не отправляет.

Account ID берётся из профиля (если пользователь вписал его вручную)
или определяется автоматически по токену (кэшируется).
"""

import re
from typing import Optional, Tuple

import requests

from services import image_providers


# Встроенных ключей нет: токен берётся только из профиля пользователя
DEFAULT_CF_ACCOUNT = ""
DEFAULT_CF_TOKEN = ""

# Кэш: токен -> account_id
_ACCOUNT_CACHE: dict = {}

CF_ACCOUNTS_URL = "https://api.cloudflare.com/client/v4/accounts"

# Последняя причина, почему нет доступа к Cloudflare (показывается пользователю)
last_error: str = ""

_NEED_ACCOUNT_MSG = (
    "Не удалось определить Account ID по токену. "
    "Впиши Account ID вручную: Настройки → Cloudflare ключ."
)


def parse_account_id(text: str) -> str:
    """Достаёт Account ID (32 символа 0-9a-f) из текста или ссылки на дашборд."""
    m = re.search(r"[0-9a-fA-F]{32}", text or "")
    return m.group(0).lower() if m else ""


def _get_account_by_token(token: str) -> Optional[str]:
    """Запрашивает у Cloudflare список аккаунтов по токену.
    Возвращает первый account_id или None (причина — в last_error).
    """
    global last_error
    if not token:
        return None
    if token in _ACCOUNT_CACHE:
        return _ACCOUNT_CACHE[token]

    try:
        r = image_providers._get_with_fallback(
            CF_ACCOUNTS_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[CF] accounts request {r.status_code}: {r.text[:120]}")
            if r.status_code in (400, 401, 403):
                last_error = _NEED_ACCOUNT_MSG
            else:
                last_error = f"Cloudflare вернул {r.status_code} при проверке токена."
            return None
        data = r.json()
        result = data.get("result") or []
        if not result:
            print("[CF] аккаунтов нет")
            last_error = _NEED_ACCOUNT_MSG
            return None
        account_id = result[0].get("id")
        if account_id:
            _ACCOUNT_CACHE[token] = account_id
            return account_id
        last_error = _NEED_ACCOUNT_MSG
    except Exception as ex:
        print(f"[CF] accounts error: {ex}")
        last_error = ("Нет связи с Cloudflare. Проверь интернет, "
                      "а если включён VPN или прокси, проверь, что он работает.")
    return None


def get_cf_credentials() -> Tuple[str, str]:
    """Возвращает (account_id, token).

    Берёт токен пользователя из профиля. Нет токена или Account ID —
    вернёт пустые строки, а причина будет в cf_config.last_error.
    """
    global last_error
    last_error = ""
    try:
        from services.user_profile import get_current
        profile = get_current()
        if profile and getattr(profile, "cf_token", "").strip():
            user_token = profile.cf_token.strip()
            user_account = parse_account_id(getattr(profile, "cf_account", "") or "")
            if not user_account:
                user_account = _get_account_by_token(user_token) or ""
            if user_account:
                return user_account, user_token
            if not last_error:
                last_error = _NEED_ACCOUNT_MSG
            return DEFAULT_CF_ACCOUNT, DEFAULT_CF_TOKEN
    except Exception as ex:
        print(f"[CF] credentials error: {ex}")

    last_error = "Ключ Cloudflare не задан. Добавь его в Настройках."
    return DEFAULT_CF_ACCOUNT, DEFAULT_CF_TOKEN


def has_user_token() -> bool:
    try:
        from services.user_profile import get_current
        p = get_current()
        return bool(p and getattr(p, "cf_token", "").strip())
    except Exception:
        return False