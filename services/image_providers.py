"""Провайдеры генерации картинок.

Основной — Cloudflare Workers AI (FLUX.1-schnell).
Резервный — Pollinations.AI.

Безопасность SSL:
  1. Сначала пробуем обычное соединение с проверкой сертификата.
  2. Если Kaspersky/VPN подменяет сертификат и соединение падает —
     автоматически переключаемся на ослабленный режим ТОЛЬКО для этого
     запроса. В лог пишется предупреждение.

Возвращает (bytes, "") при успехе или (None, "причина ошибки").
"""

import time
import urllib.parse
from typing import Optional, Tuple

import urllib3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ---------------------------------------------------------------------------
# SSL-контексты
# ---------------------------------------------------------------------------

class _StrictTLSAdapter(HTTPAdapter):
    """Обычный адаптер — с полной проверкой сертификата."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        # Проверка включена по умолчанию
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class _LooseTLSAdapter(HTTPAdapter):
    """Ослабленный адаптер — для Kaspersky/VPN, которые ломают сертификат."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = False
        try:
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except Exception:
            pass
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _make_session(loose: bool = False) -> requests.Session:
    """Создаёт сессию.

    loose=False (по умолчанию) — с полной проверкой SSL.
    loose=True  — ослабленный режим для проблемных сетей.
    """
    session = requests.Session()
    retry = Retry(
        total=2, backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    if loose:
        adapter = _LooseTLSAdapter(max_retries=retry)
        session.verify = False
        print("[SSL] Включён ослабленный режим (Kaspersky/VPN). "
              "Проверка сертификата отключена только для этого запроса.")
    else:
        adapter = _StrictTLSAdapter(max_retries=retry)
        session.verify = True
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _post_with_fallback(url: str, **kwargs) -> requests.Response:
    """POST с автоматическим fallback на ослабленный SSL."""
    try:
        session = _make_session(loose=False)
        return session.post(url, **kwargs)
    except requests.exceptions.SSLError as ex:
        print(f"[SSL] Ошибка проверки сертификата: {ex}")
        print("[SSL] Пробую ослабленный режим...")
        session = _make_session(loose=True)
        return session.post(url, **kwargs)


def _get_with_fallback(url: str, **kwargs) -> requests.Response:
    """GET с автоматическим fallback на ослабленный SSL."""
    try:
        session = _make_session(loose=False)
        return session.get(url, **kwargs)
    except requests.exceptions.SSLError as ex:
        print(f"[SSL] Ошибка проверки сертификата: {ex}")
        print("[SSL] Пробую ослабленный режим...")
        session = _make_session(loose=True)
        return session.get(url, **kwargs)


# ---------------------------------------------------------------------------
# Cloudflare
# ---------------------------------------------------------------------------

def generate_cloudflare(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
) -> Tuple[Optional[bytes], str]:
    """Обёртка над cf_image.generate_cf_image."""
    try:
        from services import cf_image
        result, err = cf_image.generate_cf_image(prompt, width, height)
        if result:
            return result, ""
        print(f"[CF IMAGE] ошибка: {err}")
        return None, err
    except Exception as ex:
        print(f"[CF IMAGE] исключение: {ex}")
        return None, f"Cloudflare: {ex}"


# ---------------------------------------------------------------------------
# Pollinations (резерв)
# ---------------------------------------------------------------------------

POLLINATIONS_IMAGE_URL = "https://image.pollinations.ai/prompt/"
POLLINATIONS_MODELS = ["flux", "turbo", "kontext"]


def generate_pollinations(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
) -> Tuple[Optional[bytes], str]:
    encoded = urllib.parse.quote(prompt, safe="")
    last_error = "Pollinations недоступен"

    for model in POLLINATIONS_MODELS:
        url = (
            f"{POLLINATIONS_IMAGE_URL}{encoded}"
            f"?width={width}&height={height}"
            f"&nologo=true&model={model}"
            f"&enhance=false"
            f"&seed={int(time.time())}"
        )
        for attempt in range(1, 3):
            try:
                response = _get_with_fallback(url, timeout=120)
                if response.status_code == 402:
                    last_error = "Бесплатный лимит исчерпан. Попробуй позже"
                    break
                if response.status_code in (500, 502, 503, 504):
                    last_error = f"Pollinations вернул {response.status_code}"
                    if attempt < 2:
                        time.sleep(3)
                        continue
                    break
                response.raise_for_status()
                print(f"[POLL] {model} OK")
                return response.content, ""
            except requests.exceptions.SSLError:
                last_error = "SSL-ошибка Pollinations"
                if attempt < 2:
                    time.sleep(3)
            except requests.exceptions.ConnectionError:
                last_error = "Нет связи с Pollinations"
                if attempt < 2:
                    time.sleep(3)
            except requests.exceptions.Timeout:
                last_error = "Pollinations не ответил вовремя"
                if attempt < 2:
                    time.sleep(3)
            except Exception as ex:
                last_error = f"Ошибка Pollinations: {ex}"
                if attempt < 2:
                    time.sleep(3)

    return None, last_error