"""Заглушки для будущих чатов.

build_stub_screen — общая заготовка.
"""

import flet as ft

from ui import theme


def build_stub_screen(title: str, subtitle: str, icon: str) -> ft.Container:
    """Стандартная заглушка для чата."""
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(expand=True),
                ft.Icon(icon, size=64, color=theme.PRIMARY),
                ft.Container(height=16),
                ft.Text(
                    title,
                    size=24,
                    weight=ft.FontWeight.BOLD,
                    color=theme.TEXT_PRIMARY,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=8),
                ft.Text(
                    subtitle,
                    size=14,
                    color=theme.TEXT_SECONDARY,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=8),
                ft.Text(
                    "Скоро будет доступно",
                    size=12,
                    italic=True,
                    color=theme.TEXT_SECONDARY,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(expand=True),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        ),
        alignment=ft.alignment.center,
        padding=ft.padding.all(24),
        expand=True,
    )


def screen_templates() -> ft.Container:
    return build_stub_screen(
        title="Шаблоны",
        subtitle="Готовые шаблоны постов: инструкция, обзор, 10 фактов",
        icon=ft.Icons.GRID_VIEW_ROUNDED,
    )


def screen_ideas() -> ft.Container:
    return build_stub_screen(
        title="Идеи для постов",
        subtitle="Сгенерирует 10 идей по твоей теме",
        icon=ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
    )