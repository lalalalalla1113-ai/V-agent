"""Единое место, где решается, куда писать данные и откуда читать ресурсы.

ВАЖНО:
  Данные пользователя (профиль, ключи Cloudflare, боты Telegram,
  история чатов, картинки, напоминания) хранятся ТОЛЬКО на устройстве
  пользователя, ВНЕ папки проекта. В git они никогда не попадают.

Пути:
  Windows:   %APPDATA%\\V-AGENT
  macOS:     ~/Library/Application Support/V-AGENT
  Linux:     ~/.local/share/V-AGENT   (или $XDG_DATA_HOME/V-AGENT)
  Android:   <FLET_APP_STORAGE_DATA>/V-AGENT
  iOS:       <FLET_APP_STORAGE_DATA>/V-AGENT

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
    """Папка, где лежит assets/ (только для чтения)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", project_root()))
    return project_root()


def _system_data_base() -> Path:
    """Системная папка для данных приложения."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA")
                    or (Path.home() / "AppData" / "Roaming"))
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME")
                or (Path.home() / ".local" / "share"))


def data_dir() -> Path:
    """Возвращает папку для пользовательских данных.

    ВСЕГДА вне папки проекта, чтобы данные НЕ попадали в git.
    """
    override = os.environ.get("VAGENT_DATA_DIR")
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p

    mobile = os.environ.get("FLET_APP_STORAGE_DATA")
    if mobile:
        p = Path(mobile) / APP_NAME
        p.mkdir(parents=True, exist_ok=True)
        return p

    p = _system_data_base() / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p
