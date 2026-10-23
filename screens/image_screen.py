"""Экран генерации картинок через Cloudflare.

История привязана к текущему проекту (tab_id="image").
Кнопка «Новый чат» создаёт новый проект — прошлые видны в панели проектов.

Кнопка «Редактировать» под картинкой:
  • Подставляет актуальный промпт обратно в поле ввода.
  • Ты дописываешь изменение и жмёшь Enter.
  • Создаётся НОВОЕ сообщение с новой картинкой внизу.
  • Старая картинка остаётся выше в истории — можно листать.

Enter — отправить, Shift+Enter — новая строка.
В пустом чате — анимированный текст.
"""

import math
import os
import re
import shutil
import threading
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import flet as ft

from services import image_ai, image_storage, storage
from services.models import Message
from services.user_profile import get_current
from state import state
from ui import theme
from ui.effects import create_effect

_IMG_TYPING_TEXT = "V-Agent - твой помощник в генерации картинок"
_IMG_TYPING_SPEED = 0.06

STYLE_UI = {
    "photo": (ft.Icons.PHOTO_CAMERA_ROUNDED, "Реализм", "как фото"),
    "anime": (ft.Icons.AUTO_AWESOME_ROUNDED, "Аниме", "Studio Ghibli"),
    "3d": (ft.Icons.VIEW_IN_AR_ROUNDED, "3D", "Pixar / Unreal"),
    "cyberpunk": (ft.Icons.LOCATION_CITY_ROUNDED, "Киберпанк", "neon city"),
    "fantasy": (ft.Icons.AUTO_FIX_HIGH_ROUNDED, "Фэнтези", "epic fantasy"),
    "sketch": (ft.Icons.EDIT_ROUNDED, "Скетч", "pencil"),
    "minimal": (ft.Icons.CROP_SQUARE_ROUNDED, "Минимализм", "flat vector"),
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


class ImageScreen:
    def __init__(self, page: ft.Page, on_open_settings=None) -> None:
        self.page = page
        self.on_open_settings = on_open_settings
        self.mobile = _is_mobile(page)

        self.current_style = "photo"
        self.is_generating = False

        self._editing_msg_id: Optional[str] = None

        self._typing_alive = False
        self._typing_text_widget: Optional[ft.Text] = None
        self._typing_thread: Optional[threading.Thread] = None

        self._ensure_image_project()

        self.prompt_field = ft.TextField(
            hint_text="Опиши картинку...",
            multiline=True,
            min_lines=1,
            max_lines=6,
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=theme.RADIUS,
            border_color=theme.SURFACE,
            expand=True,
            shift_enter=True,
            on_submit=self._handle_send,
        )

        self.send_btn = ft.Container(
            content=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED,
                            size=20, color=ft.Colors.WHITE),
            width=48, height=48,
            bgcolor=theme.PRIMARY,
            border_radius=12,
            alignment=ft.alignment.center,
            on_click=self._handle_send,
            ink=True,
            tooltip="Сгенерировать (Enter)",
        )

        self.editing_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.EDIT_ROUNDED, size=12, color=ft.Colors.WHITE),
                    ft.Text("Режим редактирования", size=11,
                            color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED, icon_size=12,
                        icon_color=ft.Colors.WHITE,
                        tooltip="Отменить редактирование",
                        on_click=self._cancel_edit,
                    ),
                ],
                spacing=6, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=10, right=2),
            bgcolor=theme.PRIMARY,
            border_radius=8,
            visible=False,
            margin=ft.margin.only(bottom=6),
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
        self._render_messages()

    # ------------------------------------------------------------------
    # Premium
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
            print(f"[IMAGE] open subscription error: {ex}")

    # ------------------------------------------------------------------
    # Проекты
    # ------------------------------------------------------------------

    def _ensure_image_project(self) -> None:
        proj = state.current_project
        if proj is not None and getattr(proj, "tab_id", "chat") == "image":
            return
        try:
            projects = storage.list_projects()
        except Exception:
            projects = []
        image_projects = [p for p in projects
                          if getattr(p, "tab_id", "chat") == "image"]
        if image_projects:
            state.current_project = image_projects[0]
        else:
            new_proj = storage.create_project(
                first_message_text="Генерация картинок",
                tab_id="image",
            )
            state.current_project = new_proj

    def _handle_new_chat(self, e) -> None:
        self.is_generating = False
        self._cancel_edit(None)
        self._stop_typing_animation()
        new_proj = storage.create_project(
            first_message_text="Новый чат картинок",
            tab_id="image",
        )
        state.current_project = new_proj
        self._render_messages()
        try:
            self.page.update()
        except Exception:
            pass

    def _make_new_chat_button(self) -> ft.Container:
        # ПРОВЕРКА НА ПУСТОТУ
        is_disabled = False
        if state.current_project and len(state.current_project.messages) == 0:
            is_disabled = True

        bg_color = theme.SURFACE if is_disabled else theme.PRIMARY
        text_color = theme.TEXT_MUTED if is_disabled else ft.Colors.WHITE
        icon_color = theme.TEXT_MUTED if is_disabled else ft.Colors.WHITE

        def on_click(e):
            if is_disabled:
                return
            self._handle_new_chat(e)

        return ft.Container(
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
            on_click=on_click,
            ink=not is_disabled,
            tooltip="Создать новый чат" if not is_disabled else "Чат уже пуст",
        )

    # ------------------------------------------------------------------
    # Жизненный цикл
    # ------------------------------------------------------------------

    def _has_cf_token(self) -> bool:
        try:
            from services import cf_config
            account, token = cf_config.get_cf_credentials()
            return bool(account and token)
        except Exception:
            return False

    def stop_effect(self) -> None:
        self._stopped = True
        self._stop_typing_animation()
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None
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
        self._stopped = False

    # ------------------------------------------------------------------
    # Построение
    # ------------------------------------------------------------------

    def build(self) -> ft.Container:
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

        premium_btn = self._make_premium_button()
        new_chat_btn = self._make_new_chat_button()

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.BRUSH_ROUNDED, size=22, color=theme.PRIMARY),
                    ft.Text("Генерация картинок", size=18,
                            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    premium_btn,
                    ft.Container(width=8),
                    new_chat_btn,
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
            padding=ft.padding.only(left=24, right=24, top=8, bottom=8),
        )

        input_row = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[self.prompt_field, self.send_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "Enter — отправить · Shift+Enter — новая строка",
                            size=10,
                            color=theme.TEXT_MUTED,
                            text_align=ft.TextAlign.RIGHT,
                        ),
                        padding=ft.padding.only(right=8, top=2),
                    ),
                ],
                spacing=2,
                tight=True,
            ),
            padding=ft.padding.only(left=24, right=24, top=10, bottom=6),
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
        self._prev_keyboard_handler = getattr(self.page, "on_keyboard_event", None)

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

    # ------------------------------------------------------------------
    # Стили
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Лента сообщений
    # ------------------------------------------------------------------

    def _messages_from_project(self) -> list:
        proj = state.current_project
        if proj is None or not proj.messages:
            return []

        items = []
        for m in proj.messages:
            attachments = getattr(m, "attachments", []) or []
            image_path = ""
            for a in attachments:
                p = Path(a)
                if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                    image_path = str(p)
                    break

            items.append({
                "id": m.timestamp,
                "role": m.role,
                "prompt": m.text,
                "style_key": getattr(m, "style", "") or "photo",
                "image_path": image_path,
                "error": "",
                "timestamp": m.timestamp,
            })
        return items

    def _render_messages(self) -> None:
        from ui.message_bubble import set_dynamic_width
        try:
            set_dynamic_width(self.page)
        except Exception:
            pass

        self.messages_list.controls.clear()
        items = self._messages_from_project()

        if not items:
            self._start_typing_animation()
            try:
                self.page.update()
            except Exception:
                pass
            return

        self._stop_typing_animation()

        last_date = None
        for item in items:
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
        prompt = item.get("prompt", "")
        style_key = item.get("style_key", "photo")
        msg_id = item.get("id", "")

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

        style_ui = STYLE_UI.get(style_key, (None, "", ""))
        style_icon = style_ui[0]
        style_label = style_ui[1] if len(style_ui) > 1 else ""

        def open_full(ev):
            self._open_full_image(item)

        def download_image(ev):
            try:
                src = Path(path)
                downloads = Path(os.path.expanduser("~")) / "Downloads"
                downloads.mkdir(parents=True, exist_ok=True)

                prompt_text = (prompt or "").strip()
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

        def edit_image(ev):
            self._editing_msg_id = msg_id
            self.prompt_field.value = prompt
            if style_key in image_ai.IMAGE_STYLES:
                self.current_style = style_key
                self._render_styles()

            self.editing_badge.visible = True
            try:
                self.editing_badge.update()
            except Exception:
                pass

            try:
                self.prompt_field.focus()
                self.prompt_field.update()
            except Exception:
                pass

            self.page.open(ft.SnackBar(
                content=ft.Text(
                    "Допиши, что изменить — и Enter. "
                    "Новая картинка появится ниже."
                ),
                duration=3000,
                bgcolor=theme.PRIMARY,
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
                            ft.Icon(ft.Icons.EDIT_ROUNDED, size=14,
                                    color=theme.PRIMARY),
                            ft.Text("Редактировать", size=11, color=theme.PRIMARY),
                        ],
                        spacing=4, tight=True,
                    ),
                    on_click=edit_image,
                    tooltip="Дописать промпт и сгенерировать заново",
                ),
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

    # ------------------------------------------------------------------
    # Режим редактирования
    # ------------------------------------------------------------------

    def _cancel_edit(self, e) -> None:
        self._editing_msg_id = None
        self.editing_badge.visible = False
        self.prompt_field.value = ""
        try:
            self.editing_badge.update()
            self.prompt_field.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Анимация печати в пустом чате
    # ------------------------------------------------------------------

    def _start_typing_animation(self) -> None:
        self._stop_typing_animation()

        text_widget = ft.Text(
            "",
            size=34,
            weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY,
            text_align=ft.TextAlign.CENTER,
        )
        self._typing_text_widget = text_widget
        self._typing_alive = True

        self.messages_list.controls.clear()
        self.messages_list.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        text_widget,
                        ft.Container(
                            content=ft.Text(
                                "Опиши картинку ниже, чтобы начать",
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
                padding=ft.padding.symmetric(vertical=180),
            )
        )
        try:
            self.page.update()
        except Exception:
            pass

        def _loop():
            for i in range(len(_IMG_TYPING_TEXT) + 1):
                if not self._typing_alive:
                    return
                try:
                    text_widget.value = _IMG_TYPING_TEXT[:i]
                    text_widget.update()
                except Exception:
                    pass
                time.sleep(_IMG_TYPING_SPEED)

        t = threading.Thread(target=_loop, daemon=True)
        self._typing_thread = t
        t.start()

    def _stop_typing_animation(self) -> None:
        self._typing_alive = False
        self._typing_thread = None
        self._typing_text_widget = None

    # ------------------------------------------------------------------
    # Прогресс
    # ------------------------------------------------------------------

    def _make_progress_bubble(self):
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

        anim_block: ft.Control
        extras = {}

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
            extras["waves"] = waves

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
            extras["sparkle_dots"] = dots_arr
            extras["sparkle_cx"] = CX
            extras["sparkle_cy"] = CY
            extras["sparkle_max"] = RADIUS_MAX
            extras["sparkle_dot"] = DOT

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
            extras["hb_bars"] = bars
            extras["hb_h"] = ORBIT_H

        else:
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
            extras["orbit_ball"] = ball
            extras["orbit_ghost"] = ghost
            extras["orbit_w"] = ORBIT_W
            extras["orbit_h"] = ORBIT_H
            extras["orbit_rx"] = RADIUS_X
            extras["orbit_ry"] = RADIUS_Y
            extras["orbit_ball_size"] = BALL_SIZE

        widget = ft.Container(
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

        return widget, {
            "progress_bar": progress_bar,
            "progress_text": percent,
            "dots": dots,
            **extras,
        }

    # ------------------------------------------------------------------
    # Отправка
    # ------------------------------------------------------------------

    def _handle_send(self, e) -> None:
        if self._stopped:
            return
        if self.is_generating:
            return

        prompt = (self.prompt_field.value or "").strip()
        if not prompt:
            return

        self._stop_typing_animation()

        self._ensure_image_project()
        proj = state.current_project
        if proj is None:
            return

        user_msg = Message(
            role="user",
            text=prompt,
            style=self.current_style,
        )
        state.append_message(user_msg)

        self._render_messages()
        self.prompt_field.value = ""
        self._editing_msg_id = None
        self.editing_badge.visible = False
        try:
            self.prompt_field.update()
            self.editing_badge.update()
        except Exception:
            pass

        self.is_generating = True
        self.status_text.value = "⏳ Генерирую..."
        try:
            self.page.update()
        except Exception:
            pass

        progress_widget, refs = self._make_progress_bubble()
        self.messages_list.controls.append(progress_widget)
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

                bar = refs.get("progress_bar")
                txt = refs.get("progress_text")
                dots = refs.get("dots")

                try:
                    if bar is not None:
                        bar.value = pct / 100.0
                        bar.update()
                    if txt is not None:
                        txt.value = f"{pct}%"
                        txt.update()
                    if dots is not None:
                        dots.value = dots_seq[dots_idx % 3]
                        dots.update()
                        dots_idx += 1
                except Exception:
                    pass

                ball = refs.get("orbit_ball")
                ghost = refs.get("orbit_ghost")
                if ball is not None:
                    ow = refs.get("orbit_w") or 320
                    oh = refs.get("orbit_h") or 120
                    rx = refs.get("orbit_rx") or 90
                    ry = refs.get("orbit_ry") or 30
                    bs = refs.get("orbit_ball_size") or 18
                    try:
                        cx = ow / 2
                        cy = oh / 2
                        ball.left = cx + rx * math.cos(angle) - bs / 2
                        ball.top = cy + ry * math.sin(angle) - bs / 2
                        ball.opacity = 0.85 + 0.15 * (1 + math.sin(angle * 3)) / 2
                        ball.update()
                        if ghost is not None:
                            ghost.left = cx + rx * math.cos(angle - 0.35) - bs / 2
                            ghost.top = cy + ry * math.sin(angle - 0.35) - bs / 2
                            ghost.opacity = 0.25 + 0.15 * (1 + math.sin(angle * 2))
                            ghost.update()
                    except Exception:
                        pass

                angle += 0.18
                if angle > math.pi * 2:
                    angle -= math.pi * 2

                waves = refs.get("waves")
                if waves:
                    wave_phase += 1
                    for i, w in enumerate(waves):
                        phase = (wave_phase + i * 20) % 100
                        width = phase * 6 if phase < 50 else (100 - phase) * 6
                        try:
                            w.width = width
                            w.update()
                        except Exception:
                            pass

                sparkle_dots = refs.get("sparkle_dots")
                if sparkle_dots:
                    scx = refs.get("sparkle_cx") or 160
                    scy = refs.get("sparkle_cy") or 60
                    smax = refs.get("sparkle_max") or 60
                    sdot = refs.get("sparkle_dot") or 8
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
                            d.update()
                        except Exception:
                            pass

                hb_bars = refs.get("hb_bars")
                if hb_bars:
                    hb_h = refs.get("hb_h") or 120
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
                            b.update()
                        except Exception:
                            pass

                time.sleep(0.05)

        def _worker():
            image_bytes, error_msg = image_ai.generate_image(
                prompt, style_key=style_key,
            )

            def _done():
                stop_flag["stop"] = True
                self.is_generating = False
                self.status_text.value = ""

                try:
                    if progress_widget in self.messages_list.controls:
                        self.messages_list.controls.remove(progress_widget)
                except Exception:
                    pass

                if not image_bytes:
                    err_text = error_msg or "Не удалось сгенерировать картинку"
                    ai_msg = Message(
                        role="assistant",
                        text=err_text,
                        style=style_key,
                    )
                    state.append_message(ai_msg)
                else:
                    try:
                        saved = image_storage.save_image(image_bytes, prompt, style_key)
                    except Exception:
                        saved = None

                    if saved:
                        ai_msg = Message(
                            role="assistant",
                            text=prompt,
                            style=style_key,
                            attachments=[saved.full_path()],
                        )
                        state.append_message(ai_msg)
                    else:
                        ai_msg = Message(
                            role="assistant",
                            text="Не удалось сохранить картинку",
                            style=style_key,
                        )
                        state.append_message(ai_msg)

                self._render_messages()

            threading.Timer(0, _done).start()

        threading.Thread(target=_progress_loop, daemon=True).start()
        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Просмотр
    # ------------------------------------------------------------------

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