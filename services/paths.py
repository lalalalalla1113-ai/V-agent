"""Единое место, где решается, куда писать данные и откуда читать ресурсы.

Запуск из исходников:  <папка проекта>/ContentFarm
Android/iOS:           папка, которую даёт система (FLET_APP_STORAGE_DATA)
Запуск из .exe:        %APPDATA%/V-AGENT   (Windows)
                       ~/Library/Application Support/V-AGENT   (macOS)
                       ~/.local/share/V-AGENT   (Linux)

ВАЖНО: все пользовательские данные (профиль, ключи Cloudflare, Telegram-боты,
история чатов, картинки, напоминания) хранятся ТОЛЬКО локально на устройстве
пользователя и НИКОГДА не должны попадать в git-репозиторий.

Переменная окружения VAGENT_DATA_DIR переопределяет папку данных.
"""

import os
import sys
from pathlib import Path

APP_NAME = "V-AGENT"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Папка, где лежит assets/ (в .exe это временная распаковка)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", project_root()))
    return project_root()


def data_dir() -> Path:
    override = os.environ.get("VAGENT_DATA_DIR")
    mobile = os.environ.get("FLET_APP_STORAGE_DATA")  # Android / iOS сборка Flet

    if override:
        p = Path(override)
    elif mobile:
        p = Path(mobile) / "V-AGENT"
    elif is_frozen():
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
        p = base / APP_NAME
    else:
        # Из исходников — тоже в системную папку, чтобы данные НЕ попадали
        # в git-репозиторий проекта
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
        p = base / APP_NAME

    p.mkdir(parents=True, exist_ok=True)
    return p
