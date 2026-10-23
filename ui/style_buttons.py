"""Компонент выбора стиля — 3 компактные кнопки в одну строку."""

from typing import Callable, Optional

import flet as ft

from ui import theme

STYLES = [
    ("complex", "🎓", "Сложный"),
    ("simple", "💬", "Простой"),
    ("anti_ai", "🥷", "Анти-ИИ"),
]


def create_style_buttons(
    on_change: Callable[[Optional[str]], None],
    current: Optional[str],
) -> ft.Row:
    """Возвращает Row с тремя компактными кнопками в одну строку."""
    buttons: list[ft.Control] = []

    for style_key, icon, label in STYLES:
        is_active = style_key == current

        btn = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(icon, size=18, text_align=ft.TextAlign.CENTER),
                    ft.Text(
                        label,
                        size=11,
                        color=theme.TEXT_PRIMARY if is_active else theme.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=10,
            bgcolor=theme.PRIMARY if is_active else theme.SURFACE,
            border=ft.border.all(
                2,
                theme.PRIMARY if is_active else ft.Colors.TRANSPARENT,
            ),
            on_click=lambda e, key=style_key: on_change(key),
            ink=True,
            expand=True,
        )
        buttons.append(btn)

    return ft.Row(
        controls=buttons,
        spacing=8,
        alignment=ft.MainAxisAlignment.CENTER,
    )