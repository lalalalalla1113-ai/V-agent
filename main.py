"""Точка входа приложения V-AGENT."""

import sys

from services import paths

# В .exe без консоли stdout/stderr отсутствуют — пишем в лог-файл,
# чтобы print() не падал и было что смотреть при ошибках.
if paths.is_frozen():
    try:
        _log = paths.data_dir() / "app.log"
        if _log.exists() and _log.stat().st_size > 1_000_000:
            _log.unlink()
        sys.stdout = sys.stderr = open(_log, "a", encoding="utf-8", buffering=1)
    except Exception:
        pass

import flet as ft  # noqa: E402

from app import main  # noqa: E402


if __name__ == "__main__":
    import random
    ft.app(
        target=main,
        assets_dir=str(paths.resource_dir() / "assets"),
        port=random.randint(20000, 40000),
    )
