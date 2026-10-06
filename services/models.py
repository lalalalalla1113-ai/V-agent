"""Dataclass-модели данных приложения."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal, Optional

StyleType = Literal["complex", "simple", "anti_ai"]


@dataclass
class Message:
    """Одно сообщение в диалоге — от пользователя или от ИИ."""

    role: Literal["user", "assistant"]
    text: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    style: Optional[StyleType] = None
    attachments: list = field(default_factory=list)
    # Для ответов ИИ: список из 2 вариантов поста (может быть пустым)
    variants: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Message":
        return Message(
            role=data["role"],
            text=data["text"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            style=data.get("style"),
            attachments=data.get("attachments", []),
            variants=data.get("variants", []),
        )


@dataclass
class Project:
    """Проект — отдельный диалог со своей историей сообщений."""

    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list = field(default_factory=list)
    is_finished: bool = False
    chosen_style: Optional[StyleType] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "is_finished": self.is_finished,
            "chosen_style": self.chosen_style,
        }

    @staticmethod
    def from_dict(data: dict) -> "Project":
        return Project(
            id=data["id"],
            title=data["title"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            is_finished=data.get("is_finished", False),
            chosen_style=data.get("chosen_style"),
        )