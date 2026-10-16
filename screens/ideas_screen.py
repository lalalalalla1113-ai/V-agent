"""Экран «Идеи для постов» — генератор идей.

  • Сверху — шапка + Premium + Новый чат.
  • По центру — чат-лента с датами.
  • Внизу — быстрые темы, поле ввода, кнопка.

Enter — отправить, Shift+Enter — новая строка.
"""

import json
import os
import threading
import time
from datetime import datetime, date

import flet as ft

from services import paths, text_provider, text_ai
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect
from ui.message_bubble import render_telegram_html


_TYPING_PREFIX = "V-Agent"
_TYPING_SUFFIX = " - твой помощник с идеями"
_TYPING_SPEED = 0.07
_TYPING_DELETE_SPEED = 0.035
_TYPING_HOLD_SEC = 4.0
_TYPING_DELETE_HOLD = 0.5


QUICK_TOPICS = [
    "Утренние привычки",
    "Продуктивность",
    "Психология",
    "Здоровое питание",
    "Путешествия",
    "Финансы",
    "Отношения",
    "Саморазвитие",
]

IDEA_STYLES = [
    {"id": "universal", "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
     "title": "Универсальные", "subtitle": "Разные форматы",
     "color": "#9C27B0"},
    {"id": "story", "icon": ft.Icons.AUTO_STORIES_ROUNDED,
     "title": "Истории", "subtitle": "От первого лица",
     "color": "#2196F3"},
    {"id": "list", "icon": ft.Icons.FORMAT_LIST_BULLETED_ROUNDED,
     "title": "Списки", "subtitle": "5 способов, 7 ошибок",
     "color": "#4CAF50"},
    {"id": "question", "icon": ft.Icons.HELP_OUTLINE_ROUNDED,
     "title": "Вопросы", "subtitle": "С вопроса читателю",
     "color": "#00BCD4"},
    {"id": "provocation", "icon": ft.Icons.BOLT_ROUNDED,
     "title": "Провокации", "subtitle": "Резкие тезисы",
     "color": "#E53935"},
]


def _history_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "ideas_history.json")


def _load_history() -> list:
    p = _history_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(items: list) -> None:
    try:
        paths.atomic_write_json(_history_path(), items)
    except Exception as ex:
        print(f"[IDEAS] save error: {ex}")


def _is_mobile(page: ft.Page) -> bool:
    if os.environ.get("FLET_APP_STORAGE_DATA"):
        return True
    try:
        if page.platform in ("android", "ios"):
            return True
    except Exception:
        pass
    try:
        w = int(page.width or 0)
        return 0 < w < 700
    except Exception:
        return False


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


class IdeasScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.mobile = _is_mobile(page)
        self._bg_effect = None
        self._stopped = False

        self.current_style = "universal"
        self.is_generating = False
        self.history: list = _load_history()
        self.chat_messages: list = []

        self._typing_alive = False
        self._typing_text_widget = None
        self._typing_thread = None

        self.topic_field = ft.TextField(
            hint_text="Опиши тему — например: как перестать откладывать дела",
            multiline=True,
            min_lines=1,
            max_lines=3,
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=14,
            border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY,
            text_size=15,
            content_padding=ft.padding.all(14),
            expand=True,
            shift_enter=True,
            on_submit=self._handle_generate,
        )

        self.send_btn = ft.Container(
            content=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED,
                            size=20, color=ft.Colors.WHITE),
            width=48, height=48,
            bgcolor=theme.PRIMARY,
            border_radius=12,
            alignment=ft.alignment.center,
            on_click=self._handle_generate,
            ink=True,
            tooltip="Придумать идеи (Enter)",
        )

        self.status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

        self.styles_row = ft.Row(
            spacing=10, run_spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )
        self.quick_topics_row = ft.Row(
            spacing=8, run_spacing=8, wrap=True,
        )

        self.messages_list = ft.ListView(
            expand=True, spacing=2, auto_scroll=True,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
        )

        self._style_refs: dict = {}

        self._render_styles()
        self._render_quick_topics()
        self._render_chat()

    def stop_effect(self) -> None:
        self._stopped = True
        self._stop_typing_animation()
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None

    # ------------------------------------------------------------------
    # Premium + Новый чат
    # ------------------------------------------------------------------

    def _make_premium_button(self) -> ft.Container:
        try:
            from services.premium_guard import is_premium
            premium = is_premium()
        except Exception:
            premium = False

        if premium:
            color = "#4CAF50"
            text = "Premium ✓"
            tooltip = "Premium активен"
        else:
            color = "#FFD700"
            text = "Premium"
            tooltip = "Купить Premium"

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                            size=14, color=color),
                    ft.Text(text, size=11, color=color,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=4, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            bgcolor=ft.Colors.with_opacity(0.15, color),
            border=ft.border.all(1, ft.Colors.with_opacity(0.5, color)),
            border_radius=8,
            on_click=lambda e: self._open_subscription(),
            ink=True,
            tooltip=tooltip,
        )

    def _open_subscription(self) -> None:
        try:
            chat = getattr(self.page, "_vagent_chat_screen", None)
            if chat is not None:
                chat._handle_nav("subscription")
        except Exception as ex:
            print(f"[IDEAS] open subscription error: {ex}")

    def _make_new_chat_button(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=14,
                            color=ft.Colors.WHITE),
                    ft.Text("Новый чат", size=11,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=4, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
            bgcolor=theme.PRIMARY,
            on_click=self._handle_new_chat,
            ink=True,
            tooltip="Очистить и начать заново",
        )

    def _handle_new_chat(self, e) -> None:
        self._stop_typing_animation()
        self.chat_messages.clear()
        self.is_generating = False
        self.topic_field.value = ""
        try:
            self.topic_field.update()
        except Exception:
            pass
        self._render_chat()
        try:
            self.page.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Построение
    # ------------------------------------------------------------------

    def build(self) -> ft.Container:
        profile = get_current()
        effect_key = (profile.bg_effect if profile else "snow") or "snow"
        count_scale = float(profile.bg_count_scale) if profile else 1.0
        size_scale = float(profile.bg_size_scale) if profile else 1.0

        try:
            ww = int(self.page.window.width or self.page.width or 1920)
            wh = int(self.page.window.height or self.page.height or 1080)
        except Exception:
            ww, wh = 1920, 1080

        if self._bg_effect is None:
            self._bg_effect = create_effect(
                effect_key, self.page,
                width=ww, height=wh,
                count_scale=count_scale,
                size_scale=size_scale,
            )
            self._bg_effect.start()
        else:
            try:
                self._bg_effect.resume()
            except Exception:
                pass

        bg_layer = self._bg_effect.build()

        top_pad = 32 if self.mobile else 0

        premium_btn = self._make_premium_button()
        new_chat_btn = self._make_new_chat_button()

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.LIGHTBULB_ROUNDED, size=22,
                            color=theme.PRIMARY,
                        ),
                        width=44, height=44, border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.15, theme.PRIMARY),
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Идеи для постов", size=22,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text("10 идей по одной теме",
                                        size=11, color=theme.TEXT_SECONDARY),
                            ],
                            spacing=0, tight=True,
                        ),
                        margin=ft.margin.only(left=12),
                    ),
                    ft.Container(expand=True),
                    premium_btn,
                    ft.Container(width=8),
                    new_chat_btn,
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(
                left=24, right=24, top=top_pad + 16, bottom=12,
            ),
        )

        styles_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PALETTE_ROUNDED, size=14,
                                    color=theme.TEXT_SECONDARY),
                            ft.Text("Стиль", size=12,
                                    color=theme.TEXT_SECONDARY,
                                    weight=ft.FontWeight.BOLD),
                        ],
                        spacing=6, tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=10),
                    self.styles_row,
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
            bgcolor=ft.Colors.with_opacity(0.5, theme.BG_DARK),
        )

        # ============================================================
        # Быстрые темы — теперь ВНИЗУ, над полем ввода
        # ============================================================
        quick_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Быстрые темы", size=11,
                            color=theme.TEXT_MUTED),
                    ft.Container(height=6),
                    self.quick_topics_row,
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.only(left=24, right=24, top=8, bottom=6),
        )

        # ============================================================
        # Нижний блок ввода — единый стиль с хештегами и чатом
        # ============================================================
        input_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[self.topic_field, self.send_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "Enter — придумать · Shift+Enter — новая строка",
                            size=10,
                            color=theme.TEXT_MUTED,
                            text_align=ft.TextAlign.RIGHT,
                        ),
                        padding=ft.padding.only(right=8, top=2),
                    ),
                    self.status_text,
                ],
                spacing=2,
                tight=True,
            ),
            padding=ft.padding.only(left=24, right=24, top=10, bottom=6),
        )

        # ============================================================
        # ПОРЯДОК: header, styles, чат (expand), быстрые темы, ввод
        # ============================================================
        content_col = ft.Column(
            controls=[
                header,
                ft.Container(content=self.messages_list, expand=True),
                styles_block,
                quick_block,
                input_block,
            ],
            spacing=0,
            expand=True,
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

    # ------------------------------------------------------------------
    # Чат-лента
    # ------------------------------------------------------------------

    def _render_chat(self) -> None:
        try:
            self.messages_list.controls.clear()
        except Exception:
            pass

        if not self.chat_messages:
            self._start_typing_animation()
            try:
                self.page.update()
            except Exception:
                pass
            return

        self._stop_typing_animation()

        last_date = None
        for msg in self.chat_messages:
            ts = msg.get("timestamp", "")
            msg_date = None
            if ts:
                try:
                    msg_date = datetime.fromisoformat(ts).date()
                except Exception:
                    msg_date = None

            if msg_date is not None and msg_date != last_date:
                self.messages_list.controls.append(
                    self._make_date_divider(_fmt_date_header(msg_date))
                )
                last_date = msg_date

            role = msg.get("role")
            text = msg.get("text", "")
            if role == "user":
                self.messages_list.controls.append(self._make_user_bubble(text, ts))
            else:
                self.messages_list.controls.append(self._make_ai_bubble(text, ts))

        try:
            self.page.update()
        except Exception:
            pass

    def _make_date_divider(self, text: str) -> ft.Container:
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

    def _make_user_bubble(self, text: str, ts: str) -> ft.Container:
        from ui.message_bubble import get_dynamic_width
        width = get_dynamic_width()
        time_str = _fmt_time(ts)

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(text, size=14, color=ft.Colors.WHITE,
                                        selectable=True, no_wrap=False),
                                ft.Container(
                                    content=ft.Text(
                                        time_str, size=10,
                                        color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
                                    ) if time_str else ft.Container(),
                                    alignment=ft.alignment.bottom_right,
                                    padding=ft.padding.only(top=4),
                                ),
                            ],
                            spacing=0, tight=True,
                        ),
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        bgcolor=theme.USER_BUBBLE,
                        border_radius=theme.RADIUS,
                        width=width,
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            margin=ft.margin.only(left=20, top=4, bottom=4),
        )

    def _make_ai_bubble(self, text: str, ts: str) -> ft.Container:
        from ui.message_bubble import get_dynamic_width
        width = get_dynamic_width()
        time_str = _fmt_time(ts)

        style_title = "универсальные"
        for st in IDEA_STYLES:
            if st["id"] == self.current_style:
                style_title = st["title"].lower()
                break

        rows = []
        header = ft.Row(
            controls=[
                ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, size=14,
                        color=theme.TEXT_SECONDARY),
                ft.Text(
                    f"Идеи к данной теме · стиль {style_title}",
                    size=12,
                    color=theme.TEXT_SECONDARY,
                    weight=ft.FontWeight.NORMAL,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
            spacing=6,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        rows.append(header)
        rows.append(ft.Container(height=8))

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                rows.append(ft.Container(height=4))
                continue

            rows.append(
                ft.Container(
                    content=ft.Text(
                        line,
                        size=14,
                        color=theme.TEXT_PRIMARY,
                        weight=ft.FontWeight.NORMAL,
                        selectable=False,
                        no_wrap=False,
                    ),
                    padding=ft.padding.symmetric(horizontal=6, vertical=3),
                )
            )

        def _copy_all(e):
            try:
                self.page.set_clipboard(text)
                try:
                    self.page.update()
                except Exception:
                    pass
                self.page.open(ft.SnackBar(
                    content=ft.Text("Идеи скопированы"),
                    duration=1200,
                ))
                try:
                    self.page.update()
                except Exception:
                    pass
            except Exception as ex:
                print(f"[IDEAS] copy error: {ex}")

        rows.append(ft.Container(height=8))
        rows.append(
            ft.Row(
                controls=[
                    ft.TextButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.COPY_ROUNDED, size=14,
                                        color=theme.TEXT_SECONDARY),
                                ft.Text("Копировать всё", size=11,
                                        color=theme.TEXT_SECONDARY),
                            ],
                            spacing=4, tight=True,
                        ),
                        on_click=_copy_all,
                    ),
                    ft.Container(expand=True),
                    ft.Text(time_str, size=10,
                            color=theme.TEXT_SECONDARY) if time_str else ft.Container(),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=rows,
                            spacing=2,
                            tight=True,
                        ),
                        padding=ft.padding.all(14),
                        bgcolor=theme.AI_BUBBLE,
                        border_radius=theme.RADIUS,
                        width=width,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            margin=ft.margin.only(right=20, top=4, bottom=4),
        )

    # ------------------------------------------------------------------
    # Анимация печати
    # ------------------------------------------------------------------

    def _start_typing_animation(self) -> None:
        self._stop_typing_animation()

        prefix_widget = ft.Text(_TYPING_PREFIX, size=34,
                                weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_PRIMARY)
        suffix_widget = ft.Text("", size=34,
                                weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_PRIMARY)

        self._typing_text_widget = suffix_widget
        self._typing_alive = True

        title_row = ft.Row(
            controls=[prefix_widget, suffix_widget],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=0, tight=True,
        )

        self.messages_list.controls.clear()
        self.messages_list.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        title_row,
                        ft.Container(
                            content=ft.Text(
                                "Введи тему ниже, чтобы начать",
                                size=13, color=theme.TEXT_MUTED,
                                text_align=ft.TextAlign.CENTER, italic=True,
                            ),
                            margin=ft.margin.only(top=20),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                alignment=ft.alignment.center,
                expand=True,
                padding=ft.padding.symmetric(vertical=160),
            )
        )
        try:
            self.page.update()
        except Exception:
            pass

        def _loop():
            while self._typing_alive:
                for i in range(len(_TYPING_SUFFIX) + 1):
                    if not self._typing_alive:
                        return
                    try:
                        suffix_widget.value = _TYPING_SUFFIX[:i]
                        suffix_widget.update()
                    except Exception:
                        pass
                    time.sleep(_TYPING_SPEED)
                for _ in range(int(_TYPING_HOLD_SEC / 0.1)):
                    if not self._typing_alive:
                        return
                    time.sleep(0.1)
                for _ in range(int(_TYPING_DELETE_HOLD / 0.1)):
                    if not self._typing_alive:
                        return
                    time.sleep(0.1)
                for i in range(len(_TYPING_SUFFIX), -1, -1):
                    if not self._typing_alive:
                        return
                    try:
                        suffix_widget.value = _TYPING_SUFFIX[:i]
                        suffix_widget.update()
                    except Exception:
                        pass
                    time.sleep(_TYPING_DELETE_SPEED)
                for _ in range(5):
                    if not self._typing_alive:
                        return
                    time.sleep(0.1)

        t = threading.Thread(target=_loop, daemon=True)
        self._typing_thread = t
        t.start()

    def _stop_typing_animation(self) -> None:
        self._typing_alive = False
        self._typing_thread = None
        self._typing_text_widget = None

    # ------------------------------------------------------------------
    # Стили
    # ------------------------------------------------------------------

    def _render_styles(self) -> None:
        self.styles_row.controls.clear()
        self._style_refs.clear()
        for st in IDEA_STYLES:
            card, ref = self._make_style_card(st)
            self.styles_row.controls.append(card)
            self._style_refs[st["id"]] = ref

    def _make_style_card(self, style: dict):
        color = style["color"]
        is_active = style["id"] == self.current_style

        if is_active:
            bg = ft.Colors.with_opacity(0.2, color)
            border = color
            icon_bg = color
            icon_c = ft.Colors.WHITE
            title_c = ft.Colors.WHITE
            sub_c = ft.Colors.with_opacity(0.85, color)
        else:
            bg = ft.Colors.with_opacity(0.65, theme.SURFACE)
            border = ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY)
            icon_bg = ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY)
            icon_c = theme.TEXT_PRIMARY
            title_c = theme.TEXT_PRIMARY
            sub_c = theme.TEXT_SECONDARY

        def _click(e, sid=style["id"]):
            self._select_style(sid)

        card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(style["icon"], size=20, color=icon_c),
                        width=40, height=40, border_radius=12,
                        bgcolor=icon_bg,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(height=6),
                    ft.Text(style["title"], size=12,
                            weight=ft.FontWeight.BOLD, color=title_c,
                            text_align=ft.TextAlign.CENTER,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(style["subtitle"], size=9, color=sub_c,
                            text_align=ft.TextAlign.CENTER,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            width=128, height=112,
            padding=ft.padding.symmetric(horizontal=8, vertical=10),
            bgcolor=bg,
            border=ft.border.all(2, border),
            border_radius=14,
            alignment=ft.alignment.center,
            on_click=_click,
            ink=True,
            tooltip=style["subtitle"],
        )

        return card, {"card": card, "color": color}

    def _select_style(self, key: str) -> None:
        if self.current_style == key:
            return
        self.current_style = key

        for sid, ref in self._style_refs.items():
            is_active = sid == key
            color = ref["color"]
            card = ref["card"]
            if is_active:
                card.bgcolor = ft.Colors.with_opacity(0.2, color)
                card.border = ft.border.all(2, color)
                card.content.controls[0].bgcolor = color
                card.content.controls[0].content.color = ft.Colors.WHITE
                card.content.controls[1].color = ft.Colors.WHITE
                card.content.controls[2].color = ft.Colors.with_opacity(0.85, color)
            else:
                card.bgcolor = ft.Colors.with_opacity(0.65, theme.SURFACE)
                card.border = ft.border.all(2, ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY))
                card.content.controls[0].bgcolor = ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY)
                card.content.controls[0].content.color = theme.TEXT_PRIMARY
                card.content.controls[1].color = theme.TEXT_PRIMARY
                card.content.controls[2].color = theme.TEXT_SECONDARY

        try:
            self.page.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Быстрые темы
    # ------------------------------------------------------------------

    def _render_quick_topics(self) -> None:
        self.quick_topics_row.controls.clear()
        for topic in QUICK_TOPICS:
            self.quick_topics_row.controls.append(self._make_quick_chip(topic))

    def _make_quick_chip(self, text: str) -> ft.Container:
        def pick(e):
            self.topic_field.value = text
            try:
                self.topic_field.update()
            except Exception:
                pass

        return ft.Container(
            content=ft.Text(text, size=11,
                            color=theme.TEXT_SECONDARY),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            bgcolor=ft.Colors.with_opacity(0.5, theme.SURFACE),
            border_radius=16,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            on_click=pick,
            ink=True,
        )

    # ------------------------------------------------------------------
    # Генерация
    # ------------------------------------------------------------------

    def _handle_generate(self, e) -> None:
        if self.is_generating or self._stopped:
            return

        topic = (self.topic_field.value or "").strip()
        if not topic:
            self.page.open(ft.SnackBar(
                content=ft.Text("Введи тему"),
                duration=1500,
            ))
            return

        self._stop_typing_animation()

        now_iso = datetime.now().isoformat()
        self.chat_messages.append({
            "role": "user",
            "text": topic,
            "timestamp": now_iso,
        })

        self.topic_field.value = ""
        try:
            self.topic_field.update()
        except Exception:
            pass

        self.is_generating = True
        self.status_text.value = "⏳ Придумываю..."

        self._render_chat()

        thinking_text = ft.Text(
            "Нейро думает",
            size=13, color=theme.TEXT_SECONDARY, italic=True, no_wrap=True,
        )
        dots = []
        for i in range(3):
            d = ft.Container(width=7, height=7, border_radius=4,
                             bgcolor=theme.TEXT_SECONDARY, opacity=0.3)
            dots.append(d)
        dots_row = ft.Row(controls=dots, spacing=4, tight=True)
        content_row = ft.Row(
            controls=[thinking_text, ft.Container(width=6), dots_row],
            spacing=0, alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True,
        )
        bubble = ft.Container(
            content=content_row,
            bgcolor=theme.AI_BUBBLE,
            border_radius=theme.RADIUS,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
        )
        thinking_bubble = ft.Container(
            content=ft.Row(controls=[bubble], alignment=ft.MainAxisAlignment.START),
            margin=ft.margin.only(right=20, top=4, bottom=4),
        )
        self.messages_list.controls.append(thinking_bubble)
        try:
            self.page.update()
        except Exception:
            pass

        dots_state = {"alive": True, "i": 0}

        def _animate():
            while dots_state["alive"] and not self._stopped:
                i = dots_state["i"] % 3
                for j, d in enumerate(dots):
                    try:
                        d.opacity = 1.0 if j == i else 0.3
                        d.update()
                    except Exception:
                        pass
                dots_state["i"] += 1
                time.sleep(0.4)

        threading.Thread(target=_animate, daemon=True).start()

        style_key = self.current_style

        def _worker():
            prompt = self._build_prompt(topic, style_key)
            result = text_provider.ask(
                prompt,
                system="Ты креативный SMM-редактор. Придумываешь идеи "
                       "для постов. Выдаёшь только список, без пояснений.",
                max_tokens=900,
            )

            def _done():
                dots_state["alive"] = False
                self.is_generating = False
                self.status_text.value = ""

                try:
                    if thinking_bubble in self.messages_list.controls:
                        self.messages_list.controls.remove(thinking_bubble)
                except Exception:
                    pass

                if not result:
                    self.chat_messages.append({
                        "role": "assistant",
                        "text": "❌ Не удалось получить идеи",
                        "timestamp": datetime.now().isoformat(),
                    })
                else:
                    ideas = self._parse_ideas(result)
                    if not ideas:
                        self.chat_messages.append({
                            "role": "assistant",
                            "text": "❌ ИИ вернул пустой ответ",
                            "timestamp": datetime.now().isoformat(),
                        })
                    else:
                        formatted = "\n".join(
                            f"{i}. {idea}" for i, idea in enumerate(ideas, 1)
                        )
                        self.chat_messages.append({
                            "role": "assistant",
                            "text": formatted,
                            "timestamp": datetime.now().isoformat(),
                        })
                        self._save_idea_to_history(topic, formatted)

                self._render_chat()

            threading.Timer(0, _done).start()

        threading.Thread(target=_worker, daemon=True).start()

    def _build_prompt(self, topic: str, style_key: str) -> str:
        style_hints = {
            "universal": "Универсальные идеи — разные форматы.",
            "story": "Идеи в формате историй от первого лица.",
            "list": "Идеи в формате списков: «5 способов…», «7 ошибок…».",
            "question": "Идеи в формате вопрос-ответ.",
            "provocation": "Провокационные идеи — резкие тезисы.",
        }
        hint = style_hints.get(style_key, style_hints["universal"])
        return (
            f"Тема: «{topic}»\n\n"
            f"Придумай РОВНО 10 разных идей для постов по этой теме.\n\n"
            f"Стиль: {hint}\n\n"
            "ФОРМАТ ОТВЕТА:\n"
            "Каждая идея на новой строке, начинается с цифры и точки.\n"
            "Идея = 1-2 предложения, конкретная.\n"
            "НЕ пиши вступление и заключение.\n"
            "Только список 1-10.\n"
            "Начни СРАЗУ с «1.»."
        )

    def _parse_ideas(self, raw: str) -> list:
        import re as _re
        text = (raw or "").strip()
        pattern = _re.compile(
            r"^\s*(\d+)\s*[\.\)]\s*(.+?)(?=^\s*\d+\s*[\.\)]|\Z)",
            _re.MULTILINE | _re.DOTALL,
        )
        ideas = []
        for m in pattern.finditer(text):
            body = m.group(2).strip()
            body = _re.sub(r"\s+", " ", body)
            if body:
                ideas.append(body)
        if not ideas:
            for line in text.split("\n"):
                line = line.strip()
                if len(line) > 5:
                    ideas.append(line)
        return ideas[:10]

    def _save_idea_to_history(self, topic: str, ideas_text: str) -> None:
        try:
            item = {
                "id": f"{int(datetime.now().timestamp() * 1000)}",
                "topic": topic[:120],
                "ideas": ideas_text,
                "created_at": datetime.now().isoformat(),
            }
            self.history.insert(0, item)
            self.history = self.history[:50]
            _save_history(self.history)
        except Exception as ex:
            print(f"[IDEAS] save history error: {ex}")