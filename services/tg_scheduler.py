"""Планировщик публикаций в Telegram."""

import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Optional

from services import paths, telegram, text_ai


WEEKDAYS = [
    (0, "Понедельник"),
    (1, "Вторник"),
    (2, "Среда"),
    (3, "Четверг"),
    (4, "Пятница"),
    (5, "Суббота"),
    (6, "Воскресенье"),
]

WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

CHECK_INTERVAL_SEC = 30
SEND_WINDOW_MIN = 5
MAX_HISTORY = 500


_global_scheduler: Optional["TgScheduler"] = None


def get_global() -> Optional["TgScheduler"]:
    return _global_scheduler


def set_global(scheduler: "TgScheduler") -> None:
    global _global_scheduler
    _global_scheduler = scheduler


# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------

def _schedule_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "tg_schedule.json")


def _history_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "tg_history.json")


# ---------------------------------------------------------------------------
# Слоты
# ---------------------------------------------------------------------------

def load_slots() -> list:
    p = _schedule_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_slots(slots: list) -> None:
    try:
        with open(_schedule_path(), "w", encoding="utf-8") as f:
            json.dump(slots, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print(f"[TG SCHEDULE] save error: {ex}")


def make_slot(
    weekday: int,
    time_str: str,
    topic: str,
    style: str = "simple",
    add_hashtags: bool = False,
    auto_add: bool = True,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "weekday": int(weekday),
        "time": time_str,
        "topic": topic.strip(),
        "style": style,
        "add_hashtags": bool(add_hashtags),
        "auto_add": bool(auto_add),
        "enabled": True,
        "last_sent_date": "",
    }


# ---------------------------------------------------------------------------
# История
# ---------------------------------------------------------------------------

def load_history() -> list:
    p = _history_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            items = json.load(f)
        if not isinstance(items, list):
            return []
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return items
    except Exception:
        return []


def _append_history(item: dict) -> None:
    p = _history_path()
    items = []
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                items = json.load(f)
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []
    items.append(item)
    if len(items) > MAX_HISTORY:
        items = items[-MAX_HISTORY:]
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print(f"[TG SCHEDULER] history write error: {ex}")


def clear_history() -> None:
    p = _history_path()
    if os.path.exists(p):
        try:
            os.remove(p)
        except Exception as ex:
            print(f"[TG SCHEDULER] history clear error: {ex}")


# ---------------------------------------------------------------------------
# Планировщик
# ---------------------------------------------------------------------------

class TgScheduler:
    def __init__(self, page=None) -> None:
        self.page = page
        self.alive = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.alive:
            return
        self.alive = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[TG SCHEDULER] started")

    def stop(self) -> None:
        self.alive = False
        print("[TG SCHEDULER] stopped")

    def _loop(self) -> None:
        while self.alive:
            try:
                self._check_and_send()
            except Exception as ex:
                print(f"[TG SCHEDULER] error: {ex}")
            for _ in range(CHECK_INTERVAL_SEC):
                if not self.alive:
                    return
                time.sleep(1)

    def _check_and_send(self) -> None:
        slots = load_slots()
        if not slots:
            return

        now = datetime.now()
        today_key = now.strftime("%Y-%m-%d")
        current_weekday = now.weekday()
        changed = False

        for slot in slots:
            if not slot.get("enabled", True):
                continue
            if int(slot.get("weekday", -1)) != current_weekday:
                continue
            if slot.get("last_sent_date") == today_key:
                continue

            slot_time = slot.get("time", "")
            try:
                hh, mm = slot_time.split(":")
                target = now.replace(hour=int(hh), minute=int(mm),
                                     second=0, microsecond=0)
            except Exception:
                continue

            delta_min = (now - target).total_seconds() / 60.0
            if delta_min < 0 or delta_min > SEND_WINDOW_MIN:
                continue

            print(f"[TG SCHEDULER] отправляю слот: {slot.get('topic', '')}")
            ok = self._publish_slot(slot)
            if ok:
                slot["last_sent_date"] = today_key
                changed = True

        if changed:
            save_slots(slots)

    def _publish_slot(self, slot: dict) -> bool:
        profile = None
        bot = None

        try:
            from services.user_profile import get_current
            profile = get_current()
            if not profile:
                print("[TG SCHEDULER] нет профиля")
                self._log_fail(slot, "", "", "Нет профиля пользователя")
                return False

            bot = profile.get_active_bot()
            if not bot:
                print("[TG SCHEDULER] нет активного бота")
                self._log_fail(slot, "", "", "Нет активного бота")
                return False

            topic = (slot.get("topic") or "").strip()
            if not topic:
                self._log_fail(slot, bot, "", "Пустая тема поста")
                return False

            style = slot.get("style", "simple")
            add_tags = bool(slot.get("add_hashtags", False))
            auto_add = bool(slot.get("auto_add", True))

            samples = []
            try:
                samples = profile.get_bot_samples(bot.get("id"))
            except Exception as ex:
                print(f"[TG SCHEDULER] samples error: {ex}")

            print(f"[TG SCHEDULER] генерирую текст "
                  f"(стиль={style}, auto_add={auto_add})...")
            variants = text_ai.generate_content(
                idea=topic,
                style=style,
                history=None,
                profile=profile,
                samples=samples,
                auto_add=auto_add,
            )
            text = variants[0] if variants else ""
            if not text:
                print("[TG SCHEDULER] пустой текст от ИИ")
                self._log_fail(slot, bot, "", "ИИ вернул пустой текст")
                return False

            # ИИ отказался из-за нехватки информации
            if text.strip().startswith("❌ Недостаточно информации"):
                print("[TG SCHEDULER] ИИ: недостаточно информации")
                self._log_fail(slot, bot, text,
                               "ИИ: недостаточно информации в теме")
                return False

            print(f"[TG SCHEDULER] текст получен ({len(text)} симв.)")

            if add_tags:
                try:
                    tags = text_ai.generate_hashtags(topic, style=style)
                    if tags:
                        text = f"{text}\n\n{tags}"
                        print("[TG SCHEDULER] хештеги добавлены")
                except Exception as ex:
                    print(f"[TG SCHEDULER] hashtags error: {ex}")

            print(f"[TG SCHEDULER] отправляю в канал "
                  f"{bot.get('channel', '')}...")
            ok, err = telegram.send_message(
                bot.get("token", ""),
                bot.get("channel", ""),
                text,
            )

            if ok:
                print("[TG SCHEDULER] ✅ отправлено OK")
                self._log_ok(slot, bot, text)
                return True
            else:
                print(f"[TG SCHEDULER] ❌ ошибка отправки: {err}")
                self._log_fail(slot, bot, text, err)
                return False

        except Exception as ex:
            import traceback
            print(f"[TG SCHEDULER] publish exception: {ex}")
            traceback.print_exc()
            self._log_fail(slot, bot, "", f"Исключение: {ex}")
            return False

    def _log_ok(self, slot: dict, bot: dict, text: str) -> None:
        try:
            _append_history({
                "timestamp": datetime.now().isoformat(),
                "bot_id": bot.get("id", "") if bot else "",
                "bot_username": bot.get("username", "") if bot else "",
                "channel": bot.get("channel", "") if bot else "",
                "topic": slot.get("topic", ""),
                "style": slot.get("style", "simple"),
                "text": text,
                "status": "ok",
                "error": "",
            })
        except Exception as ex:
            print(f"[TG SCHEDULER] history save error: {ex}")

    def _log_fail(self, slot: dict, bot, text: str, error: str) -> None:
        try:
            bot_id = ""
            bot_username = ""
            channel = ""
            if isinstance(bot, dict):
                bot_id = bot.get("id", "")
                bot_username = bot.get("username", "")
                channel = bot.get("channel", "")
            elif bot is None:
                try:
                    from services.user_profile import get_current
                    p = get_current()
                    if p:
                        b = p.get_active_bot()
                        if b:
                            bot_id = b.get("id", "")
                            bot_username = b.get("username", "")
                            channel = b.get("channel", "")
                except Exception:
                    pass

            _append_history({
                "timestamp": datetime.now().isoformat(),
                "bot_id": bot_id,
                "bot_username": bot_username,
                "channel": channel,
                "topic": slot.get("topic", ""),
                "style": slot.get("style", "simple"),
                "text": text,
                "status": "fail",
                "error": error or "Неизвестная ошибка",
            })
        except Exception as ex:
            print(f"[TG SCHEDULER] history save error: {ex}")

    def publish_now(self, slot: dict) -> bool:
        return self._publish_slot(slot)