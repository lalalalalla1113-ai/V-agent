"""Отправка сообщений в Telegram через Bot API.

Порядок отправки:
  1. Пробуем с parse_mode="HTML" (для поддержки <b>, <i>, <blockquote> и т.д.).
  2. Если Telegram вернул ошибку разметки — отправляем БЕЗ тегов.
  3. Если и это не помогло — возвращаем понятную ошибку.

Все ошибки логируются в консоль, чтобы было видно, что пошло не так.
"""

import re
from typing import Optional, Tuple

import requests

from services import image_providers


TG_API = "https://api.telegram.org/bot{token}/{method}"

MAX_MESSAGE_LEN = 4096


# ===========================================================================
# Утилиты
# ===========================================================================

_HTML_TAG_RE = re.compile(
    r"</?(?:b|i|u|s|code|pre|blockquote|tg-spoiler|tg-emoji)"
    r"(?:\s[^>]*)?>",
    re.IGNORECASE,
)


def strip_html(text: str) -> str:
    """Убирает HTML-теги Telegram, оставляя только содержимое."""
    if not text:
        return ""
    clean = _HTML_TAG_RE.sub("", text)
    clean = clean.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return clean


def is_parse_error(err: str) -> bool:
    """Проверяет, что ошибка связана с разметкой."""
    e = (err or "").lower()
    return (
        "can't parse entities" in e
        or "can't find end" in e
        or "unsupported start tag" in e
        or "unsupported start tag" in e
        or ("invalid" in e and "parse" in e)
    )


# ===========================================================================
# Обработка ошибок
# ===========================================================================

def _friendly_error(err: str, status: int) -> str:
    e = (err or "").lower()

    if "chat not found" in e:
        return ("Канал не найден. Проверь:\n"
                "• ID канала (для канала начинается с -100...)\n"
                "• Бот добавлен в канал\n"
                "• Бот — администратор")
    if "not enough rights" in e or "have no rights" in e:
        return ("У бота нет прав публиковать в канал. Добавь бота в админы "
                "и дай право «Публикация сообщений».")
    if "bot was blocked" in e:
        return "Бот заблокирован пользователем."
    if "bot is not a member" in e or "user is not a member" in e:
        return "Бот не добавлен в канал."
    if "forbidden" in e:
        return ("403 Forbidden.\n"
                "Бот не админ канала или канал запрещает публикацию.\n"
                "Решение: добавь бота в администраторы канала.")
    if "chat_id is empty" in e:
        return "ID канала пустой."
    if "message is too long" in e:
        return "Пост слишком длинный. Telegram: 4096 символов."
    if "too many requests" in e:
        return "Слишком много запросов. Подожди минуту."
    if "unauthorized" in e or status == 401:
        return "Неверный токен бота. Скопируй из @BotFather."
    if is_parse_error(err):
        return "Ошибка разметки поста."

    return err or f"Ошибка {status}"


# ===========================================================================
# Отправка
# ===========================================================================

def _send_raw(token: str, channel: str, text: str,
               parse_mode: str = "") -> Tuple[bool, str]:
    """Одна попытка отправки. Возвращает (ok, err)."""
    url = TG_API.format(token=token.strip(), method="sendMessage")

    payload = {
        "chat_id": channel.strip(),
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        r = image_providers._post_with_fallback(url, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if data.get("ok"):
                return True, ""
            err = data.get("description", "")
            return False, err
        try:
            data = r.json()
            err = data.get("description", "")
        except Exception:
            err = ""
        return False, err or f"HTTP {r.status_code}"
    except requests.exceptions.Timeout:
        return False, "Превышено время ожидания."
    except requests.exceptions.SSLError:
        return False, "SSL ошибка соединения."
    except requests.exceptions.ConnectionError:
        return False, "Нет связи с Telegram."
    except Exception as ex:
        return False, f"Ошибка: {ex}"


def send_message(token, channel, text, parse_mode="HTML"):
    """Отправляет сообщение в канал.

    parse_mode="HTML" — по умолчанию.
    Если Telegram не может распарсить разметку — отправляем без тегов.
    """
    if not token or not token.strip():
        return False, "Токен бота не задан"
    if not channel or not channel.strip():
        return False, "ID канала не задан"
    if not text or not text.strip():
        return False, "Пустой текст"

    # Обрезаем до лимита Telegram
    if len(text) > MAX_MESSAGE_LEN:
        text = text[:MAX_MESSAGE_LEN - 3] + "..."

    # 1. Пробуем с HTML
    if parse_mode:
        ok, err = _send_raw(token, channel, text, parse_mode=parse_mode)
        if ok:
            print(f"[TG] отправлено с HTML ({len(text)} симв.)")
            return True, ""
        if not is_parse_error(err):
            print(f"[TG] ошибка НЕ про разметку: {err}")
            return False, _friendly_error(err, 0)
        print(f"[TG] ошибка разметки, пробую без тегов: {err}")

    # 2. Fallback — без тегов
    plain = strip_html(text)
    print(f"[TG] fallback: {len(plain)} симв. без тегов")
    ok, err = _send_raw(token, channel, plain, parse_mode="")
    if ok:
        print(f"[TG] отправлено без тегов")
        return True, ""
    print(f"[TG] fallback тоже упал: {err}")
    return False, _friendly_error(err, 0)


# ===========================================================================
# Проверка подключения
# ===========================================================================

def get_bot_info(token):
    """Возвращает (ok, bot_dict, err)."""
    if not token or not token.strip():
        return False, {}, "Токен не задан"

    url = TG_API.format(token=token.strip(), method="getMe")

    try:
        r = image_providers._get_with_fallback(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("ok"):
                return True, data.get("result", {}), ""
        try:
            data = r.json()
            err = data.get("description", "")
        except Exception:
            err = ""
        return False, {}, _friendly_error(err, r.status_code)
    except Exception as ex:
        return False, {}, f"Ошибка: {ex}"


def test_connection(token, channel):
    """Проверяет токен + отправляет тестовое сообщение в канал.

    Возвращает (ok, msg, bot_dict).
    """
    ok, bot, err = get_bot_info(token)
    if not ok:
        return False, err, {}

    ok2, err2 = send_message(
        token, channel,
        "✅ <b>V-AGENT подключён</b> к этому каналу.\n"
        "Здесь будут появляться ваши посты.",
    )
    if not ok2:
        return False, err2, bot

    first_name = bot.get("first_name", "")
    username = bot.get("username", "")
    msg = f"Бот {first_name} (@{username}) подключён к каналу"
    return True, msg, bot