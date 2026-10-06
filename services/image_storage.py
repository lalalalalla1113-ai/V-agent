"""Хранилище сгенерированных картинок.

Каждая картинка сохраняется в ContentFarm/images/.
Метаданные хранятся в ContentFarm/images.json.
"""

import json
import os
from services import paths
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


# ---------- Пути ----------

_THIS_FILE = os.path.abspath(__file__)
_SERVICES_DIR = os.path.dirname(_THIS_FILE)
_PROJECT_ROOT = os.path.dirname(_SERVICES_DIR)


def _content_dir() -> str:
    base_dir = str(paths.data_dir())
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def _images_dir() -> str:
    d = os.path.join(_content_dir(), "images")
    os.makedirs(d, exist_ok=True)
    return d


def _index_path() -> str:
    return os.path.join(_content_dir(), "images.json")


# ---------- Модель ----------

@dataclass
class GeneratedImage:
    """Одна сгенерированная картинка."""

    id: str
    prompt: str
    style_key: str
    filename: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "GeneratedImage":
        return GeneratedImage(
            id=data["id"],
            prompt=data["prompt"],
            style_key=data.get("style_key", "photo"),
            filename=data["filename"],
            created_at=data.get("created_at", ""),
        )

    def full_path(self) -> str:
        """Полный путь к файлу."""
        return os.path.join(_images_dir(), self.filename)


# ---------- Индекс (список картинок) ----------

def _load_index() -> list:
    path = _index_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [GeneratedImage.from_dict(item) for item in data]
    except (json.JSONDecodeError, OSError, KeyError):
        return []


def _save_index(items: list) -> None:
    path = _index_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump([i.to_dict() for i in items], f, ensure_ascii=False, indent=2)


# ---------- Публичные функции ----------

def save_image(image_bytes: bytes, prompt: str, style_key: str) -> Optional[GeneratedImage]:
    """Сохраняет картинку в файл и добавляет в индекс."""
    if not image_bytes:
        return None

    image_id = str(uuid.uuid4())
    filename = f"{image_id}.png"
    filepath = os.path.join(_images_dir(), filename)

    try:
        with open(filepath, "wb") as f:
            f.write(image_bytes)
    except OSError as ex:
        print(f"Ошибка сохранения картинки: {ex}")
        return None

    item = GeneratedImage(
        id=image_id,
        prompt=prompt,
        style_key=style_key,
        filename=filename,
    )

    items = _load_index()
    items.insert(0, item)   # новые — сверху
    _save_index(items)

    return item


def list_images() -> list:
    """Все сгенерированные картинки, свежие сверху."""
    items = _load_index()
    items.sort(key=lambda x: x.created_at, reverse=True)
    return items


def delete_image(image_id: str) -> bool:
    """Удаляет картинку и запись из индекса."""
    items = _load_index()
    found = None
    for item in items:
        if item.id == image_id:
            found = item
            break

    if not found:
        return False

    # Удаляем файл
    filepath = found.full_path()
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass

    # Убираем из индекса
    items = [i for i in items if i.id != image_id]
    _save_index(items)
    return True