"""Главная страница — главное меню V-Agent.

Адаптивный дизайн:
  • Ширина окна < 1300 px  → SMALL (компактно)
  • Ширина окна >= 1300 px → BIG   (крупный текст + отступы)
"""

import os
from datetime import datetime
from typing import Callable, Optional

import flet as ft

from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


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


def _get_window_width(page: ft.Page) -> int:
    candidates = []
    try:
        w = int(page.width or 0)
        if w > 0:
            candidates.append(w)
    except Exception:
        pass
    try:
        w = int(page.window.width or 0)
        if w > 0:
            candidates.append(w)
    except Exception:
        pass
    w = max(candidates) if candidates else 0
    print(f"[HOME] width candidates={candidates}, using={w}")
    return w


def _is_big_mode(page: ft.Page) -> bool:
    return _get_window_width(page) >= 1300


# ===========================================================================
# Карточки главного меню
# ===========================================================================

MAIN_MENU = [
    {
        "id": "ideas",
        "title": "Идеи",
        "subtitle": (
            "10 свежих идей для постов по одной теме.\n"
            "Выбери формат — список, история, вопрос —\n"
            "и получи готовые темы для контента."
        ),
        "icon": ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
        "color": "#FFC107",
        "premium": False,
    },
    {
        "id": "content",
        "title": "Автосоздание контента",
        "subtitle": (
            "ИИ напишет пачку постов по одной теме:\n"
            "разные форматы и стили сразу.\n"
            "Готовый текст с эмодзи и оформлением."
        ),
        "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
        "color": "#8E44AD",
        "premium": True,
    },
    {
        "id": "image",
        "title": "Изображения",
        "subtitle": (
            "7 стилей картинок: реализм, аниме, 3D,\n"
            "киберпанк, фэнтези, скетч, минимализм.\n"
            "Просто опиши — ИИ нарисует."
        ),
        "icon": ft.Icons.IMAGE_ROUNDED,
        "color": "#16A085",
        "premium": False,
    },
    {
        "id": "telegram",
        "title": "Автоведение ТГК",
        "subtitle": (
            "Автопостинг в Telegram-канал по расписанию.\n"
            "Составь контент-план, добавь бота —\n"
            "посты уйдут сами в нужное время."
        ),
        "icon": ft.Icons.SEND_ROUNDED,
        "color": "#229ED9",
        "premium": True,
    },
    {
        "id": "templates",
        "title": "Шаблоны",
        "subtitle": (
            "8 готовых структур: инструкция, обзор,\n"
            "кейс, 10 фактов, вопрос-ответ, ТОП-N,\n"
            "сравнение, ошибки."
        ),
        "icon": ft.Icons.GRID_VIEW_ROUNDED,
        "color": "#4CAF50",
        "premium": False,
    },
    {
        "id": "chat",
        "title": "Чат с ИИ",
        "subtitle": (
            "Задай любой вопрос или попроси написать\n"
            "пост, письмо, сценарий. ИИ отвечает\n"
            "в реальном времени, помнит контекст."
        ),
        "icon": ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
        "color": "#9C27B0",
        "premium": False,
    },
]


# ===========================================================================
# Стили
# ===========================================================================

SMALL = {
    "font_title": 16, "font_subtitle": 11, "font_icon": 24, "font_arrow": 18,
    "icon_size": 48, "arrow_size": 32, "card_padding": 14, "card_radius": 16,
    "card_spacing_h": 16, "card_spacing_v": 16, "icon_height": 10, "title_gap": 4,
    "page_padding": 24, "top_gap": 12, "greeting_gap": 12,
    "font_greeting": 20, "font_greeting_sub": 12,
    "font_logo": 20, "font_logo_sub": 10,
    "card_min_height": 200,
}

BIG = {
    "font_title": 22, "font_subtitle": 14, "font_icon": 30, "font_arrow": 22,
    "icon_size": 60, "arrow_size": 40, "card_padding": 22, "card_radius": 20,
    "card_spacing_h": 28, "card_spacing_v": 28, "icon_height": 16, "title_gap": 8,
    "page_padding": 32, "top_gap": 16, "greeting_gap": 20,
    "font_greeting": 24, "font_greeting_sub": 13,
    "font_logo": 22, "font_logo_sub": 11,
    "card_min_height": 260,
}


