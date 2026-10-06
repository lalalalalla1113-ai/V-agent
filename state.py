"""Глобальное состояние приложения."""

from datetime import datetime
from typing import Optional

from services.models import Message, Project, StyleType
from services import storage


class AppState:
    """Хранит текущий открытый проект и выбранный стиль генерации."""

    def __init__(self) -> None:
        self.current_project: Optional[Project] = None
        self.current_style: StyleType = "simple"

    def new_project(self) -> Project:
        """Создаёт новый пустой проект и делает его текущим."""
        project = storage.create_project()
        self.current_project = project
        return project

    def load_project(self, project_id: str) -> Optional[Project]:
        """Загружает проект по id и делает его текущим."""
        project = storage.load_project(project_id)
        if project is not None:
            self.current_project = project
        return project

    def append_message(self, message: Message) -> None:
        """Добавляет сообщение в текущий проект и сохраняет проект на диск.

        Если у проекта ещё нет "настоящего" названия (первое сообщение
        пользователя), название формируется из первых 30 символов текста.
        """
        if self.current_project is None:
            self.new_project()

        project = self.current_project
        is_first_user_message = (
            message.role == "user" and len(project.messages) == 0
        )

        project.messages.append(message)
        project.updated_at = datetime.now().isoformat()

        if is_first_user_message:
            project.title = message.text.strip()[:30] or "Новый проект"

        storage.save_project(project)

    def set_style(self, style: StyleType) -> None:
        """Меняет текущий выбранный стиль генерации."""
        self.current_style = style


# Единый экземпляр состояния на всё приложение
state = AppState()
