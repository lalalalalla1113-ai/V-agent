"""Реальное хранение проектов в локальных JSON-файлах."""

import json
import os
import uuid
from datetime import datetime
from typing import Optional

from services import paths
from services.models import Project


def get_projects_dir() -> str:
    """Возвращает путь к папке с проектами, создавая её при отсутствии."""
    projects_dir = str(paths.data_dir() / "projects")
    os.makedirs(projects_dir, exist_ok=True)
    return projects_dir


def _project_path(project_id: str) -> str:
    """Путь к файлу конкретного проекта."""
    return os.path.join(get_projects_dir(), f"{project_id}.json")


def list_projects() -> list:
    """Возвращает список всех проектов, отсортированный по updated_at."""
    projects_dir = get_projects_dir()
    projects: list = []

    for filename in os.listdir(projects_dir):
        if not filename.endswith(".json"):
            continue
        project_id = filename[:-len(".json")]
        project = load_project(project_id)
        if project is not None:
            projects.append(project)

    projects.sort(key=lambda p: p.updated_at, reverse=True)
    return projects


def load_project(project_id: str) -> Optional[Project]:
    """Загружает проект по id. Возвращает None при ошибке."""
    path = _project_path(project_id)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Project.from_dict(data)
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def save_project(project: Project) -> None:
    """Сохраняет проект в файл {project_id}.json."""
    path = _project_path(project.id)
    paths.atomic_write_json(path, project.to_dict())


def delete_project(project_id: str) -> None:
    """Удаляет файл проекта, если он существует."""
    path = _project_path(project_id)
    if os.path.exists(path):
        os.remove(path)


def create_project(first_message_text: str = "",
                   tab_id: str = "chat") -> Project:
    """Создаёт новый проект с названием из первых 30 символов текста.

    tab_id — вкладка, в которой создан проект (chat/image/hashtags/...).
    """
    now = datetime.now().isoformat()
    title = first_message_text.strip()[:30] or "Новый проект"

    project = Project(
        id=str(uuid.uuid4()),
        title=title,
        created_at=now,
        updated_at=now,
        messages=[],
        tab_id=tab_id,
    )
    save_project(project)
    return project