"""Точка входа приложения V-AGENT."""

import os
import sys


def _setup_logging() -> None:
    """Логи в системную папку пользователя, а не в проект."""
    try:
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
        pass


_setup_logging()


import flet as ft  # noqa: E402

from app import main  # noqa: E402


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
