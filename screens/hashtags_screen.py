"""Экран «Хештеги» — генератор хештегов по теме.

  • Сверху — шапка + Premium + Новый чат.
  • По центру — чат-лента с пузырями и датами.
  • Внизу — стиль, поле ввода, кнопка.

Фиксированно 20 хештегов. Строго по теме.
"""

import json
import os
import threading
import time
from datetime import datetime, date

import flet as ft

from services import paths, text_ai
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


_TYPING_PREFIX = "V-Agent"
_TYPING_SUFFIX = " - твой помощник в хештегах"
_TYPING_SPEED = 0.07
_TYPING_DELETE_SPEED = 0.035
_TYPING_HOLD_SEC = 4.0
_TYPING_DELETE_HOLD = 0.5


FIXED_COUNT = 20


HASHTAG_STRATEGIES = [
    {"id": "mixed", "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
     "title": "Смешанные", "subtitle": "Разные", "color": "#9C27B0"},
    {"id": "content", "icon": ft.Icons.ARTICLE_ROUNDED,
     "title": "Контентные", "subtitle": "Тематические", "color": "#2196F3"},
    {"id": "wide", "icon": ft.Icons.PUBLIC_ROUNDED,
     "title": "Широкие", "subtitle": "Массовые", "color": "#4CAF50"},
    {"id": "medium", "icon": ft.Icons.LOCATION_CITY_ROUNDED,
     "title": "Средние", "subtitle": "Тематические", "color": "#00BCD4"},
    {"id": "niche", "icon": ft.Icons.SEARCH_ROUNDED,
     "title": "Нишевые", "subtitle": "Точные", "color": "#009688"},
    {"id": "trending", "icon": ft.Icons.TRENDING_UP_ROUNDED,
     "title": "Трендовые", "subtitle": "Актуальные", "color": "#FF5722"},
    {"id": "branded", "icon": ft.Icons.BUSINESS_CENTER_ROUNDED,
     "title": "Брендовые", "subtitle": "Личный бренд", "color": "#E91E63"},
    {"id": "audience", "icon": ft.Icons.GROUPS_ROUNDED,
     "title": "Целевые", "subtitle": "По аудитории", "color": "#3F51B5"},
    {"id": "flashmob", "icon": ft.Icons.BOLT_ROUNDED,
     "title": "Флешмобы", "subtitle": "Челленджи", "color": "#FFC107"},
    {"id": "emotion", "icon": ft.Icons.FAVORITE_ROUNDED,
     "title": "Эмоции", "subtitle": "Настроение", "color": "#F06292"},
    {"id": "humor", "icon": ft.Icons.SENTIMENT_VERY_SATISFIED_ROUNDED,
     "title": "Юмор", "subtitle": "Ирония", "color": "#FFB74D"},
    {"id": "spam", "icon": ft.Icons.WARNING_AMBER_ROUNDED,
     "title": "Спам", "subtitle": "Не рекомендуется", "color": "#F44336"},
    {"id": "abstract", "icon": ft.Icons.CLOUD_ROUNDED,
     "title": "Абстрактные", "subtitle": "Общие", "color": "#795548"},
]


# ===========================================================================
# История
# ===========================================================================

def _history_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "hashtags_history.json")


def _load_history() -> list:
    p = _history_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            items = json.load(f)
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _save_history(items: list) -> None:
    try:
        paths.atomic_write_json(_history_path(), items)
    except Exception as ex:
        print(f"[HASHTAGS] save error: {ex}")


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


class HashtagsScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.mobile = _is_mobile(page)
        self._bg_effect = None
        self._stopped = False

        self.current_strategy = "mixed"
        self.current_count = FIXED_COUNT
        self.is_generating = False

        self.history: list = _load_history()
        self.chat_messages: list = []

        self._typing_alive = False
        self._typing_text_widget = None
        self._typing_thread = None

        self.topic_field = ft.TextField(
            hint_text="Введи тему или текст поста...",
            multiline=True,
            min_lines=1,
            max_lines=6,
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=theme.RADIUS,
            border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY,
            text_size=14,
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
            tooltip="Сгенерировать хештеги",
        )

        self.status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

        self.strategies_row = ft.Row(
            spacing=10, run_spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

        self.messages_list = ft.ListView(
            expand=True, spacing=2, auto_scroll=True,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
        )

        self._strategy_refs: dict = {}

        self._render_strategies()
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
                    ft.Text(text, size=11,
                            color=color,
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
            print(f"[HASHTAGS] open subscription error: {ex}")

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

        # ПРОВЕРКА НА ПУСТОТУ ДЛЯ КНОПКИ "НОВЫЙ ЧАТ"
        is_disabled = len(self.chat_messages) == 0
        bg_color = theme.SURFACE if is_disabled else theme.PRIMARY
        text_color = theme.TEXT_MUTED if is_disabled else ft.Colors.WHITE
        icon_color = theme.TEXT_MUTED if is_disabled else ft.Colors.WHITE

        new_chat_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=14, color=icon_color),
                    ft.Text("Новый чат", size=11, color=text_color, weight=ft.FontWeight.BOLD),
                ],
                spacing=4, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
            bgcolor=bg_color,
            on_click=self._handle_new_chat if not is_disabled else None,
            ink=not is_disabled,
            tooltip="Создать новый чат" if not is_disabled else "Чат уже пуст",
        )

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.TAG_ROUNDED, size=22,
                            color=theme.PRIMARY,
                        ),
                        width=44, height=44, border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.15, theme.PRIMARY),
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Хештеги", size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text("ИИ подберёт теги по теме поста",
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
                left=24, right=24, top=top_pad + 16, bottom=8,
            ),
        )

        settings_block = ft.Container(
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
                    self.strategies_row,
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
            bgcolor=ft.Colors.with_opacity(0.5, theme.BG_DARK),
        )
        input_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[self.topic_field, self.send_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Text(
                        "Enter — сгенерировать · Shift+Enter — новая строка",
                        size=10, color=theme.TEXT_MUTED,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                    self.status_text,
                ],
                spacing=2, tight=True,
            ),
            padding=ft.padding.only(left=24, right=24, top=14, bottom=14),
            bgcolor=ft.Colors.with_opacity(0.7, theme.BG_DARK),
        )

        content_col = ft.Column(
            controls=[
                header,
                ft.Container(content=self.messages_list, expand=True),
                settings_block,
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

        style_title = "смешанные"
        for st in HASHTAG_STRATEGIES:
            if st["id"] == self.current_strategy:
                style_title = st["title"].lower()
                break

        rows = []
        header = ft.Row(
            controls=[
                ft.Icon(ft.Icons.TAG_ROUNDED, size=14,
                        color=theme.TEXT_SECONDARY),
                ft.Text(
                    f"Хештеги к данной теме · стиль {style_title}",
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

            def _copy_tag(e, t=line):
                try:
                    self.page.set_clipboard(t)
                    try:
                        self.page.update()
                    except Exception:
                        pass
                    self.page.open(ft.SnackBar(
                        content=ft.Text(f"Скопировано: {t}"),
                        duration=1000,
                    ))
                    try:
                        self.page.update()
                    except Exception:
                        pass
                except Exception as ex:
                    print(f"[HASHTAGS] copy tag error: {ex}")

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
                    border_radius=6,
                    on_click=_copy_tag,
                    ink=True,
                    tooltip="Нажми, чтобы скопировать",
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
                    content=ft.Text("Хештеги скопированы"),
                    duration=1200,
                ))
                try:
                    self.page.update()
                except Exception:
                    pass
            except Exception as ex:
                print(f"[HASHTAGS] copy error: {ex}")

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

        prefix_widget = ft.Text(
            _TYPING_PREFIX,
            size=34,
            weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY,
        )

        suffix_widget = ft.Text(
            "",
            size=34,
            weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY,
        )

        self._typing_text_widget = suffix_widget
        self._typing_alive = True

        title_row = ft.Row(
            controls=[prefix_widget, suffix_widget],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=0,
            tight=True,
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
                                size=13,
                                color=theme.TEXT_MUTED,
                                text_align=ft.TextAlign.CENTER,
                                italic=True,
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
    # Кружки «Нейро думает» в одном пузыре с текстом
    # ------------------------------------------------------------------

    def _make_thinking_bubble(self) -> ft.Container:
        thinking_text = ft.Text(
            "Нейро думает",
            size=13,
            color=theme.TEXT_SECONDARY,
            italic=True,
            no_wrap=True,
        )

        dots = []
        for i in range(3):
            d = ft.Container(
                width=7, height=7,
                border_radius=4,
                bgcolor=theme.TEXT_SECONDARY,
                opacity=0.3,
            )
            dots.append(d)

        dots_row = ft.Row(
            controls=dots,
            spacing=4,
            alignment=ft.MainAxisAlignment.START,
            tight=True,
        )

        content_row = ft.Row(
            controls=[thinking_text, ft.Container(width=6), dots_row],
            spacing=0,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

        bubble = ft.Container(
            content=content_row,
            bgcolor=theme.AI_BUBBLE,
            border_radius=theme.RADIUS,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
        )

        outer = ft.Container(
            content=ft.Row(
                controls=[bubble],
                alignment=ft.MainAxisAlignment.START,
            ),
            margin=ft.margin.only(right=20, top=4, bottom=4),
        )

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

        t = threading.Thread(target=_animate, daemon=True)
        t.start()

        outer._dots_state = dots_state
        return outer

    # ------------------------------------------------------------------
    # Стратегии
    # ------------------------------------------------------------------

    def _render_strategies(self) -> None:
        self.strategies_row.controls.clear()
        self._strategy_refs.clear()
        for st in HASHTAG_STRATEGIES:
            card, ref = self._make_strategy_card(st)
            self.strategies_row.controls.append(card)
            self._strategy_refs[st["id"]] = ref

    def _make_strategy_card(self, style: dict):
        color = style["color"]
        is_active = style["id"] == self.current_strategy

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
            self._select_strategy(sid)

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
                            weight=ft.FontWeight.BOLD,
                            color=title_c,
                            text_align=ft.TextAlign.CENTER,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(style["subtitle"], size=9, color=sub_c,
                            text_align=ft.TextAlign.CENTER,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
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

    def _select_strategy(self, key: str) -> None:
        if self.current_strategy == key:
            return
        self.current_strategy = key

        for sid, ref in self._strategy_refs.items():
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
    # Генерация
    # ------------------------------------------------------------------

    def _handle_generate(self, e) -> None:
        if self.is_generating or self._stopped:
            return

        topic = (self.topic_field.value or "").strip()
        if not topic:
            self.page.open(ft.SnackBar(
                content=ft.Text("Введи тему или текст поста"),
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
        self.status_text.value = ""

        self._render_chat()

        thinking_bubble = self._make_thinking_bubble()
        self.messages_list.controls.append(thinking_bubble)
        try:
            self.page.update()
        except Exception:
            pass

        strategy = self.current_strategy
        count = FIXED_COUNT

        def _worker():
            result = text_ai.generate_hashtags(
                topic=topic,
                hashtag_style=strategy,
                count=count,
            )

            def _done():
                try:
                    if hasattr(thinking_bubble, "_dots_state"):
                        thinking_bubble._dots_state["alive"] = False
                except Exception:
                    pass

                self.is_generating = False

                try:
                    if thinking_bubble in self.messages_list.controls:
                        self.messages_list.controls.remove(thinking_bubble)
                except Exception:
                    pass

                if not result:
                    err = "❌ Не удалось получить хештеги"
                    self.chat_messages.append({
                        "role": "assistant",
                        "text": err,
                        "timestamp": datetime.now().isoformat(),
                    })
                else:
                    tags = [t for t in result.split() if t.startswith("#")]
                    formatted = "\n".join(tags)

                    self.chat_messages.append({
                        "role": "assistant",
                        "text": formatted,
                        "timestamp": datetime.now().isoformat(),
                    })
                    self._save_to_history(topic, formatted, strategy, count)

                self._render_chat()
                # Обновляем кнопку "Новый чат"
                try:
                    self.page.update()
                except Exception:
                    pass

            threading.Timer(0, _done).start()

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # История
    # ------------------------------------------------------------------

    def _save_to_history(self, topic: str, hashtags: str,
                         strategy: str, count: int) -> None:
        try:
            item = {
                "id": f"{int(datetime.now().timestamp() * 1000)}",
                "topic": topic[:120],
                "hashtags": hashtags,
                "strategy": strategy,
                "count": count,
                "created_at": datetime.now().isoformat(),
            }
            self.history.insert(0, item)
            self.history = self.history[:50]
            _save_history(self.history)
        except Exception as ex:
            print(f"[HASHTAGS] save history error: {ex}")