"""Экран профиля."""

import shutil
from pathlib import Path
from typing import Callable

import flet as ft

from services import storage
from services.user_profile import (
    UserProfile,
    get_current,
    get_avatar_path,
)
from ui import theme


STICKERS = [
    "🐱", "🐶", "🦊", "🐼", "🐨", "🐯", "🦁", "🐸",
    "🦄", "🐧", "🐙", "🐝", "🌸", "🌈", "⚡", "⭐",
    "🎨", "🎵", "🚀", "💎", "🔥", "✨", "🦋", "🍀",
]


class ProfileScreen:
    def __init__(self, page: ft.Page, on_edit_profile: Callable[[], None]) -> None:
        self.page = page
        self.on_edit_profile = on_edit_profile

        self.avatar_picker = ft.FilePicker(on_result=self._on_avatar_picked)
        try:
            self.page.overlay.append(self.avatar_picker)
        except Exception:
            pass

        self.avatar_container = ft.Container()
        self.nick_container = ft.Container()
        self.subtitle_container = ft.Container()
        self.stats_container = ft.Container()
        self.interests_container = ft.Container()
        self.audience_container = ft.Container()

        self._parent_container = ft.Container()
        self._current_dialog = None

    def build(self) -> ft.Container:
        profile = get_current()
        if not profile:
            return ft.Container(
                content=ft.Text("Профиль не найден", color=theme.TEXT_PRIMARY),
                alignment=ft.alignment.center, expand=True,
            )

        self._refresh_all()

        logo_header = ft.Container(
            content=ft.Image(
                src="logo_text.webp",
                width=200, height=60, fit=ft.ImageFit.CONTAIN,
            ),
            alignment=ft.alignment.center,
        )

        cf_status_text = (
            "✅ Ключ подключён" if profile.cf_token else "⚠️ Ключ не задан"
        )
        cf_status_color = "#4CAF50" if profile.cf_token else "#FF9800"

        cf_key_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.CLOUD_ROUNDED, size=22,
                                        color=theme.PRIMARY),
                        width=44, height=44,
                        bgcolor=ft.Colors.with_opacity(0.15, theme.PRIMARY),
                        border_radius=12, alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Cloudflare ключ", size=16,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text(cf_status_text, size=12,
                                        color=cf_status_color),
                            ],
                            spacing=2, tight=True,
                        ),
                        expand=True, margin=ft.margin.only(left=16),
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=20,
                            color=theme.TEXT_SECONDARY),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            bgcolor=theme.SURFACE, border_radius=14,
            ink=True,
        )

        edit_button = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.EDIT_ROUNDED, size=18, color=ft.Colors.WHITE),
                    ft.Text("Редактировать профиль", size=14,
                            color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                ],
                spacing=8, tight=True,
            ),
            bgcolor=theme.PRIMARY,
            on_click=lambda e: self.on_edit_profile(),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.padding.symmetric(horizontal=24, vertical=14),
            ),
        )

        content = ft.Column(
            controls=[
                ft.Container(height=16),
                logo_header,
                ft.Container(height=16),
                self.avatar_container,
                ft.Container(height=16),
                self.nick_container,
                self.subtitle_container,
                ft.Container(height=24),
                self.stats_container,
                ft.Container(height=24),
                self.interests_container,
                self.audience_container,
                ft.Container(height=24),
                cf_key_card,
                ft.Container(height=24),
                ft.Container(content=edit_button, alignment=ft.alignment.center),
                ft.Container(height=32),
            ],
            spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self._parent_container.content = ft.Container(
            content=ft.Container(
                content=ft.Column(
                    controls=[content], scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=24), width=520,
            ),
            alignment=ft.alignment.top_center,
            padding=ft.padding.all(16), expand=True,
        )
        return self._parent_container

    def _refresh_all(self) -> None:
        profile = get_current()
        if not profile:
            return
        self._render_avatar(profile)
        self._render_nick(profile)
        self._render_stats(profile)
        self._render_interests(profile)
        self._render_audience(profile)

    def _render_avatar(self, profile: UserProfile) -> None:
        if profile.has_photo_avatar():
            inner = ft.Image(src=get_avatar_path(), width=120, height=120,
                             fit=ft.ImageFit.COVER)
        elif profile.avatar_sticker:
            inner = ft.Text(profile.avatar_sticker, size=64,
                            text_align=ft.TextAlign.CENTER)
        else:
            letter = (profile.name or "?").strip()[:1].upper()
            inner = ft.Text(letter, size=52, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER)

        avatar = ft.Container(
            content=ft.Container(content=inner, alignment=ft.alignment.center),
            width=120, height=120, border_radius=60,
            bgcolor=theme.PRIMARY if not profile.has_photo_avatar() else None,
            border=ft.border.all(3, theme.PRIMARY),
            alignment=ft.alignment.center,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            on_click=lambda e: self._open_avatar_menu(),
            ink=True, tooltip="Сменить аватарку",
        )

        edit_badge = ft.Container(
            content=ft.Icon(ft.Icons.EDIT_ROUNDED, size=14,
                            color=ft.Colors.WHITE),
            width=32, height=32, bgcolor=theme.PRIMARY, border_radius=16,
            alignment=ft.alignment.center,
            border=ft.border.all(2, theme.BG_DARK),
            on_click=lambda e: self._open_avatar_menu(),
            ink=True, tooltip="Сменить аватарку",
        )

        stack = ft.Stack(
            controls=[
                avatar,
                ft.Container(
                    content=edit_badge,
                    alignment=ft.alignment.bottom_right,
                    padding=ft.padding.only(right=2, bottom=2),
                ),
            ],
            width=120, height=120,
        )
        self.avatar_container.content = stack

    def _render_nick(self, profile: UserProfile) -> None:
        self.nick_container.content = ft.Text(
            profile.name or "Без имени", size=24,
            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY,
            text_align=ft.TextAlign.CENTER,
        )
        parts = []
        if profile.age:
            parts.append(f"{profile.age} лет")
        if profile.gender == "male":
            parts.append("мужчина")
        elif profile.gender == "female":
            parts.append("женщина")

        if parts:
            self.subtitle_container.content = ft.Container(
                content=ft.Text(" · ".join(parts), size=13,
                                color=theme.TEXT_SECONDARY,
                                text_align=ft.TextAlign.CENTER),
                padding=ft.padding.only(top=4),
            )
        else:
            self.subtitle_container.content = ft.Container()

    def _render_stats(self, profile: UserProfile) -> None:
        try:
            projects_count = len(storage.list_projects())
        except Exception:
            projects_count = 0
        total_messages = 0
        try:
            for p in storage.list_projects():
                total_messages += len(p.messages)
        except Exception:
            total_messages = 0
        days = profile.days_since_registration()

        def stat_card(icon, value, label):
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(icon, size=20, color=theme.PRIMARY),
                        ft.Container(height=4),
                        ft.Text(value, size=20, weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_PRIMARY),
                        ft.Text(label, size=11, color=theme.TEXT_SECONDARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                bgcolor=theme.SURFACE, border_radius=14,
                expand=True, alignment=ft.alignment.center,
            )

        self.stats_container.content = ft.Row(
            controls=[
                stat_card(ft.Icons.FOLDER_ROUNDED, str(projects_count),
                          "Проектов"),
                ft.Container(width=8),
                stat_card(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                          str(total_messages), "Сообщений"),
                ft.Container(width=8),
                stat_card(ft.Icons.CALENDAR_MONTH_ROUNDED, str(days), "Дней"),
            ],
            spacing=0,
        )

    def _render_interests(self, profile: UserProfile) -> None:
        if not profile.interests:
            self.interests_container.content = ft.Container()
            return
        INTEREST_MAP = {
            "tech": "📱 Технологии", "sport": "💪 Спорт",
            "food": "🍳 Кулинария", "travel": "✈️ Путешествия",
            "games": "🎮 Игры", "art": "🎨 Искусство",
            "books": "📚 Книги", "music": "🎵 Музыка",
            "business": "💼 Бизнес", "selfdev": "🌱 Саморазвитие",
            "mom": "👶 Материнство", "pets": "🐾 Питомцы",
            "cinema": "🎬 Кино", "photo": "📸 Фотография", "auto": "🚗 Авто",
        }
        chips = []
        for key in profile.interests:
            label = INTEREST_MAP.get(key, key)
            chips.append(ft.Container(
                content=ft.Text(label, size=12, color=theme.TEXT_PRIMARY),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                bgcolor=theme.SURFACE, border_radius=20,
            ))
        self.interests_container.content = ft.Column(
            controls=[
                ft.Text("Интересы", size=14, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY),
                ft.Container(height=8),
                ft.Row(controls=chips, wrap=True, spacing=8, run_spacing=8),
            ],
            spacing=0, horizontal_alignment=ft.CrossAxisAlignment.START,
        )

    def _render_audience(self, profile: UserProfile) -> None:
        if not profile.audience.strip():
            self.audience_container.content = ft.Container()
            return
        self.audience_container.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Аудитория", size=14, weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_PRIMARY),
                    ft.Container(height=8),
                    ft.Container(
                        content=ft.Text(profile.audience, size=13,
                                        color=theme.TEXT_PRIMARY),
                        padding=ft.padding.all(12),
                        bgcolor=theme.SURFACE, border_radius=12,
                    ),
                ],
                spacing=0, horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.padding.only(top=16),
        )

    # ---------- Меню аватарки ----------

    def _open_avatar_menu(self) -> None:
        def close(ev):
            self._close_dialog()

        def upload_photo(ev):
            self._close_dialog()
            import threading
            def _pick():
                try:
                    self.avatar_picker.pick_files(
                        allow_multiple=False,
                        allowed_extensions=["png", "jpg", "jpeg", "webp"],
                    )
                except Exception as ex:
                    print(f"[AVATAR] pick error: {ex}")
            threading.Timer(0.2, _pick).start()

        def pick_sticker(ev):
            self._close_dialog()
            import threading
            threading.Timer(0.2, self._open_sticker_chooser).start()

        def remove_avatar(ev):
            self._close_dialog()
            profile = get_current()
            if profile:
                profile.avatar_sticker = ""
                profile.save()
                av = get_avatar_path()
                if Path(av).exists():
                    Path(av).unlink()
                self._refresh_after_avatar()

        dialog = ft.AlertDialog(modal=True)
        dialog.title = ft.Text("Сменить аватарку")
        dialog.content = ft.Column(
            controls=[
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=20),
                            ft.Text("Загрузить фото", size=14),
                        ],
                        spacing=10,
                    ),
                    on_click=upload_photo,
                ),
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.EMOJI_EMOTIONS_ROUNDED, size=20),
                            ft.Text("Выбрать стикер", size=14),
                        ],
                        spacing=10,
                    ),
                    on_click=pick_sticker,
                ),
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, size=20),
                            ft.Text("Удалить аватарку", size=14),
                        ],
                        spacing=10,
                    ),
                    on_click=remove_avatar,
                ),
            ],
            spacing=4, tight=True,
        )
        dialog.actions = [
            ft.TextButton("Отмена", on_click=close,
                          style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
        ]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        self._current_dialog = dialog
        self.page.open(dialog)
        try:
            self.page.update()
        except Exception:
            pass

    def _close_dialog(self) -> None:
        if self._current_dialog is not None:
            try:
                self.page.close(self._current_dialog)
            except Exception:
                pass
            self._current_dialog = None
            try:
                self.page.update()
            except Exception:
                pass

    def _open_sticker_chooser(self) -> None:
        def close(ev):
            self._close_dialog()

        def pick_sticker(sticker: str) -> None:
            profile = get_current()
            if profile:
                av = get_avatar_path()
                if Path(av).exists():
                    Path(av).unlink()
                profile.avatar_sticker = sticker
                profile.save()
            self._close_dialog()
            self._refresh_after_avatar()

        stickers_grid = []
        for s in STICKERS:
            stickers_grid.append(ft.Container(
                content=ft.Text(s, size=32, text_align=ft.TextAlign.CENTER),
                width=64, height=64, bgcolor=theme.SURFACE,
                border_radius=12, alignment=ft.alignment.center,
                on_click=lambda e, st=s: pick_sticker(st), ink=True,
            ))

        dialog = ft.AlertDialog(modal=True)
        dialog.title = ft.Text("Выбери стикер")
        dialog.content = ft.Container(
            content=ft.Row(
                controls=stickers_grid, wrap=True, spacing=8,
                run_spacing=8, alignment=ft.MainAxisAlignment.CENTER,
            ),
            width=420, padding=ft.padding.all(8),
        )
        dialog.actions = [
            ft.TextButton("Отмена", on_click=close,
                          style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
        ]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        self._current_dialog = dialog
        self.page.open(dialog)
        try:
            self.page.update()
        except Exception:
            pass

    def _on_avatar_picked(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        src = Path(e.files[0].path)
        if not src.exists():
            return
        dest = Path(get_avatar_path())
        try:
            shutil.copy(src, dest)
        except Exception as ex:
            print(f"Ошибка копирования аватарки: {ex}")
            return
        profile = get_current()
        if profile:
            profile.avatar_sticker = ""
            profile.save()
        self._refresh_after_avatar()

    def _refresh_after_avatar(self) -> None:
        profile = get_current()
        if not profile:
            return
        self._render_avatar(profile)
        try:
            self.page.update()
        except Exception:
            pass