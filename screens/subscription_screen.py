"""Экран платной подписки V-AGENT.

Три тарифа:
  • Free — бесплатный (базовый доступ)
  • Премиум — от 199 ₽
  • Премиум Плюс — от 299 ₽

Логика бейджей:
  • ТЕКУЩИЙ — тариф, который уже активен (по профилю).
  • ВЫБРАНО — тариф, который пользователь выбрал в UI.
  • Если выбранный совпадает с текущим — показываем только ТЕКУЩИЙ.

Пользователь выбирает тариф → выбирает срок → попадает на FunPay.
"""

import os
import webbrowser
from typing import Optional

import flet as ft

from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


FUNPAY_URLS = {
    "premium": {
        "month": "https://funpay.com/lots/offer?id=79612930",
        "3months": "https://funpay.com/lots/offer?id=79612995",
        "year": "https://funpay.com/lots/offer?id=79613080",
        "forever": "https://funpay.com/lots/offer?id=79613394",
    },
    "premium_plus": {
        "month": "https://funpay.com/lots/offer?id=79613185",
        "3months": "https://funpay.com/lots/offer?id=79613233",
        "year": "https://funpay.com/lots/offer?id=79613267",
        "forever": "https://funpay.com/lots/offer?id=79613329",
    },
}


ALL_FEATURES = [
    "Безлимитные посты через ИИ",
    "12 стилей текста",
    "Генерация картинок",
    "7 стилей изображений",
    "Хештеги и шаблоны",
    "Свой ключ Cloudflare",
    "Автосоздание контента",
    "Автопостинг в Telegram",
    "10 идей за раз в одном запросе",
    "Приоритетная поддержка 24/7",
    "Ранний доступ к новым функциям",
]

FREE_MASK    = [True,  True,  True,  True,  True,  True,  False, False, False, False, False]
PREMIUM_MASK = [True,  True,  True,  True,  True,  True,  True,  True,  False, False, False]
PLUS_MASK    = [True,  True,  True,  True,  True,  True,  True,  True,  True,  True,  True]


PLANS = [
    {
        "id": "free",
        "title": "Free",
        "icon": ft.Icons.PERSON_ROUNDED,
        "color": "#9E9E9E",
        "from_price": "0 ₽",
        "short": "Базовый доступ",
        "features_mask": FREE_MASK,
        "periods": [],
    },
    {
        "id": "premium",
        "title": "Премиум",
        "icon": ft.Icons.STAR_ROUNDED,
        "color": "#2196F3",
        "from_price": "от 199 ₽",
        "short": "Базовый доступ ко всем функциям",
        "features_mask": PREMIUM_MASK,
        "periods": [
            {"id": "month",     "label": "1 месяц",    "price": "199 ₽",  "sub": "30 дней"},
            {"id": "3months",   "label": "3 месяца",   "price": "499 ₽",  "sub": "90 дней", "badge": "−17%"},
            {"id": "year",      "label": "1 год",      "price": "1 490 ₽", "sub": "365 дней", "badge": "−38%", "popular": True},
            {"id": "forever",   "label": "Навсегда",   "price": "3 990 ₽", "sub": "пожизненно"},
        ],
    },
    {
        "id": "premium_plus",
        "title": "Премиум Плюс",
        "icon": ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
        "color": "#FF9800",
        "from_price": "от 299 ₽",
        "short": "Всё из Премиума + расширенные функции",
        "features_mask": PLUS_MASK,
        "periods": [
            {"id": "month",     "label": "1 месяц",    "price": "299 ₽",  "sub": "30 дней"},
            {"id": "3months",   "label": "3 месяца",   "price": "749 ₽",  "sub": "90 дней", "badge": "−17%"},
            {"id": "year",      "label": "1 год",      "price": "2 190 ₽", "sub": "365 дней", "badge": "−39%", "popular": True},
            {"id": "forever",   "label": "Навсегда",   "price": "5 990 ₽", "sub": "пожизненно"},
        ],
    },
]


class SubscriptionScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.mobile = self._is_mobile()
        self._bg_effect = None
        self._stopped = False

        # Определяем текущий активный тариф
        self.current_plan_id = self._detect_current_plan()
        # Что выбрал пользователь (по умолчанию = текущий, если он не free)
        self.selected_plan_id = (
            self.current_plan_id
            if self.current_plan_id != "free" else "premium"
        )

        self.plans_row = ft.Row(
            controls=[], spacing=16, run_spacing=16, wrap=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        self.periods_column = ft.Column(
            controls=[], spacing=10, tight=True,
        )

        self._render_plans()

    # ------------------------------------------------------------------
    # Определение текущего тарифа
    # ------------------------------------------------------------------

    def _detect_current_plan(self) -> str:
        """Определяет текущий активный тариф из профиля."""
        try:
            profile = get_current()
            if profile and hasattr(profile, "is_premium") and profile.is_premium():
                return "premium"
        except Exception as ex:
            print(f"[SUB] detect current plan error: {ex}")
        return "free"

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------

    def _is_mobile(self) -> bool:
        if os.environ.get("FLET_APP_STORAGE_DATA"):
            return True
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

    def stop_effect(self) -> None:
        self._stopped = True
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None

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

        top_pad = 32 if self.mobile else 8

        def _close_screen(e):
            try:
                chat = getattr(self.page, "_vagent_chat_screen", None)
                if chat is not None:
                    chat._handle_nav("home")
                    return
            except Exception as ex:
                print(f"[SUB] close error: {ex}")

        top_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CLOSE_ROUNDED, size=16,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text("Закрыть", size=12,
                                        color=theme.TEXT_PRIMARY,
                                        weight=ft.FontWeight.BOLD),
                            ],
                            spacing=6, tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                        bgcolor=ft.Colors.with_opacity(0.5, theme.SURFACE),
                        border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
                        border_radius=10,
                        on_click=_close_screen,
                        ink=True,
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            padding=ft.padding.only(
                left=24, right=24, top=top_pad, bottom=0,
            ),
        )

        header = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                            size=40, color=ft.Colors.WHITE,
                        ),
                        width=80, height=80, border_radius=24,
                        bgcolor=theme.PRIMARY,
                        alignment=ft.alignment.center,
                        shadow=ft.BoxShadow(
                            spread_radius=2,
                            blur_radius=20,
                            color=ft.Colors.with_opacity(0.5, theme.PRIMARY),
                        ),
                    ),
                    ft.Container(height=16),
                    ft.Text(
                        "V-AGENT Тарифы",
                        size=28, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        "Сравни и выбери подходящий",
                        size=13, color=theme.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(
                left=24, right=24, top=20, bottom=20,
            ),
        )

        plans_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Тарифы",
                        size=13, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(height=12),
                    self.plans_row,
                ],
                spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
        )

        periods_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Срок подписки",
                        size=13, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(height=12),
                    self.periods_column,
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=12),
        )

        info_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LOCK_ROUNDED, size=14,
                                    color=theme.TEXT_MUTED),
                            ft.Text(
                                "Оплата проходит на FunPay.",
                                size=11, color=theme.TEXT_MUTED,
                            ),
                        ],
                        spacing=6, tight=True,
                    ),
                    ft.Container(height=4),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.KEY_ROUNDED, size=14,
                                    color=theme.TEXT_MUTED),
                            ft.Text(
                                "После оплаты получишь ключ активации. "
                                "Введи его в разделе «Активация Premium».",
                                size=11, color=theme.TEXT_MUTED,
                            ),
                        ],
                        spacing=6, tight=True,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=20),
        )

        content_col = ft.Column(
            controls=[
                top_bar,
                header,
                plans_block,
                periods_block,
                info_block,
                ft.Container(height=60),
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
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
    # Тарифы
    # ------------------------------------------------------------------

    def _render_plans(self) -> None:
        self.plans_row.controls.clear()
        for plan in PLANS:
            self.plans_row.controls.append(
                self._make_plan_tab(plan)
            )
        self._render_periods()

    def _make_plan_tab(self, plan: dict) -> ft.Container:
        color = plan["color"]
        plan_id = plan["id"]
        is_free = plan_id == "free"

        is_current = plan_id == self.current_plan_id
        is_selected = plan_id == self.selected_plan_id

        # Стиль карточки
        bg = (
            ft.Colors.with_opacity(0.15, color) if is_selected
            else ft.Colors.with_opacity(0.6, theme.SURFACE)
        )
        border_color = color if is_selected else theme.DRAWER_ITEM_BORDER

        # Список функций
        feature_rows = []
        mask = plan["features_mask"]
        for i, label in enumerate(ALL_FEATURES):
            has = mask[i] if i < len(mask) else False
            if has:
                icon = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED,
                               size=15, color="#4CAF50")
                text_color = theme.TEXT_PRIMARY
            else:
                icon = ft.Icon(ft.Icons.CANCEL_ROUNDED,
                               size=15, color="#FF5252")
                text_color = theme.TEXT_MUTED

            feature_rows.append(
                ft.Row(
                    controls=[
                        icon,
                        ft.Container(
                            content=ft.Text(
                                label, size=12,
                                color=text_color,
                            ),
                            expand=True,
                            margin=ft.margin.only(left=8),
                        ),
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        def _select(e, pid=plan_id):
            if self.selected_plan_id == pid:
                return
            self.selected_plan_id = pid
            self._render_plans()
            try:
                self.page.update()
            except Exception:
                pass

        # Бейдж:
        #  • Если тариф уже активен → ТЕКУЩИЙ
        #  • Иначе если выбран → ВЫБРАНО
        #  • Иначе → пусто
        badge_visible = False
        badge_text = ""
        badge_color = color

        if is_current:
            badge_text = "ТЕКУЩИЙ"
            badge_color = theme.SUCCESS
            badge_visible = True
        elif is_selected:
            badge_text = "ВЫБРАНО"
            badge_color = color
            badge_visible = True

        badge_icon = (
            ft.Icons.CHECK_ROUNDED if is_selected or is_current
            else ft.Icons.PERSON_ROUNDED
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(plan["icon"], size=28,
                                                color=ft.Colors.WHITE),
                                width=52, height=52, border_radius=16,
                                bgcolor=color,
                                alignment=ft.alignment.center,
                                shadow=ft.BoxShadow(
                                    spread_radius=1,
                                    blur_radius=12,
                                    color=ft.Colors.with_opacity(0.4, color),
                                ),
                            ),
                            ft.Container(expand=True),
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(badge_icon, size=12,
                                                color=ft.Colors.WHITE),
                                        ft.Text(badge_text, size=9,
                                                color=ft.Colors.WHITE,
                                                weight=ft.FontWeight.BOLD),
                                    ],
                                    spacing=4, tight=True,
                                ),
                                padding=ft.padding.symmetric(
                                    horizontal=8, vertical=4),
                                bgcolor=badge_color,
                                border_radius=6,
                                visible=badge_visible,
                            ),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Container(height=12),
                    ft.Text(
                        plan["title"], size=20,
                        weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY,
                    ),
                    ft.Container(height=4),
                    ft.Text(
                        plan["short"], size=11,
                        color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(
                        height=1,
                        bgcolor=ft.Colors.with_opacity(0.15, theme.TEXT_SECONDARY),
                        margin=ft.margin.symmetric(vertical=12),
                    ),
                    ft.Column(controls=feature_rows, spacing=6, tight=True),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text(
                                    plan["from_price"], size=20,
                                    weight=ft.FontWeight.BOLD,
                                    color=color,
                                ),
                                ft.Container(expand=True),
                                ft.Icon(
                                    ft.Icons.CHECK_ROUNDED if is_current
                                    else ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                    size=20,
                                    color=(theme.SUCCESS if is_current else color),
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.only(top=14),
                    ),
                ],
                spacing=0, tight=True,
            ),
            width=340,
            padding=ft.padding.all(18),
            bgcolor=bg,
            border=ft.border.all(2, border_color),
            border_radius=20,
            on_click=_select if not is_free else None,
            ink=not is_free,
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            scale=1.0,
            on_hover=self._hover_scale if not is_free else None,
        )

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

    # ------------------------------------------------------------------
    # Сроки
    # ------------------------------------------------------------------

    def _render_periods(self) -> None:
        self.periods_column.controls.clear()

        plan = None
        for p in PLANS:
            if p["id"] == self.selected_plan_id:
                plan = p
                break
        if not plan:
            return

        # Free — сообщение
        if plan["id"] == "free":
            is_current = self.current_plan_id == "free"
            self.periods_column.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(
                                        ft.Icons.CHECK_CIRCLE_ROUNDED
                                        if is_current
                                        else ft.Icons.INFO_OUTLINE_ROUNDED,
                                        size=20,
                                        color=(theme.SUCCESS if is_current
                                               else "#9E9E9E"),
                                    ),
                                    ft.Text(
                                        "У вас активен Free-тариф"
                                        if is_current
                                        else "Вы используете Free-версию",
                                        size=14, weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY,
                                    ),
                                ],
                                spacing=10, tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Container(height=8),
                            ft.Text(
                                "Чтобы разблокировать все функции, "
                                "выбери Премиум или Премиум Плюс.",
                                size=12, color=theme.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=0, tight=True,
                    ),
                    padding=ft.padding.all(16),
                    bgcolor=theme.SURFACE,
                    border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
                    border_radius=12,
                )
            )
            return

        color = plan["color"]
        is_selected_current = plan["id"] == self.current_plan_id

        # Если выбранный тариф уже текущий — сообщение вместо сроков
        if is_selected_current:
            # Считаем остаток дней
            days_left = 0
            until_str = ""
            is_forever = False
            try:
                profile = get_current()
                if profile and hasattr(profile, "premium_days_left"):
                    days_left = profile.premium_days_left()
                    if days_left == -1:
                        is_forever = True
                    until_str = getattr(profile, "premium_until", "") or ""
            except Exception as ex:
                print(f"[SUB] days_left error: {ex}")

            # Формируем строку
            if is_forever:
                subtitle = "Навсегда · без ограничений"
            elif days_left > 0:
                # Склонение слова «день»
                n = days_left
                mod10 = n % 10
                mod100 = n % 100
                if mod10 == 1 and mod100 != 11:
                    word = "день"
                elif 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
                    word = "дня"
                else:
                    word = "дней"
                subtitle = f"Осталось {n} {word}"
                if until_str:
                    try:
                        from datetime import date
                        until_date = date.fromisoformat(until_str)
                        subtitle += f" · до {until_date.strftime('%d.%m.%Y')}"
                    except Exception:
                        pass
            else:
                subtitle = "Срок истекает"

            self.periods_column.controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.ALL_INCLUSIVE_ROUNDED if is_forever
                                else ft.Icons.CHECK_CIRCLE_ROUNDED,
                                size=22,
                                color=theme.SUCCESS,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
                                            f"Тариф «{plan['title']}» уже активен",
                                            size=14, weight=ft.FontWeight.BOLD,
                                            color=theme.TEXT_PRIMARY,
                                        ),
                                        ft.Container(height=4),
                                        ft.Text(
                                            subtitle,
                                            size=12,
                                            color=ft.Colors.with_opacity(0.85, theme.SUCCESS),
                                        ),
                                    ],
                                    spacing=0, tight=True,
                                ),
                                expand=True,
                                margin=ft.margin.only(left=10),
                            ),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.all(16),
                    bgcolor=ft.Colors.with_opacity(0.1, theme.SUCCESS),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.4, theme.SUCCESS)),
                    border_radius=12,
                )
            )
            return
        # Обычный список периодов
        for period in plan["periods"]:
            is_popular = period.get("popular", False)
            badge = period.get("badge", "")

            def _buy(e, pid=plan["id"], per=period["id"]):
                url = FUNPAY_URLS.get(pid, {}).get(per, "")
                if not url or "СЮДА" in url:
                    self.page.open(ft.SnackBar(
                        content=ft.Text(
                            "Ссылка на лот FunPay ещё не настроена."
                        ),
                        duration=3000,
                        bgcolor=theme.DANGER,
                    ))
                    return
                try:
                    webbrowser.open(url)
                except Exception as ex:
                    print(f"[SUB] open url error: {ex}")
                self.page.open(ft.SnackBar(
                    content=ft.Text(
                        "Открылся браузер с лотом FunPay.\n"
                        "Оплати — получишь ключ активации."
                    ),
                    duration=4000,
                    bgcolor=theme.SURFACE,
                ))

            row_controls = [
                ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(period["label"], size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Container(
                                    content=ft.Text(
                                        badge, size=9,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                    ),
                                    padding=ft.padding.symmetric(
                                        horizontal=6, vertical=2),
                                    bgcolor=theme.SUCCESS,
                                    border_radius=6,
                                    visible=bool(badge),
                                ),
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
                                                    size=11,
                                                    color="#FF9800"),
                                            ft.Text("ХИТ", size=9,
                                                    color="#FF9800",
                                                    weight=ft.FontWeight.BOLD),
                                        ],
                                        spacing=3, tight=True,
                                    ),
                                    padding=ft.padding.symmetric(
                                        horizontal=6, vertical=2),
                                    bgcolor=ft.Colors.with_opacity(0.15, "#FF9800"),
                                    border_radius=6,
                                    visible=is_popular,
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(period["sub"], size=11,
                                color=theme.TEXT_SECONDARY),
                    ],
                    spacing=2, tight=True,
                ),
                ft.Container(expand=True),
                ft.Text(period["price"], size=18,
                        weight=ft.FontWeight.BOLD,
                        color=color),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=20,
                        color=color),
            ]

            self.periods_column.controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=row_controls,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=16, vertical=14),
                    bgcolor=theme.SURFACE,
                    border=ft.border.all(
                        2 if is_popular else 1,
                        color if is_popular else theme.DRAWER_ITEM_BORDER,
                    ),
                    border_radius=12,
                    on_click=_buy,
                    ink=True,
                )
            )