"""Экран генерации картинок с анимацией и сохранением истории."""

import json
import math
import os
import random
import re
import shutil
import threading
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import flet as ft

from services import image_ai, image_storage, paths
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


def _history_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "image_history.json")


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
    clean = []
    for it in items:
        if it.get("_is_progress"):
            continue
        clean.append({
            "role": it.get("role"),
            "prompt": it.get("prompt"),
            "style_key": it.get("style_key"),
            "image_path": it.get("image_path"),
            "error": it.get("error"),
            "timestamp": it.get("timestamp"),
        })
    try:
        with open(_history_path(), "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print(f"[IMAGE HISTORY] save error: {ex}")


STYLE_UI = {
    "photo":     (ft.Icons.PHOTO_CAMERA_ROUNDED,  "Реализм",    "как фото"),
    "anime":     (ft.Icons.AUTO_AWESOME_ROUNDED,  "Аниме",      "Studio Ghibli"),
    "3d":        (ft.Icons.VIEW_IN_AR_ROUNDED,    "3D",         "Pixar / Unreal"),
    "cyberpunk": (ft.Icons.LOCATION_CITY_ROUNDED, "Киберпанк",  "neon city"),
    "fantasy":   (ft.Icons.AUTO_FIX_HIGH_ROUNDED, "Фэнтези",    "epic fantasy"),
    "sketch":    (ft.Icons.EDIT_ROUNDED,          "Скетч",      "pencil"),
    "minimal":   (ft.Icons.CROP_SQUARE_ROUNDED,   "Минимализм", "flat vector"),
}


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


class ImageScreen:
    def __init__(self, page: ft.Page, on_open_settings=None) -> None:
        self.page = page
        self.on_open_settings = on_open_settings

        self.current_style = "photo"
        self.is_generating = False
        self.history: list[dict] = _load_history()

        self.prompt_field = ft.TextField(
            hint_text="Опиши картинку...",
            min_lines=1,
            max_lines=6,
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=theme.RADIUS,
            border_color=theme.SURFACE,
            expand=True,
            on_submit=self._handle_send,
        )

        self.send_btn = ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD_ROUNDED,
            icon_color=ft.Colors.WHITE,
            bgcolor=theme.PRIMARY,
            on_click=self._handle_send,
            tooltip="Сгенерировать",
        )

        self.clear_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, size=16,
                            color=theme.TEXT_SECONDARY),
                    ft.Text("Очистить историю", size=12,
                            color=theme.TEXT_SECONDARY),
                ],
                spacing=6, tight=True,
            ),
            on_click=self._clear_history,
        )

        self.messages_list = ft.ListView(
            expand=True, spacing=12, auto_scroll=True,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
        )

        self.styles_grid = ft.Row(
            controls=[], spacing=8, run_spacing=8, wrap=True,
        )

        self.status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

        self._bg_effect = None
        self._stopped = False
        self._prev_keyboard_handler = None

        self._render_styles()
        self._render_history()

    def _has_cf_token(self) -> bool:
        try:
            from services import cf_config
            account, token = cf_cfg_creds = cf_config.get_cf_credentials()
            return bool(account and token)
        except Exception:
            return False

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
        try:
            prev = self._prev_keyboard_handler
            self._prev_keyboard_handler = None
            if prev is not None:
                self.page.on_keyboard_event = prev
            else:
                self.page.on_keyboard_event = None
        except Exception:
            pass

    def resume_effect(self) -> None:
        """Возобновление после возврата на экран."""
        self._stopped = False

    def build(self) -> ft.Container:
        # Сброс stopped — на случай, если вернулись на экран
        self._stopped = False

        if not self._has_cf_token():
            return self._build_no_token_screen()

        profile = get_current()
        effect_key = (profile.bg_effect if profile else "snow") or "snow"
        count_scale = float(profile.bg_count_scale) if profile else 1.0
        size_scale = float(profile.bg_size_scale) if profile else 1.0

        try:
            ww = int(self.page.window.width or self.page.width or 1920)
            wh = int(self.page.window.height or self.page.height or 1080)
        except Exception:
            ww, wh = 1920, 1080

        # Если эффект уже есть — используем его, не создаём заново
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

        self._install_keyboard()

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.BRUSH_ROUNDED, size=22, color=theme.PRIMARY),
                    ft.Text("Генерация картинок", size=18,
                            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    self.clear_btn,
                ],
                spacing=10, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
        )

        style_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PALETTE_ROUNDED, size=14,
                                    color=theme.TEXT_SECONDARY),
                            ft.Text("Стиль", size=12, color=theme.TEXT_SECONDARY,
                                    weight=ft.FontWeight.BOLD),
                        ],
                        spacing=6, tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=10),
                    self.styles_grid,
                ],
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
        )

        input_row = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[self.prompt_field, self.send_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Text(
                        "Enter — сгенерировать",
                        size=10, color=theme.TEXT_SECONDARY,
                    ),
                    self.status_text,
                ],
                spacing=6,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
        )

        content_col = ft.Column(
            controls=[header, self.messages_list, style_panel, input_row],
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
        """Enter — сгенерировать. Shift+Enter — новая строка."""
        self._prev_keyboard_handler = getattr(self.page, "on_keyboard_event", None)

        def on_key(e: ft.KeyboardEvent) -> None:
            if self._stopped:
                return
            if e.key != "Enter":
                return
            if e.shift:
                # Shift+Enter — новая строка, обрабатывает TextField сам
                return
            self._handle_send(None)

        try:
            self.page.on_keyboard_event = on_key
        except Exception:
            pass

    def _build_no_token_screen(self) -> ft.Container:
        def open_settings(e):
            if self.on_open_settings:
                self.on_open_settings()

        profile = get_current()
        effect_key = (profile.bg_effect if profile else "snow") or "snow"
        count_scale = float(profile.bg_count_scale) if profile else 1.0
        size_scale = float(profile.bg_size_scale) if profile else 1.0

        if self._bg_effect is None:
            self._bg_effect = create_effect(
                effect_key, self.page,
                count_scale=count_scale,
                size_scale=size_scale,
            )
            self._bg_effect.start()
        bg_layer = self._bg_effect.build()

        card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.CLOUD_ROUNDED, size=48,
                                        color=ft.Colors.WHITE),
                        width=96, height=96, border_radius=48,
                        bgcolor=ft.Colors.with_opacity(0.15, theme.PRIMARY),
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(height=20),
                    ft.Text("Нужен ключ Cloudflare", size=22,
                            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    ft.Text("Без ключа генерация картинок недоступна.\n"
                            "Ключ бесплатный, получить — 2 минуты.",
                            size=14, color=theme.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=24),
                    ft.ElevatedButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.SETTINGS_ROUNDED, size=18,
                                        color=ft.Colors.WHITE),
                                ft.Text("Перейти в настройки", size=14,
                                        color=ft.Colors.WHITE,
                                        weight=ft.FontWeight.BOLD),
                            ],
                            spacing=8, tight=True,
                        ),
                        bgcolor=theme.PRIMARY, on_click=open_settings,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            padding=ft.padding.symmetric(horizontal=24, vertical=14),
                        ),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                tight=True,
            ),
            padding=ft.padding.all(32),
            bgcolor=theme.SURFACE,
            border_radius=20,
            width=540,
            height=None,
        )

        centered_card = ft.Container(
            content=card,
            alignment=ft.alignment.center,
            expand=True,
            bgcolor=ft.Colors.TRANSPARENT,
        )

        main_layer = ft.Container(
            content=centered_card,
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

    # ---------- Стили ----------

    def _render_styles(self) -> None:
        self.styles_grid.controls.clear()
        for style_key, style_info in image_ai.IMAGE_STYLES.items():
            icon, label, sub = STYLE_UI.get(
                style_key, (ft.Icons.IMAGE_ROUNDED, style_info["label"], "")
            )
            self.styles_grid.controls.append(
                self._make_style_card(style_key, icon, label, sub,
                                      is_active=(style_key == self.current_style))
            )

    def _make_style_card(self, style_key, icon, label, sub, is_active):
        if is_active:
            bg = ft.Colors.with_opacity(0.2, theme.PRIMARY)
            border = theme.PRIMARY
            icon_bg = theme.PRIMARY
            icon_c = ft.Colors.WHITE
            title_c = ft.Colors.WHITE
            sub_c = ft.Colors.with_opacity(0.85, theme.PRIMARY)
        else:
            bg = ft.Colors.with_opacity(0.65, theme.SURFACE)
            border = ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY)
            icon_bg = ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY)
            icon_c = theme.TEXT_PRIMARY
            title_c = theme.TEXT_PRIMARY
            sub_c = theme.TEXT_SECONDARY

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, size=20, color=icon_c),
                        width=40, height=40, border_radius=12,
                        bgcolor=icon_bg,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(height=6),
                    ft.Text(label, size=12, weight=ft.FontWeight.BOLD,
                            color=title_c, text_align=ft.TextAlign.CENTER),
                    ft.Text(sub, size=9, color=sub_c,
                            text_align=ft.TextAlign.CENTER, max_lines=1,
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
            on_click=lambda e, k=style_key: self._select_style(k),
            ink=True,
            tooltip=f"{label} — {sub}",
        )

    def _select_style(self, style_key: str) -> None:
        self.current_style = style_key
        self._render_styles()
        try:
            self.page.update()
        except Exception:
            pass

    # ---------- Лента ----------

    def _render_history(self) -> None:
        from ui.message_bubble import set_dynamic_width
        try:
            set_dynamic_width(self.page)
        except Exception:
            pass

        self.messages_list.controls.clear()
        if not self.history:
            self.messages_list.controls.append(self._make_empty_state())
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
                        self._make_date_divider(_fmt_date_header(msg_date))
                    )
                    last_date = msg_date

                if item["role"] == "user":
                    self.messages_list.controls.append(self._make_user_bubble(item))
                else:
                    if item.get("_is_progress"):
                        self.messages_list.controls.append(
                            self._make_progress_bubble(item)
                        )
                    else:
                        self.messages_list.controls.append(self._make_ai_bubble(item))

        try:
            self.page.update()
        except Exception:
            pass

    def _make_date_divider(self, text):
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(text, size=11, color=theme.TEXT_SECONDARY,
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

    def _make_empty_state(self):
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.IMAGE_OUTLINED, size=56,
                            color=ft.Colors.with_opacity(0.25, theme.TEXT_SECONDARY)),
                    ft.Container(height=12),
                    ft.Text("Опиши картинку и нажми Enter",
                            size=15, color=theme.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=6),
                    ft.Text("Например: «замок на скале в тумане на закате»",
                            size=12, color=ft.Colors.with_opacity(0.5, theme.TEXT_SECONDARY),
                            italic=True, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0,
            ),
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(vertical=60), expand=True,
        )

    def _make_user_bubble(self, item):
        from ui.message_bubble import get_dynamic_width
        width = get_dynamic_width()

        time_str = _fmt_time(item.get("timestamp", ""))
        time_widget = ft.Text(
            time_str, size=10,
            color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
            no_wrap=True,
        ) if time_str else ft.Text("", size=1)

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(item.get("prompt", ""), size=14,
                                        color=ft.Colors.WHITE,
                                        selectable=True, no_wrap=False),
                                ft.Container(
                                    content=time_widget,
                                    alignment=ft.alignment.bottom_right,
                                    padding=ft.padding.only(top=4),
                                ),
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

    def _make_ai_bubble(self, item):
        from ui.message_bubble import get_dynamic_width
        width = get_dynamic_width()

        path = item.get("image_path")
        error = item.get("error")
        time_str = _fmt_time(item.get("timestamp", ""))

        if error:
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED,
                                                    size=20, color=theme.DANGER),
                                            ft.Text(error, size=13, color=theme.DANGER,
                                                    selectable=True, no_wrap=False),
                                        ],
                                        spacing=10, tight=True,
                                    ),
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
                            bgcolor=ft.Colors.with_opacity(0.15, theme.DANGER),
                            border=ft.border.all(1, theme.DANGER),
                            border_radius=theme.RADIUS, width=width,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                margin=ft.margin.only(right=20),
            )

        if not path:
            return ft.Container()

        style_ui = STYLE_UI.get(item.get("style_key"), (None, "", ""))
        style_icon = style_ui[0]
        style_label = style_ui[1] if len(style_ui) > 1 else ""

        def open_full(ev):
            self._open_full_image(item)

        def download_image(ev):
            try:
                src = Path(path)
                downloads = Path(os.path.expanduser("~")) / "Downloads"
                downloads.mkdir(parents=True, exist_ok=True)

                prompt_text = (item.get("prompt") or "").strip()
                safe_name = re.sub(r'[^\w\s\-]', '', prompt_text)
                safe_name = re.sub(r'\s+', '_', safe_name)[:40]
                if not safe_name:
                    safe_name = "image"

                ext = src.suffix or ".png"
                dst = downloads / f"{safe_name}{ext}"
                counter = 1
                while dst.exists():
                    dst = downloads / f"{safe_name}_{counter}{ext}"
                    counter += 1

                shutil.copy(src, dst)

                try:
                    os.remove(str(dst) + ":Zone.Identifier")
                except Exception:
                    pass

                self.page.open(ft.SnackBar(
                    content=ft.Text(f"Скачано: {dst.name}"),
                    duration=2500,
                ))
            except Exception as ex:
                print(f"[DOWNLOAD] error: {ex}")
                self.page.open(ft.SnackBar(
                    content=ft.Text(f"Ошибка скачивания: {ex}"),
                    duration=2500,
                ))

        image = ft.Container(
            content=ft.Image(src=path, width=width, height=width,
                             fit=ft.ImageFit.COVER, border_radius=12),
            border_radius=12, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            on_click=open_full, ink=True,
        )

        meta = ft.Row(
            controls=[
                ft.Icon(style_icon, size=12,
                        color=theme.TEXT_SECONDARY) if style_icon else ft.Container(),
                ft.Text(style_label, size=11, color=theme.TEXT_SECONDARY),
                ft.Container(expand=True),
                ft.Text(time_str, size=10,
                        color=theme.TEXT_SECONDARY) if time_str else ft.Container(),
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=14,
                                    color=theme.PRIMARY),
                            ft.Text("Скачать", size=11, color=theme.PRIMARY),
                        ],
                        spacing=4, tight=True,
                    ),
                    on_click=download_image,
                ),
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=14,
                                    color=theme.PRIMARY),
                            ft.Text("Открыть", size=11, color=theme.PRIMARY),
                        ],
                        spacing=4, tight=True,
                    ),
                    on_click=open_full,
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[image, ft.Container(height=6), meta],
                            spacing=0, tight=True,
                        ),
                        padding=ft.padding.all(10),
                        bgcolor=theme.AI_BUBBLE, border_radius=theme.RADIUS,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            margin=ft.margin.only(right=20),
        )

    # ---------- Прогресс-пузырь ----------

    def _make_progress_bubble(self, item):
        from ui.message_bubble import get_dynamic_width
        bubble_width = max(280, get_dynamic_width())

        profile = get_current()
        anim = (profile.gen_animation if profile else "orbit") or "orbit"

        if anim not in ("orbit", "wave", "sparkle", "heartbeat"):
            anim = "orbit"

        icon_box = ft.Container(
            content=ft.Icon(ft.Icons.BRUSH_ROUNDED, size=18, color=ft.Colors.WHITE),
            width=36, height=36, border_radius=10,
            bgcolor=theme.PRIMARY,
            alignment=ft.alignment.center,
        )

        title = ft.Text("Генерация картинки", size=13,
                        weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY)
        dots = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=theme.PRIMARY)
        percent = ft.Text("0%", size=14, weight=ft.FontWeight.BOLD, color=theme.PRIMARY)

        head = ft.Row(
            controls=[
                icon_box,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[title, dots],
                                spacing=4, tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text("Подбираю стиль и детали…", size=11,
                                    color=theme.TEXT_SECONDARY),
                        ],
                        spacing=0, tight=True,
                    ),
                    expand=True,
                    margin=ft.margin.only(left=10),
                ),
                percent,
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        progress_bar = ft.ProgressBar(
            value=0.0,
            bgcolor=ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY),
            color=theme.PRIMARY,
            bar_height=8, border_radius=4,
        )

        item["_progress_bar"] = progress_bar
        item["_progress_text"] = percent
        item["_dots"] = dots

        anim_block: ft.Control

        if anim == "wave":
            waves = []
            for i in range(3):
                w = ft.Container(
                    width=0, height=4,
                    bgcolor=theme.PRIMARY,
                    border_radius=2,
                    opacity=1.0 - i * 0.25,
                )
                waves.append(w)
            anim_block = ft.Container(
                content=ft.Column(
                    controls=waves,
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                ),
                height=120,
                padding=ft.padding.symmetric(horizontal=20, vertical=40),
            )
            item["_waves"] = waves

        elif anim == "sparkle":
            ORBIT_W = max(220, bubble_width - 40)
            ORBIT_H = 120
            CX = ORBIT_W / 2
            CY = ORBIT_H / 2
            N = 8
            RADIUS_MAX = min(CX, CY) * 0.85
            DOT = 8

            canvas = ft.Container(
                width=ORBIT_W, height=ORBIT_H,
                bgcolor=ft.Colors.with_opacity(0.35, theme.SURFACE),
                border_radius=12,
            )

            dots_arr = []
            for i in range(N):
                d = ft.Container(
                    width=DOT, height=DOT,
                    border_radius=DOT // 2,
                    bgcolor=theme.PRIMARY,
                    left=CX - DOT / 2,
                    top=CY - DOT / 2,
                    opacity=0.0,
                )
                dots_arr.append(d)

            center = ft.Container(
                width=14, height=14, border_radius=7,
                bgcolor=theme.PRIMARY,
                left=CX - 7, top=CY - 7,
            )

            stack = ft.Stack(
                controls=[canvas, *dots_arr, center],
                width=ORBIT_W, height=ORBIT_H,
            )
            anim_block = ft.Container(
                content=stack,
                alignment=ft.alignment.center,
                padding=ft.padding.only(top=10, bottom=6),
            )
            item["_sparkle_dots"] = dots_arr
            item["_sparkle_cx"] = CX
            item["_sparkle_cy"] = CY
            item["_sparkle_max"] = RADIUS_MAX
            item["_sparkle_dot"] = DOT

        elif anim == "heartbeat":
            ORBIT_W = max(220, bubble_width - 40)
            ORBIT_H = 120
            N = 40
            bar_w = 3
            gap = (ORBIT_W - N * bar_w) / (N + 1)

            canvas = ft.Container(
                width=ORBIT_W, height=ORBIT_H,
                bgcolor=ft.Colors.with_opacity(0.35, theme.SURFACE),
                border_radius=12,
            )

            bars = []
            for i in range(N):
                b = ft.Container(
                    width=bar_w, height=4,
                    bgcolor=theme.PRIMARY,
                    border_radius=2,
                    left=gap + i * (bar_w + gap),
                    top=ORBIT_H / 2 - 2,
                )
                bars.append(b)

            stack = ft.Stack(
                controls=[canvas, *bars],
                width=ORBIT_W, height=ORBIT_H,
            )
            anim_block = ft.Container(
                content=stack,
                alignment=ft.alignment.center,
                padding=ft.padding.only(top=10, bottom=6),
            )
            item["_hb_bars"] = bars
            item["_hb_h"] = ORBIT_H

        else:  # orbit
            ORBIT_W = max(220, bubble_width - 40)
            ORBIT_H = 120
            RADIUS_X = max(60, ORBIT_W // 3)
            RADIUS_Y = 30
            BALL_SIZE = 18

            canvas = ft.Container(
                width=ORBIT_W, height=ORBIT_H,
                bgcolor=ft.Colors.with_opacity(0.35, theme.SURFACE),
                border_radius=12,
            )
            ball = ft.Container(
                width=BALL_SIZE, height=BALL_SIZE,
                border_radius=BALL_SIZE // 2,
                bgcolor=theme.PRIMARY,
                border=ft.border.all(3, ft.Colors.with_opacity(0.35, theme.PRIMARY)),
            )
            ghost = ft.Container(
                width=BALL_SIZE, height=BALL_SIZE,
                border_radius=BALL_SIZE // 2,
                bgcolor=ft.Colors.with_opacity(0.35, theme.PRIMARY),
            )

            canvas_stack = ft.Stack(
                controls=[canvas, ghost, ball],
                width=ORBIT_W, height=ORBIT_H,
            )
            anim_block = ft.Container(
                content=canvas_stack,
                alignment=ft.alignment.center,
                padding=ft.padding.only(top=10, bottom=6),
            )
            item["_orbit_ball"] = ball
            item["_orbit_ghost"] = ghost
            item["_orbit_w"] = ORBIT_W
            item["_orbit_h"] = ORBIT_H
            item["_orbit_rx"] = RADIUS_X
            item["_orbit_ry"] = RADIUS_Y
            item["_orbit_ball_size"] = BALL_SIZE

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                head,
                                anim_block,
                                ft.Container(height=6),
                                progress_bar,
                            ],
                            spacing=0, tight=True,
                        ),
                        padding=ft.padding.all(14),
                        bgcolor=theme.AI_BUBBLE,
                        border_radius=theme.RADIUS,
                        width=bubble_width,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            margin=ft.margin.only(right=20),
        )

    # ---------- Отправка ----------

    def _handle_send(self, e) -> None:
        """Обработчик Enter и кнопки отправки."""
        if self._stopped:
            return
        if self.is_generating:
            return

        prompt = (self.prompt_field.value or "").strip()
        if not prompt:
            return

        now_iso = datetime.now().isoformat()

        self.history.append({
            "role": "user",
            "prompt": prompt,
            "timestamp": now_iso,
        })

        ai_item = {
            "role": "ai", "prompt": prompt, "style_key": self.current_style,
            "image_path": None, "error": None,
            "timestamp": now_iso,
            "_is_progress": True,
            "_progress_bar": None, "_progress_text": None, "_dots": None,
            "_orbit_ball": None, "_orbit_ghost": None,
            "_orbit_w": None, "_orbit_h": None,
            "_orbit_rx": None, "_orbit_ry": None, "_orbit_ball_size": None,
        }
        self.history.append(ai_item)

        self._render_history()
        self.prompt_field.value = ""
        try:
            self.prompt_field.update()
        except Exception:
            pass

        self.is_generating = True
        self.status_text.value = "⏳ Генерирую..."
        try:
            self.page.update()
        except Exception:
            pass

        style_key = self.current_style
        stop_flag = {"stop": False}

        def _progress_loop():
            start = time.time()
            dots_idx = 0
            dots_seq = [".", "..", "..."]
            angle = 0.0
            wave_phase = 0
            sparkle_phase = 0.0
            heartbeat_phase = 0.0

            while not stop_flag["stop"] and not self._stopped:
                elapsed = time.time() - start
                pct = min(95, int(elapsed * 3.8))

                bar = ai_item.get("_progress_bar")
                txt = ai_item.get("_progress_text")
                dots = ai_item.get("_dots")

                try:
                    if bar is not None:
                        bar.value = pct / 100.0
                    if txt is not None:
                        txt.value = f"{pct}%"
                    if dots is not None:
                        dots.value = dots_seq[dots_idx % 3]
                        dots_idx += 1
                except Exception:
                    pass

                ball = ai_item.get("_orbit_ball")
                ghost = ai_item.get("_orbit_ghost")
                ow = ai_item.get("_orbit_w") or 320
                oh = ai_item.get("_orbit_h") or 120
                rx = ai_item.get("_orbit_rx") or 90
                ry = ai_item.get("_orbit_ry") or 30
                bs = ai_item.get("_orbit_ball_size") or 18

                try:
                    if ball is not None:
                        cx = ow / 2
                        cy = oh / 2
                        ball.left = cx + rx * math.cos(angle) - bs / 2
                        ball.top = cy + ry * math.sin(angle) - bs / 2
                        ball.opacity = 0.85 + 0.15 * (1 + math.sin(angle * 3)) / 2
                    if ghost is not None:
                        cx = ow / 2
                        cy = oh / 2
                        ghost.left = cx + rx * math.cos(angle - 0.35) - bs / 2
                        ghost.top = cy + ry * math.sin(angle - 0.35) - bs / 2
                        ghost.opacity = 0.25 + 0.15 * (1 + math.sin(angle * 2))
                except Exception:
                    pass

                angle += 0.18
                if angle > math.pi * 2:
                    angle -= math.pi * 2

                waves = ai_item.get("_waves")
                if waves:
                    wave_phase += 1
                    for i, w in enumerate(waves):
                        phase = (wave_phase + i * 20) % 100
                        if phase < 50:
                            width = phase * 6
                        else:
                            width = (100 - phase) * 6
                        try:
                            w.width = width
                        except Exception:
                            pass

                sparkle_dots = ai_item.get("_sparkle_dots")
                if sparkle_dots:
                    scx = ai_item.get("_sparkle_cx") or 160
                    scy = ai_item.get("_sparkle_cy") or 60
                    smax = ai_item.get("_sparkle_max") or 60
                    sdot = ai_item.get("_sparkle_dot") or 8
                    sparkle_phase += 0.06
                    for i, d in enumerate(sparkle_dots):
                        t_local = (sparkle_phase + i * 0.5) % 3.0
                        progress = t_local / 3.0
                        r = smax * progress
                        a = (i / len(sparkle_dots)) * math.pi * 2
                        try:
                            d.left = scx + r * math.cos(a) - sdot / 2
                            d.top = scy + r * math.sin(a) - sdot / 2
                            d.opacity = max(0.0, 1.0 - progress)
                        except Exception:
                            pass

                hb_bars = ai_item.get("_hb_bars")
                if hb_bars:
                    hb_h = ai_item.get("_hb_h") or 120
                    heartbeat_phase += 0.25
                    n = len(hb_bars)
                    for i, b in enumerate(hb_bars):
                        x = (i / n) * math.pi * 6 - heartbeat_phase
                        base = 4
                        wave_val = math.sin(x) ** 2
                        if 0.35 < (i / n) < 0.45:
                            wave_val = max(wave_val, 0.9)
                        if 0.6 < (i / n) < 0.7:
                            wave_val = max(wave_val, 0.6)
                        h = base + wave_val * (hb_h * 0.75)
                        try:
                            b.height = h
                            b.top = hb_h / 2 - h / 2
                        except Exception:
                            pass

                # Один общий update — вместо семи отдельных
                try:
                    if not self._stopped:
                        self.page.update()
                except Exception:
                    pass

                time.sleep(0.05)

        def _worker():
            image_bytes, error_msg = image_ai.generate_image(
                prompt, style_key=style_key,
            )

            def _done():
                stop_flag["stop"] = True

                bar = ai_item.get("_progress_bar")
                txt = ai_item.get("_progress_text")
                dots = ai_item.get("_dots")
                ball = ai_item.get("_orbit_ball")
                ghost = ai_item.get("_orbit_ghost")

                try:
                    if bar is not None:
                        bar.value = 1.0
                    if txt is not None:
                        txt.value = "100%"
                    if dots is not None:
                        dots.value = ""
                    if ball is not None:
                        ball.visible = False
                    if ghost is not None:
                        ghost.visible = False
                except Exception:
                    pass

                time.sleep(0.35)

                if not image_bytes:
                    ai_item["error"] = error_msg or "Не удалось сгенерировать"
                else:
                    try:
                        saved = image_storage.save_image(image_bytes, prompt, style_key)
                    except Exception:
                        saved = None
                    if saved:
                        ai_item["image_path"] = saved.full_path()
                    else:
                        ai_item["error"] = "Не удалось сохранить картинку"

                ai_item["timestamp"] = datetime.now().isoformat()
                ai_item["_is_progress"] = False

                _save_history(self.history)

                self.is_generating = False
                self.status_text.value = ""
                if not self._stopped:
                    self._render_history()

            threading.Timer(0, _done).start()

        threading.Thread(target=_progress_loop, daemon=True).start()
        threading.Thread(target=_worker, daemon=True).start()

    def _clear_history(self, e) -> None:
        self.history = []
        _save_history(self.history)
        self._render_history()
        try:
            self.page.open(ft.SnackBar(
                content=ft.Text("История очищена"),
                duration=1500,
            ))
        except Exception:
            pass

    def _open_full_image(self, item):
        path = item.get("image_path")
        if not path:
            return

        def close(ev):
            self.page.close(dialog)

        dialog = ft.AlertDialog(
            modal=True,
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Image(src=path, fit=ft.ImageFit.CONTAIN,
                                 width=520, height=520),
                        ft.Container(height=12),
                        ft.Text(item.get("prompt", ""), size=13,
                                color=theme.TEXT_PRIMARY,
                                text_align=ft.TextAlign.CENTER),
                    ],
                    spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.all(8), width=560,
            ),
            actions=[
                ft.TextButton("Закрыть", on_click=close,
                              style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dialog)