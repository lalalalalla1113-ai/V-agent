"""Чат с ИИ через Cloudflare Workers AI."""

import json
import os
import threading
from datetime import datetime, date
from typing import Optional

import flet as ft

from services import paths
from services import text_provider
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


def _chat_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "ai_chat.json")


def _load_history() -> list:
    p = _chat_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(items: list) -> None:
    try:
        with open(_chat_path(), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print(f"[AI CHAT] save error: {ex}")


def _fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return f"{dt.hour}:{dt.minute:02d}"
    except Exception:
        return ""


def _fmt_date_header(d: date) -> str:
    today = date.today()
    delta = (today - d).days
    if delta == 0:
        return "Сегодня"
    if delta == 1:
        return "Вчера"
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    if d.year == today.year:
        return f"{d.day} {months[d.month - 1]}"
    return f"{d.day} {months[d.month - 1]} {d.year}"


class AiChatScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.history: list = _load_history()
        self.is_generating = False
        self._bg_effect = None
        self._thinking_widget = None
        self._stopped = False

        self.input_field = ft.TextField(
            hint_text="Напиши сообщение...",
            multiline=True, min_lines=1, max_lines=6,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=theme.RADIUS, border_color=theme.SURFACE, expand=True,
        )

        self.send_btn = ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD_ROUNDED,
            icon_color=ft.Colors.WHITE,
            bgcolor=theme.PRIMARY,
            on_click=self._handle_send,
        )

        self.messages_list = ft.ListView(
            expand=True, spacing=10, auto_scroll=True,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
        )

        self._prev_keyboard_handler = None
        self._render()

    def build(self) -> ft.Stack:
        profile = get_current()
        effect_key = (profile.bg_effect if profile else "snow") or "snow"
        count_scale = float(profile.bg_count_scale) if profile else 1.0
        size_scale = float(profile.bg_size_scale) if profile else 1.0

        try:
            ww = int(self.page.window.width or self.page.width or 1920)
            wh = int(self.page.window.height or self.page.height or 1080)
        except Exception:
            ww, wh = 1920, 1080

        self._bg_effect = create_effect(
            effect_key, self.page,
            width=ww, height=wh,
            count_scale=count_scale,
            size_scale=size_scale,
        )
        bg_layer = self._bg_effect.build()
        self._bg_effect.start()

        self._install_keyboard()

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                            size=22, color=theme.PRIMARY),
                    ft.Text("Чат с ИИ", size=18,
                            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    ft.TextButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED,
                                        size=16, color=theme.TEXT_SECONDARY),
                                ft.Text("Очистить", size=12,
                                        color=theme.TEXT_SECONDARY),
                            ],
                            spacing=6, tight=True,
                        ),
                        on_click=self._clear_history,
                    ),
                ],
                spacing=10, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
        )

        input_row = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[self.input_field, self.send_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Text(
                        "Enter — отправить, Shift+Enter — новая строка",
                        size=10, color=theme.TEXT_SECONDARY,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
        )

        content_col = ft.Column(
            controls=[header, self.messages_list, input_row],
            spacing=0, expand=True,
        )

        main_layer = ft.Container(
            content=content_col,
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.6, theme.BG_DARK),
        )

        return ft.Container(
            content=ft.Stack(
                controls=[bg_layer, main_layer],
                expand=True,
            ),
            expand=True,
        )

    def _install_keyboard(self) -> None:
        self._prev_keyboard_handler = getattr(self.page, "on_keyboard_event", None)

        def on_key(e: ft.KeyboardEvent) -> None:
            if self._stopped:
                return
            if e.key == "Enter":
                if e.shift:
                    cur = self.input_field.value or ""
                    self.input_field.value = cur + "\n"
                    try:
                        self.input_field.update()
                    except Exception:
                        pass
                    return
                self._handle_send(None)

        self.page.on_keyboard_event = on_key

    def stop_effect(self) -> None:
        """Полная остановка — при уходе с экрана."""
        self._stopped = True
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None

        # Возвращаем прежний обработчик клавиатуры
        prev = self._prev_keyboard_handler
        self._prev_keyboard_handler = None
        try:
            if prev is not None:
                self.page.on_keyboard_event = prev
            else:
                self.page.on_keyboard_event = None
        except Exception:
            pass

    def _render(self) -> None:
        from ui.message_bubble import set_dynamic_width
        try:
            set_dynamic_width(self.page)
        except Exception:
            pass

        self.messages_list.controls.clear()
        if not self.history:
            self.messages_list.controls.append(self._empty_state())
        else:
            last_date = None
            for item in self.history:
                ts = item.get("timestamp")
                msg_date = None
                if ts:
                    try:
                        msg_date = datetime.fromisoformat(ts).date()
                    except Exception:
                        msg_date = None
                if msg_date is not None and msg_date != last_date:
                    self.messages_list.controls.append(
                        self._date_divider(_fmt_date_header(msg_date))
                    )
                    last_date = msg_date
                if item.get("role") == "user":
                    self.messages_list.controls.append(self._user_bubble(item))
                else:
                    self.messages_list.controls.append(self._ai_bubble(item))
        try:
            self.page.update()
        except Exception:
            pass

    def _empty_state(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=56,
                            color=ft.Colors.with_opacity(0.25, theme.TEXT_SECONDARY)),
                    ft.Container(height=12),
                    ft.Text("Задай любой вопрос — ИИ ответит",
                            size=15, color=theme.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0,
            ),
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(vertical=60), expand=True,
        )

    def _date_divider(self, text: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(text, size=11,
                                        color=theme.TEXT_SECONDARY,
                                        weight=ft.FontWeight.BOLD),
                        padding=ft.padding.symmetric(horizontal=12, vertical=4),
                        bgcolor=ft.Colors.with_opacity(0.5, theme.SURFACE),
                        border_radius=10,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=8),
        )

    def _user_bubble(self, item: dict) -> ft.Container:
        from ui.message_bubble import _dynamic_width  # noqa
        try:
            width = _dynamic_width
        except Exception:
            width = 380

        time_str = _fmt_time(item.get("timestamp", ""))
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(item.get("text", ""), size=14,
                                        color=ft.Colors.WHITE,
                                        selectable=True, no_wrap=False),
                                ft.Container(
                                    content=ft.Text(time_str, size=10,
                                                    color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE)),
                                    alignment=ft.alignment.bottom_right,
                                    padding=ft.padding.only(top=4),
                                ) if time_str else ft.Container(height=0),
                            ],
                            spacing=0, tight=True,
                        ),
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        bgcolor=theme.USER_BUBBLE, border_radius=theme.RADIUS,
                        width=width,
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            margin=ft.margin.only(left=20),
        )

    def _ai_bubble(self, item: dict) -> ft.Container:
        from ui.message_bubble import _dynamic_width  # noqa
        try:
            width = _dynamic_width
        except Exception:
            width = 380

        time_str = _fmt_time(item.get("timestamp", ""))
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(item.get("text", ""), size=14,
                                        color=theme.TEXT_PRIMARY,
                                        selectable=True, no_wrap=False),
                                ft.Container(
                                    content=ft.Text(time_str, size=10,
                                                    color=theme.TEXT_SECONDARY),
                                    alignment=ft.alignment.bottom_right,
                                    padding=ft.padding.only(top=6),
                                ) if time_str else ft.Container(height=0),
                            ],
                            spacing=0, tight=True,
                        ),
                        padding=ft.padding.all(14),
                        bgcolor=theme.AI_BUBBLE, border_radius=theme.RADIUS,
                        width=width,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            margin=ft.margin.only(right=20),
        )

    def _make_thinking_bubble(self) -> ft.Container:
        thinking_text = ft.Text("ИИ думает", size=14,
                                color=theme.TEXT_SECONDARY,
                                italic=True)
        self._thinking_widget = thinking_text
        return ft.Container(
            content=ft.Container(
                content=thinking_text,
                bgcolor=theme.AI_BUBBLE, border_radius=theme.RADIUS,
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
            ),
            alignment=ft.alignment.center_left,
            margin=ft.margin.only(right=60, top=4, bottom=4),
        )

    def _handle_send(self, e) -> None:
        if self.is_generating or self._stopped:
            return
        text = (self.input_field.value or "").strip()
        if not text:
            return

        now = datetime.now().isoformat()
        self.history.append({"role": "user", "text": text, "timestamp": now})
        _save_history(self.history)

        self.input_field.value = ""
        try:
            self.input_field.update()
        except Exception:
            pass
        self._render()

        thinking = self._make_thinking_bubble()
        self.messages_list.controls.append(thinking)
        try:
            self.page.update()
        except Exception:
            pass

        self.is_generating = True

        def _worker():
            context_lines = []
            for h in self.history[-8:]:
                role = "User" if h["role"] == "user" else "Assistant"
                context_lines.append(f"{role}: {h['text']}")
            context = "\n".join(context_lines)

            reply = text_provider.ask(
                context,
                system="Ты — полезный ассистент. Отвечай кратко и по делу, на русском языке.",
                max_tokens=800,
            )
            if not reply:
                reply = "❌ Не удалось получить ответ. Проверь ключ Cloudflare в Настройках."

            def _done():
                if self._stopped:
                    return
                try:
                    if thinking in self.messages_list.controls:
                        self.messages_list.controls.remove(thinking)
                except Exception:
                    pass

                self.history.append({
                    "role": "assistant",
                    "text": reply,
                    "timestamp": datetime.now().isoformat(),
                })
                _save_history(self.history)
                self.is_generating = False
                self._render()

            threading.Timer(0, _done).start()

        threading.Thread(target=_worker, daemon=True).start()

    def _clear_history(self, e) -> None:
        self.history = []
        _save_history(self.history)
        self._render()