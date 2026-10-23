"""Проверка доступа к Premium-функциям.

Используется во всех экранах, чтобы понять, можно ли показать
пользователю премиум-функцию или нужно заблокировать.

Логика:
  profile.is_premium() → True, если подписка активна.
  Если False → показываем экран блокировки.
"""

from typing import Optional

import flet as ft

from ui import theme


PREMIUM_FEATURES = {
    "content": {
        "title": "Автосоздание контента",
        "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
        "description": "Генерация пачки постов по одной теме. "
                       "Доступно в Премиум и Премиум Плюс.",
    },
    "telegram": {
        "title": "Автопостинг в Telegram",
        "icon": ft.Icons.SEND_ROUNDED,
        "description": "Автоматическая публикация постов в Telegram "
                       "по расписанию. Доступно в Премиум и Премиум Плюс.",
    },
}


def is_premium() -> bool:
    """Проверяет, активна ли Premium-подписка у текущего пользователя."""
    try:
        from services.user_profile import get_current
        profile = get_current()
        if profile is None:
            return False
        if hasattr(profile, "is_premium"):
            return profile.is_premium()
        return bool(getattr(profile, "premium_active", False))
    except Exception:
        return False


def build_locked_screen(page: ft.Page, feature_key: str,
                        on_buy_click, on_close_click) -> ft.Container:
    """Возвращает экран блокировки Premium-функции."""
    info = PREMIUM_FEATURES.get(feature_key, {
        "title": "Премиум-функция",
        "icon": ft.Icons.LOCK_ROUNDED,
        "description": "Эта функция доступна только в Премиум-подписке.",
    })

    icon = info["icon"]
    title = info["title"]
    description = info["description"]

    card = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.LOCK_ROUNDED, size=40,
                        color=ft.Colors.WHITE,
                    ),
                    width=80, height=80, border_radius=24,
                    bgcolor="#FF9800",
                    alignment=ft.alignment.center,
                    shadow=ft.BoxShadow(
                        spread_radius=2,
                        blur_radius=20,
                        color=ft.Colors.with_opacity(0.5, "#FF9800"),
                    ),
                ),
                ft.Container(height=20),
                ft.Row(
                    controls=[
                        ft.Icon(icon, size=20, color=theme.PRIMARY),
                        ft.Text(title, size=20,
                                weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_PRIMARY),
                    ],
                    spacing=10, tight=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(height=10),
                ft.Text(
                    "Эта функция доступна только в Premium",
                    size=14, weight=ft.FontWeight.BOLD,
                    color="#FF9800",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=8),
                ft.Text(
                    description,
                    size=13, color=theme.TEXT_SECONDARY,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=24),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED,
                                            size=16, color="#4CAF50"),
                                    ft.Text("Автосоздание контента", size=13,
                                            color=theme.TEXT_PRIMARY),
                                ],
                                spacing=8, tight=True,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED,
                                            size=16, color="#4CAF50"),
                                    ft.Text("Автопостинг в Telegram", size=13,
                                            color=theme.TEXT_PRIMARY),
                                ],
                                spacing=8, tight=True,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED,
                                            size=16, color="#4CAF50"),
                                    ft.Text("Приоритетная поддержка", size=13,
                                            color=theme.TEXT_PRIMARY),
                                ],
                                spacing=8, tight=True,
                            ),
                        ],
                        spacing=8, tight=True,
                    ),
                    padding=ft.padding.all(14),
                    bgcolor=ft.Colors.with_opacity(0.06, theme.PRIMARY),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.2, theme.PRIMARY)),
                    border_radius=12,
                ),
                ft.Container(height=24),
                ft.ElevatedButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                                    size=18, color=ft.Colors.WHITE),
                            ft.Text("Купить Premium", size=14,
                                    color=ft.Colors.WHITE,
                                    weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8, tight=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    bgcolor=theme.PRIMARY,
                    on_click=on_buy_click,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.padding.symmetric(horizontal=24, vertical=16),
                    ),
                ),
                ft.Container(height=8),
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=14,
                                    color=theme.TEXT_SECONDARY),
                            ft.Text("Вернуться назад", size=12,
                                    color=theme.TEXT_SECONDARY),
                        ],
                        spacing=6, tight=True,
                    ),
                    on_click=on_close_click,
                ),
            ],
            spacing=0, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.all(24),
        bgcolor=theme.SURFACE,
        border_radius=20,
        border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
        width=480,
    )

    return ft.Container(
        content=ft.Container(
            content=card,
            alignment=ft.alignment.center,
            expand=True,
        ),
        expand=True,
        padding=ft.padding.all(24),
    )