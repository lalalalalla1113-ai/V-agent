"""Проверка Premium-ключа через Cloudflare Worker.

Workers URL и логика:
  • Приложение отправляет POST с ключом.
  • Worker ищет ключ в KV.
  • Если найден → удаляет (ключ сгорает) → возвращает {valid: true, days: N}.
  • Если нет → {valid: false, error: "not_found"}.

ВАЖНО: код воркера и список ключей хранятся ТОЛЬКО у тебя в Cloudflare.
В этом файле — только URL. Его безопасно выкладывать на GitHub.
"""

from typing import Tuple

import requests


# ===========================================================================
# URL ТВОЕГО ВОРКЕРА
# ===========================================================================
# Меняешь, если пересоздашь воркер с другим именем.
# ===========================================================================

CHECK_URL = "https://vagent-premium.novalaim11.workers.dev"


# Таймаут запроса (секунды)
TIMEOUT = 20


def activate_premium_key(raw_key: str) -> Tuple[bool, int, str]:
    """Отправляет ключ на сервер и получает результат активации.

    Возвращает:
      (True, days, "")       — ключ валиден, активировано на days дней
      (False, 0, "причина")  — ключ невалиден / ошибка
    """
    key = (raw_key or "").strip().upper()

    if not key:
        return False, 0, "Введи ключ активации"

    try:
        r = requests.post(
            CHECK_URL,
            json={"key": key},
            timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
        )

        if r.status_code != 200:
            return False, 0, f"Ошибка сервера: {r.status_code}"

        try:
            data = r.json()
        except Exception:
            return False, 0, "Некорректный ответ сервера"

        if data.get("valid"):
            days = int(data.get("days", 30))
            return True, days, ""

        err = data.get("error", "")
        if err == "not_found":
            return False, 0, "Ключ недействителен или уже использован"
        if err == "empty":
            return False, 0, "Пустой ключ"
        return False, 0, "Ключ не принят"

    except requests.exceptions.Timeout:
        return False, 0, "Сервер не отвечает. Проверь интернет."
    except requests.exceptions.ConnectionError:
        return False, 0, "Нет связи с сервером. Проверь интернет."
    except Exception as ex:
        return False, 0, f"Ошибка: {ex}"