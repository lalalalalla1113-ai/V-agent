"""Точка входа приложения V-AGENT."""

import os
import sys


# ============================================================================
# Логирование ДО импорта flet — чтобы поймать ошибки инициализации.
# Логи пишутся в СИСТЕМНУЮ папку пользователя, а не в проект.
# ============================================================================

def _setup_logging() -> None:
    """Перенаправляет stdout/stderr в лог-файл в папке данных пользователя."""
    try:
        # Пытаемся определить папку данных без импорта services.paths
        # (чтобы не тащить зависимости до инициализации flet)
        log_dir = os.environ.get("FLET_APP_STORAGE_DATA")
        if not log_dir:
            if sys.platform == "win32":
                base = os.environ.get("APPDATA") or os.path.expanduser(
                    "~\\AppData\\Roaming"
                )
            elif sys.platform == "darwin":
                base = os.path.expanduser("~/Library/Application Support")
            else:
                base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
                    "~/.local/share"
                )
            log_dir = os.path.join(base, "V-AGENT")

        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "app.log")

        # Обрезаем лог, если стал больше 5 МБ
        try:
            if os.path.exists(log_path) and os.path.getsize(log_path) > 5_000_000:
                os.remove(log_path)
        except Exception:
            pass

        f = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = f
        sys.stderr = f
        print(">>> LOG STARTED")
    except Exception:
        # Если не удалось открыть файл — работаем молча
        pass


_setup_logging()


import random  # noqa: E402

import flet as ft  # noqa: E402

from app import main  # noqa: E402


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
