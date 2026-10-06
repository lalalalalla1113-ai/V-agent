"""Экран генерации хештегов по теме."""

import threading

import flet as ft

from services import text_ai
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


HASHTAG_STYLES = [
    ("mixed", "🎯 Микс", "широкие + средние + нишевые"),
    ("wide", "🌍 Широкие", "типа #жизнь #утро #счастье"),
    ("medium", "📊 Средние", "типа #утренняяпробежка"),
    ("niche", "🎯 Нишевые", "типа #бегунам"),
]


class HashtagsScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.mobile = self._is_mobile()
        self.is_generating = False
        self.current_style = "mixed"
        self._bg_effect = None
        self._style_chips = []

        self.topic_field = ft.TextField(
            hint_text="Например: утренние пробежки",
            multiline=True, min_lines=1, max_lines=3,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=theme.RADIUS, border_color=theme.SURFACE,
            expand=True,
        )

        self.generate_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TAG_ROUNDED, size=18, color=ft.Colors.WHITE),
                    ft.Text("Сгенерировать", size=14,
                            weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ],
                spacing=8, tight=True,
            ),
            bgcolor=theme.PRIMARY,
            on_click=self._handle_generate,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.padding.symmetric(horizontal=20, vertical=14),
            ),
        )

        self.result_container = ft.Container(
            content=self._build_empty(),
            padding=ft.padding.symmetric(vertical=20),
        )

        self.status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _is_mobile(self):
        try:
            if self.page.platform in ("android", "ios"):
                return True
        except Exception:
            pass
        try:
            w = int(self.page.width or 0)
            return 0 < w < 700
        except Exception:
            return False

    def build(self):
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
            count_scale=count_scale, size_scale=size_scale,
        )
        bg = self._bg_effect.build()
        self._bg_effect.start()

        top_pad = 32 if self.mobile else 0
        bottom_pad = 30 if self.mobile else 0

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TAG_ROUNDED, size=22, color=theme.PRIMARY),
                    ft.Text("Хештеги", size=18,
                            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                ],
                spacing=10, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=20, right=20,
                                    top=top_pad + 14, bottom=14),
        )

        self._style_chips.clear()
        chips = []
        for key, label, _sub in HASHTAG_STYLES:
            is_active = key == self.current_style
            chip = ft.Container(
                content=ft.Text(label, size=12,
                                color=ft.Colors.WHITE if is_active else theme.TEXT_PRIMARY,
                                weight=ft.FontWeight.BOLD),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=12,
                bgcolor=theme.PRIMARY if is_active else theme.SURFACE,
                on_click=lambda e, k=key: self._select_style(k),
                ink=True,
            )
            self._style_chips.append((key, chip))
            chips.append(chip)

        input_row = ft.Container(
            content=ft.Row(
                controls=[self.topic_field, self.generate_btn],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
        )

        content = ft.Column(
            controls=[
                header,
                ft.Container(
                    content=ft.Text("Стиль", size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_SECONDARY),
                    padding=ft.padding.only(left=20, bottom=6),
                ),
                ft.Container(
                    content=ft.Row(controls=chips, spacing=8, wrap=True),
                    padding=ft.padding.symmetric(horizontal=20),
                ),
                ft.Container(
                    content=ft.Text("Тема поста", size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_SECONDARY),
                    padding=ft.padding.only(left=20, top=16, bottom=4),
                ),
                input_row,
                self.status_text,
                ft.Divider(color=ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY)),
                ft.Container(
                    content=self.result_container,
                    padding=ft.padding.symmetric(horizontal=20, vertical=8),
                ),
                ft.Container(height=bottom_pad + 20),
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        main = ft.Container(
            content=content, expand=True,
            bgcolor=ft.Colors.with_opacity(0.6, theme.BG_DARK),
        )
        return ft.Stack(controls=[bg, main], expand=True)

    def stop_effect(self) -> None:
        """Полная остановка — при уходе с экрана."""
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None

    def _build_empty(self):
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.TAG_OUTLINED, size=56,
                            color=ft.Colors.with_opacity(0.25, theme.TEXT_SECONDARY)),
                    ft.Container(height=12),
                    ft.Text("Введи тему — получишь 15 хештегов",
                            size=15, color=theme.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(vertical=40),
        )

    def _select_style(self, key):
        self.current_style = key
        for chip_key, chip in self._style_chips:
            is_active = chip_key == key
            chip.bgcolor = theme.PRIMARY if is_active else theme.SURFACE
            chip.content.color = ft.Colors.WHITE if is_active else theme.TEXT_PRIMARY
        try:
            self.page.update()
        except Exception:
            pass

    def _handle_generate(self, e):
        if self.is_generating:
            return
        topic = (self.topic_field.value or "").strip()
        if not topic:
            self.page.open(ft.SnackBar(content=ft.Text("Введи тему"), duration=1500))
            return

        self.is_generating = True
        self.generate_btn.disabled = True
        self.status_text.value = "⏳ Генерирую..."
        self.status_text.color = theme.TEXT_SECONDARY
        try:
            self.page.update()
        except Exception:
            pass

        def _worker():
            tags = text_ai.generate_hashtags(
                topic, hashtag_style=self.current_style, count=15,
            )

            def _done():
                self.is_generating = False
                self.generate_btn.disabled = False
                self.status_text.value = "✅ Готово"
                self.status_text.color = "#4CAF50"
                self.result_container.content = self._build_result(tags)
                try:
                    self.page.update()
                except Exception:
                    pass

            threading.Timer(0, _done).start()

        threading.Thread(target=_worker, daemon=True).start()

    def _build_result(self, tags_text):
        tags = [t for t in tags_text.split() if t.startswith("#")]
        if not tags:
            return self._build_empty()

        def make_chip(tag: str) -> ft.Container:
            """Чип хештега — при клике копируется в буфер."""
            def copy_one(e, tg=tag):
                try:
                    self.page.set_clipboard(tg)
                    self.page.open(ft.SnackBar(
                        content=ft.Text(f"Скопировано: {tg}"),
                        duration=1200,
                    ))
                except Exception as ex:
                    print(f"[COPY] {ex}")

            return ft.Container(
                content=ft.Text(tag, size=13, color=theme.TEXT_PRIMARY),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                bgcolor=theme.SURFACE,
                border_radius=20,
                on_click=copy_one,
                ink=True,
                tooltip="Нажми, чтобы скопировать",
            )

        chips = [make_chip(t) for t in tags]

        def copy_all(e):
            try:
                self.page.set_clipboard(" ".join(tags))
                self.page.open(ft.SnackBar(
                    content=ft.Text("Все хештеги скопированы"),
                    duration=1500,
                ))
            except Exception as ex:
                print(f"[COPY ALL] {ex}")

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(f"{len(tags)} хештегов", size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY),
                            ft.Container(expand=True),
                            ft.TextButton("Скопировать все", on_click=copy_all,
                                          style=ft.ButtonStyle(color=theme.PRIMARY)),
                        ],
                    ),
                    ft.Container(height=12),
                    ft.Row(controls=chips, wrap=True, spacing=8, run_spacing=8),
                ],
                spacing=0,
            ),
            padding=ft.padding.symmetric(vertical=8),
        )