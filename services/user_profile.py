"""Профиль пользователя.

ВАЖНО: все файлы профиля (включая cf_token, cf_account, tg_bots)
хранятся ТОЛЬКО в папке data_dir() — вне репозитория проекта.
"""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from services import paths


def _content_dir() -> str:
    base_dir = str(paths.data_dir())
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def _profile_path() -> str:
    return os.path.join(_content_dir(), "user_profile.json")


def get_avatar_path() -> str:
    return os.path.join(_content_dir(), "avatar.png")


@dataclass
class UserProfile:
    name: str = ""
    age: int = 0
    gender: str = ""
    interests: list = field(default_factory=list)
    audience: str = ""
    avatar_sticker: str = ""
    created_at: str = ""
    cf_token: str = ""
    cf_account: str = ""

    tg_bots: list = field(default_factory=list)
    tg_active_id: str = ""

    tg_vpn_hint_hidden: bool = False
    tg_vpn_hint_shown: bool = False

    bg_effect: str = "snow"
    bg_count_scale: float = 1.0
    bg_size_scale: float = 1.0
    gen_animation: str = "orbit"
    ui_theme: str = "dark_purple"

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        try:
            self.bg_count_scale = float(self.bg_count_scale)
        except Exception:
            self.bg_count_scale = 1.0
        try:
            self.bg_size_scale = float(self.bg_size_scale)
        except Exception:
            self.bg_size_scale = 1.0
        self.bg_count_scale = max(0.2, min(3.0, self.bg_count_scale))
        self.bg_size_scale = max(0.5, min(2.0, self.bg_size_scale))
        if not isinstance(self.tg_bots, list):
            self.tg_bots = []
        if not self.ui_theme:
            self.ui_theme = "dark_purple"

    # ---------- Telegram ----------

    def get_active_bot(self) -> Optional[dict]:
        if not self.tg_bots:
            return None
        if self.tg_active_id:
            for bot in self.tg_bots:
                if bot.get("id") == self.tg_active_id:
                    return bot
        return self.tg_bots[0]

    def add_bot(self, token: str, channel: str, name: str = "",
                username: str = "") -> dict:
        bot = {
            "id": str(uuid.uuid4()),
            "token": token.strip(),
            "channel": channel.strip(),
            "name": name.strip() or "Бот",
            "username": username.strip(),
            "samples": [],
        }
        self.tg_bots.append(bot)
        self.tg_active_id = bot["id"]
        return bot

    def remove_bot(self, bot_id: str) -> None:
        self.tg_bots = [b for b in self.tg_bots if b.get("id") != bot_id]
        if self.tg_active_id == bot_id:
            self.tg_active_id = self.tg_bots[0]["id"] if self.tg_bots else ""

    def set_active_bot(self, bot_id: str) -> None:
        for bot in self.tg_bots:
            if bot.get("id") == bot_id:
                self.tg_active_id = bot_id
                return

    def update_bot(self, bot_id: str, token: str, channel: str,
                   name: str = "", username: str = "") -> None:
        for bot in self.tg_bots:
            if bot.get("id") == bot_id:
                bot["token"] = token.strip()
                bot["channel"] = channel.strip()
                if name:
                    bot["name"] = name.strip()
                if username:
                    bot["username"] = username.strip()
                return

    # ---------- Примеры постов ----------

    def get_bot_samples(self, bot_id: Optional[str] = None) -> list:
        if bot_id is None:
            bot = self.get_active_bot()
        else:
            bot = None
            for b in self.tg_bots:
                if b.get("id") == bot_id:
                    bot = b
                    break
        if not bot:
            return []
        samples = bot.get("samples", [])
        if not isinstance(samples, list):
            return []
        return samples

    def set_bot_samples(self, samples: list, bot_id: Optional[str] = None) -> None:
        if bot_id is None:
            bot = self.get_active_bot()
        else:
            bot = None
            for b in self.tg_bots:
                if b.get("id") == bot_id:
                    bot = b
                    break
        if bot is not None:
            bot["samples"] = list(samples or [])

    # ---------- Сериализация ----------

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "UserProfile":
        return UserProfile(
            name=data.get("name", ""),
            age=int(data.get("age", 0)),
            gender=data.get("gender", ""),
            interests=list(data.get("interests", [])),
            audience=data.get("audience", ""),
            avatar_sticker=data.get("avatar_sticker", ""),
            created_at=data.get("created_at", ""),
            cf_token=data.get("cf_token", ""),
            cf_account=data.get("cf_account", ""),
            tg_bots=list(data.get("tg_bots", [])),
            tg_active_id=data.get("tg_active_id", ""),
            tg_vpn_hint_hidden=bool(data.get("tg_vpn_hint_hidden", False)),
            tg_vpn_hint_shown=bool(data.get("tg_vpn_hint_shown", False)),
            bg_effect=data.get("bg_effect", "snow"),
            bg_count_scale=float(data.get("bg_count_scale", 1.0)),
            bg_size_scale=float(data.get("bg_size_scale", 1.0)),
            gen_animation=data.get("gen_animation", "orbit"),
            ui_theme=data.get("ui_theme", "dark_purple"),
        )

    def save(self) -> None:
        with open(_profile_path(), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load() -> Optional["UserProfile"]:
        path = _profile_path()
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return UserProfile.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def exists() -> bool:
        return os.path.exists(_profile_path())

    @staticmethod
    def delete() -> None:
        path = _profile_path()
        if os.path.exists(path):
            os.remove(path)
        av = get_avatar_path()
        if os.path.exists(av):
            os.remove(av)

    def has_photo_avatar(self) -> bool:
        return os.path.exists(get_avatar_path())

    def days_since_registration(self) -> int:
        if not self.created_at:
            return 1
        try:
            dt = datetime.fromisoformat(self.created_at)
            delta = datetime.now() - dt
            return max(1, delta.days + 1)
        except Exception:
            return 1


current_profile: Optional[UserProfile] = None


def get_current() -> Optional[UserProfile]:
    return current_profile


def set_current(profile: Optional[UserProfile]) -> None:
    global current_profile
    current_profile = profile
