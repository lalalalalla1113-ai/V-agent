"""Единое место, где решается, куда писать данные и откуда читать ресурсы."""

import json as _json
import os
import os as _os
import sys
import time
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
    mobile = os.environ.get("FLET_APP_STORAGE_DATA")
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
        p = project_root() / "ContentFarm"
    p.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write_json(path, data) -> None:
    """Атомарно пишет JSON с обходом блокировки файла."""
    path_str = str(path)
    tmp = path_str + ".tmp"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Пытаемся писать через временный файл (безопасно)
            with open(tmp, "w", encoding="utf-8") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)

            _os.replace(tmp, path_str)
            return  # Успех

        except PermissionError:
            if attempt == max_retries - 1:
                # Если временный файл заблокирован, пишем напрямую
                try:
                    with open(path_str, "w", encoding="utf-8") as f:
                        _json.dump(data, f, ensure_ascii=False, indent=2)
                    return
                except Exception as ex:
                    print(f"[PATHS] Критическая ошибка записи: {ex}")
                    raise
            time.sleep(0.05)

        except Exception as ex:
            print(f"[PATHS] Ошибка записи {path_str}: {ex}")
            raise