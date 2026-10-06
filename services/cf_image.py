"""Генерация картинок через Cloudflare Workers AI.

Модель: @cf/black-forest-labs/flux-1-schnell
"""

import base64
import time
from typing import Optional, Tuple

import requests

from services import cf_config, image_providers


CF_IMAGE_URL = (
    "https://api.cloudflare.com/client/v4/accounts/"
    "{account}/ai/run/@cf/black-forest-labs/flux-1-schnell"
)

TIMEOUT = 120
RETRIES = 2
RETRY_DELAY = 5


def generate_cf_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
) -> Tuple[Optional[bytes], str]:
    """Генерирует картинку через Cloudflare.

    Возвращает (bytes, "") при успехе или (None, "причина") при ошибке.
    """
    account, token = cf_config.get_cf_credentials()
    if not account or not token:
        return None, (cf_config.last_error or "Ключ Cloudflare не задан")

    url = CF_IMAGE_URL.format(account=account)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "prompt": prompt,
        "steps": 4,
    }

    last_error = "Cloudflare недоступен"

    for attempt in range(1, RETRIES + 1):
        try:
            r = image_providers._post_with_fallback(
                url, headers=headers, json=payload, timeout=TIMEOUT,
            )

            if r.status_code == 200:
                data = r.json()
                result = data.get("result") or {}
                img_b64 = result.get("image")
                if img_b64:
                    try:
                        img_bytes = base64.b64decode(img_b64)
                        print(f"[CF IMAGE] OK ({len(img_bytes)} bytes)")
                        return img_bytes, ""
                    except Exception as ex:
                        print(f"[CF IMAGE] base64 decode error: {ex}")
                        return None, "Ошибка декодирования картинки"
                else:
                    print(f"[CF IMAGE] нет поля image: {data}")
                    return None, "Cloudflare вернул пустой ответ"

            if r.status_code == 401:
                return None, "Токен Cloudflare неверный"
            if r.status_code == 403:
                return None, "Нет прав на Workers AI"
            if r.status_code == 429:
                return None, "Лимит Cloudflare исчерпан. Попробуй позже"

            print(f"[CF IMAGE] {r.status_code}: {r.text[:150]}")
            last_error = f"Cloudflare вернул {r.status_code}"
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY)
                continue

        except requests.exceptions.Timeout:
            print(f"[CF IMAGE] таймаут (попытка {attempt})")
            last_error = "Cloudflare не ответил вовремя"
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY)

        except requests.exceptions.SSLError as ex:
            print(f"[CF IMAGE] SSL ошибка: {ex}")
            last_error = "SSL ошибка Cloudflare"
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY)

        except Exception as ex:
            print(f"[CF IMAGE] ошибка: {ex}")
            last_error = f"Ошибка Cloudflare: {ex}"
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY)

    return None, last_error