class HomeScreen:
    def __init__(
        self,
        page: ft.Page,
        on_open_mode: Callable[[str], None],
    ) -> None:
        self.page = page
        self.on_open_mode = on_open_mode
        self.mobile = _is_mobile(page)
        self._bg_effect = None
        self._stopped = False
        self.S = SMALL

    def stop_effect(self) -> None:
        self._stopped = True
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None

    def _greeting(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "Доброе утро"
        if 12 <= hour < 18:
            return "Добрый день"
        if 18 <= hour < 23:
            return "Добрый вечер"
        return "Доброй ночи"

    # ---------- Построение ----------

    def build(self) -> ft.Container:
        big = _is_big_mode(self.page)
        self.S = BIG if big else SMALL
        print(f"[HOME] big_mode={big}, font_title={self.S['font_title']}")

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

        top_bar = self._make_top_bar()
        greeting = self._make_greeting()

        per_row = 1 if self.mobile else 3

        cards_rows = []
        for i in range(0, len(MAIN_MENU), per_row):
            chunk = MAIN_MENU[i:i + per_row]
            row_controls = []
            for m in chunk:
                row_controls.append(self._make_menu_card(m))
            while len(row_controls) < per_row:
                row_controls.append(ft.Container(expand=True))
            cards_rows.append(
                ft.Row(
                    controls=row_controls,
                    spacing=self.S["card_spacing_h"],
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                )
            )

        cards_col = ft.Column(
            controls=cards_rows,
            spacing=self.S["card_spacing_v"],
            expand=True,
        )

        premium_banner = self._make_premium_banner()

        content_col = ft.Column(
            controls=[
                top_bar,
                ft.Container(height=self.S["top_gap"]),
                greeting,
                ft.Container(height=self.S["greeting_gap"]),
                cards_col,
                ft.Container(height=self.S["greeting_gap"]),
                premium_banner,
                ft.Container(height=8),
                self._make_bottom_bar(),
            ],
            spacing=0,
            expand=True,
        )

        main_layer = ft.Container(
            content=content_col,
            expand=True,
            padding=ft.padding.symmetric(horizontal=self.S["page_padding"]),
            bgcolor=ft.Colors.with_opacity(0.4, theme.BG_DARK),
        )

        return ft.Container(
            content=ft.Stack(
                controls=[bg_layer, main_layer],
                expand=True,
            ),
            expand=True,
        )

    def _make_greeting(self) -> ft.Container:
        profile = get_current()
        name = (profile.name if profile else "") or "друг"
        greeting_text = self._greeting()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                f"{greeting_text}, {name}! 👋",
                                size=self.S["font_greeting"],
                                weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_PRIMARY,
                            ),
                            ft.Container(height=4),
                            ft.Text(
                                "Чем займёмся сегодня?",
                                size=self.S["font_greeting_sub"],
                                color=theme.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=0, tight=True,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=4, top=4, bottom=4),
        )

    def _make_top_bar(self) -> ft.Container:
        logo_icon = ft.Container(
            content=ft.Image(
                src="v_agent_icon.png",
                width=44, height=44,
                fit=ft.ImageFit.COVER,
                border_radius=12,
            ),
            width=48, height=48, border_radius=14,
            alignment=ft.alignment.center,
        )

        logo_text = ft.Column(
            controls=[
                ft.Text("V-Agent", size=self.S["font_logo"],
                        weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY),
                ft.Text("Твой помощник по созданию контента",
                        size=self.S["font_logo_sub"],
                        color=theme.TEXT_SECONDARY),
            ],
            spacing=2, tight=True,
        )

        logo_block = ft.Row(
            controls=[
                logo_icon,
                ft.Container(content=logo_text, margin=ft.margin.only(left=12)),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        tg_channel = self._make_tg_channel_badge()
        settings_btn = self._make_icon_button(
            ft.Icons.SETTINGS_ROUNDED, "Настройки",
            lambda e: self._safe_open("settings"),
        )
        profile_btn = self._make_icon_button(
            ft.Icons.PERSON_ROUNDED, "Профиль",
            lambda e: self._open_profile(),
        )

        right_block = ft.Row(
            controls=[
                tg_channel,
                ft.Container(width=8),
                settings_btn,
                ft.Container(width=8),
                profile_btn,
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    logo_block,
                    ft.Container(expand=True),
                    right_block,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=False,
            ),
            padding=ft.padding.only(top=16, bottom=8),
        )

    def _make_tg_channel_badge(self) -> ft.Container:
        is_ready = False
        try:
            profile = get_current()
            if profile and getattr(profile, "tg_bots", []):
                is_ready = True
        except Exception:
            pass

        if is_ready:
            status_color = "#4CAF50"
            status_text = "Готов к работе"
        else:
            status_color = "#FF9800"
            status_text = "Не подключён"

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SEND_ROUNDED, size=14,
                            color=theme.TEXT_PRIMARY),
                    ft.Column(
                        controls=[
                            ft.Text("TG Channel", size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY),
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        width=6, height=6, border_radius=3,
                                        bgcolor=status_color,
                                    ),
                                    ft.Text(status_text, size=9,
                                            color=theme.TEXT_SECONDARY),
                                ],
                                spacing=4,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=0, tight=True,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            bgcolor=ft.Colors.with_opacity(0.5, theme.SURFACE),
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            border_radius=12,
            on_click=lambda e: self._safe_open("telegram"),
            ink=True,
            tooltip="Открыть Telegram",
        )

    def _make_icon_button(self, icon, tooltip, on_click) -> ft.Container:
        return ft.Container(
            content=ft.Icon(icon, size=20, color=theme.TEXT_PRIMARY),
            width=42, height=42, border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.5, theme.SURFACE),
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            alignment=ft.alignment.center,
            on_click=on_click,
            ink=True,
            tooltip=tooltip,
        )

    # ---------- Карточка меню ----------

    def _make_menu_card(self, mode: dict) -> ft.Container:
        color = mode["color"]
        mode_id = mode["id"]
        is_premium_section = mode.get("premium", False)

        is_locked = False
        if is_premium_section:
            try:
                from services.premium_guard import is_premium
                is_locked = not is_premium()
            except Exception:
                is_locked = True

        def _open(e):
            self._safe_open(mode_id)

        icon_box = ft.Container(
            content=ft.Icon(mode["icon"], size=self.S["font_icon"],
                            color=ft.Colors.WHITE),
            width=self.S["icon_size"],
            height=self.S["icon_size"],
            border_radius=14,
            bgcolor=color,
            alignment=ft.alignment.center,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=14,
                color=ft.Colors.with_opacity(0.45, color),
            ),
        )

        if is_locked:
            lock_badge = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.KEY_ROUNDED, size=14,
                                color="#000000"),
                        ft.Text("PREMIUM", size=9,
                                color="#000000",
                                weight=ft.FontWeight.BOLD),
                    ],
                    spacing=4, tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                bgcolor="#FFD700",
                border_radius=8,
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.6, "#FFD700"),
                ),
            )
        else:
            lock_badge = ft.Container()

        arrow = ft.Container(
            content=ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED,
                            size=self.S["font_arrow"],
                            color=theme.TEXT_MUTED),
            width=self.S["arrow_size"],
            height=self.S["arrow_size"],
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.15, theme.TEXT_MUTED),
            alignment=ft.alignment.center,
        )

        title_text = ft.Text(
            mode["title"], size=self.S["font_title"],
            weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        subtitle_text = ft.Text(
            mode["subtitle"], size=self.S["font_subtitle"],
            color=theme.TEXT_SECONDARY,
            no_wrap=False,
        )

        card_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[icon_box, ft.Container(expand=True), lock_badge],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ft.Container(height=self.S["icon_height"]),
                title_text,
                ft.Container(height=self.S["title_gap"]),
                subtitle_text,
                ft.Container(expand=True),
                ft.Row(
                    controls=[
                        ft.Container(expand=True),
                        arrow,
                    ],
                    spacing=0,
                ),
            ],
            spacing=0, tight=True,
        )

        card = ft.Container(
            content=card_content,
            padding=ft.padding.all(self.S["card_padding"]),
            bgcolor=theme.SURFACE,
            border=ft.border.all(
                2 if is_locked else 1,
                "#FFD700" if is_locked else theme.DRAWER_ITEM_BORDER,
            ),
            border_radius=self.S["card_radius"],
            expand=True,
            height=self.S["card_min_height"],
            on_click=_open,
            ink=True,
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            scale=1.0,
            on_hover=self._hover_scale,
        )

        return card

    def _hover_scale(self, e: ft.ControlEvent) -> None:
        try:
            ctrl = e.control
            if e.data == "true":
                ctrl.scale = 1.02
            else:
                ctrl.scale = 1.0
            ctrl.update()
        except Exception:
            pass

    # ---------- Баннер Premium ----------

    def _make_premium_banner(self) -> ft.Container:
        try:
            from services.premium_guard import is_premium
            premium = is_premium()
        except Exception:
            premium = False

        if premium:
            bg_color = ft.Colors.with_opacity(0.12, "#4CAF50")
            border_color = ft.Colors.with_opacity(0.4, "#4CAF50")
            icon_color = "#4CAF50"
            title = "Premium активен ✓"
            subtitle = "Все функции разблокированы. Спасибо за поддержку!"
            btn_text = "Управление"
        else:
            bg_color = ft.Colors.with_opacity(0.12, "#FFD700")
            border_color = ft.Colors.with_opacity(0.6, "#FFD700")
            icon_color = "#FFD700"
            title = "Разблокируй все функции"
            subtitle = "Автоведение ТГК и Автосоздание — от 199 ₽"
            btn_text = "Купить"

        def open_premium(e):
            try:
                self.on_open_mode("subscription")
            except Exception as ex:
                print(f"[HOME] open premium error: {ex}")

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                            size=24, color=ft.Colors.BLACK if not premium else ft.Colors.WHITE,
                        ),
                        width=48, height=48, border_radius=14,
                        bgcolor=icon_color,
                        alignment=ft.alignment.center,
                        shadow=ft.BoxShadow(
                            spread_radius=1,
                            blur_radius=14,
                            color=ft.Colors.with_opacity(0.5, icon_color),
                        ),
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(title, size=15,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text(subtitle, size=12,
                                        color=theme.TEXT_SECONDARY),
                            ],
                            spacing=2, tight=True,
                        ),
                        expand=True,
                        margin=ft.margin.only(left=14),
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text(btn_text, size=13,
                                        color=ft.Colors.BLACK if not premium else ft.Colors.WHITE,
                                        weight=ft.FontWeight.BOLD),
                                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                        size=16,
                                        color=ft.Colors.BLACK if not premium else ft.Colors.WHITE),
                            ],
                            spacing=4, tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                        bgcolor=icon_color,
                        border_radius=10,
                        on_click=open_premium,
                        ink=True,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.all(14),
            bgcolor=bg_color,
            border=ft.border.all(1, border_color),
            border_radius=14,
        )

    # ---------- Нижняя панель ----------

    def _make_bottom_bar(self) -> ft.Container:
        zero_cost = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.BOLT_ROUNDED, size=12,
                            color=ft.Colors.WHITE,
                        ),
                        width=20, height=20, border_radius=10,
                        bgcolor=theme.PRIMARY,
                        alignment=ft.alignment.center,
                    ),
                    ft.Text("Управляй контентом", size=11,
                            color=theme.TEXT_SECONDARY),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            bgcolor=ft.Colors.with_opacity(0.4, theme.SURFACE),
            border_radius=10,
        )

        slogan = ft.Row(
            controls=[
                ft.Text("Больше контента — больше охватов",
                        size=11, color=theme.TEXT_MUTED),
                ft.Icon(ft.Icons.TRENDING_UP_ROUNDED,
                        size=14, color=theme.TEXT_MUTED),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    zero_cost,
                    ft.Container(expand=True),
                    slogan,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=False,
            ),
            padding=ft.padding.only(top=8, bottom=12),
        )

    # ---------- Обработчики ----------

    def _safe_open(self, mode_id: str) -> None:
        try:
            print(f"[HOME] open: {mode_id}")
            self.on_open_mode(mode_id)
        except Exception as ex:
            print(f"[HOME] open error: {ex}")

    def _open_profile(self) -> None:
        try:
            chat = getattr(self.page, "_vagent_chat_screen", None)
            if chat is not None:
                chat._open_profile()
        except Exception as ex:
            print(f"[HOME] open profile error: {ex}")