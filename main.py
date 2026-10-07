"""Точка входа приложения V-AGENT."""

import os
import sys
import random

# Логирование ДО импорта flet, чтобы поймать ошибки инициализации
try:
    _log_dir = os.environ.get("FLET_APP_STORAGE_DATA") or "."
    try:
        os.makedirs(_log_dir, exist_ok=True)
    except Exception:
        pass
    _log_path = os.path.join(_log_dir, "app.log")
    _log_file = open(_log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file
    print(">>> LOG STARTED")
except Exception:
    pass


import flet as ft  # noqa: E402

from app import main  # noqa: E402


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
