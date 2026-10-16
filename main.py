"""Точка входа приложения V-AGENT."""

import socket
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


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    p = s.getsockname()[1]
    s.close()
    return p


if __name__ == "__main__":
    ft.app(
        target=main,
        assets_dir=str(paths.resource_dir() / "assets"),
        port=_free_port(),
    )
