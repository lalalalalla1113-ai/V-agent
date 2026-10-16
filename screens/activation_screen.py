"""Экран активации Premium-ключа.

Формат ключа: XXXX-XXXX-XXXX-XXXX.
Проверка идёт через Cloudflare Worker (см. services/premium_check.py).
Ключ сгорает на сервере после первой успешной активации.
"""

import os
import re
from datetime import datetime, date, timedelta

import flet as ft

from services.premium_check import activate_premium_key
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


KEY_PATTERN = re.compile(
    r"^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$"
)


def normalize_key(raw: str) -> str:
    """Приводит ключ к виду XXXX-XXXX-XXXX-XXXX."""
    if not raw:
        return ""
    clean = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if len(clean) != 16:
        return ""
    return f"{clean[0:4]}-{clean[4:8]}-{clean[8:12]}-{clean[12:16]}"


class ActivationScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.mobile = self._is_mobile()
        self._bg_effect = None
        self._stopped = False
        self._is_checking = False

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

        # ================= ЗАГОЛОВОК =================
        header = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.KEY_ROUNDED, size=36,
                            color=ft.Colors.WHITE,
                        ),
                        width=72, height=72, border_radius=22,
                        bgcolor=theme.PRIMARY,
                        alignment=ft.alignment.center,
                        shadow=ft.BoxShadow(
                            spread_radius=2,
                            blur_radius=18,
                            color=ft.Colors.with_opacity(0.5, theme.PRIMARY),
                        ),
                    ),
                    ft.Container(height=16),
                    ft.Text(
                        "Активация Premium",
                        size=24, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        "Введи ключ, который ты получил после оплаты на FunPay",
                        size=13, color=theme.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(
                left=24, right=24, top=top_pad + 24, bottom=20,
            ),
        )

        # ================= ПОЛЕ ВВОДА =================
        key_field = ft.TextField(
            hint_text="XXXX-XXXX-XXXX-XXXX",
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=12,
            border_color=theme.DRAWER_ITEM_BORDER,
            focused_border_color=theme.PRIMARY,
            text_size=16,
            autofocus=True,
            text_align=ft.TextAlign.CENTER,
        )

        status_text = ft.Text(
            "", size=13, color=theme.TEXT_SECONDARY,
            text_align=ft.TextAlign.CENTER,
        )

        # ================= ТЕКУЩИЙ СТАТУС =================
        profile = get_current()
        current_status = ft.Container()
        if profile and hasattr(profile, "is_premium") and profile.is_premium():
            days = profile.premium_days_left()
            if days == -1:
                label = "Premium активен. Навсегда."
            else:
                label = f"Premium активен. Осталось {days} дней."
            current_status = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED,
                                size=20, color=theme.SUCCESS),
                        ft.Text(label, size=13, color=theme.SUCCESS),
                    ],
                    spacing=8, tight=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=ft.padding.all(12),
                bgcolor=ft.Colors.with_opacity(0.1, theme.SUCCESS),
                border_radius=10,
            )

        # ================= ВСТАВИТЬ ИЗ БУФЕРА =================
        def _paste_from_clipboard(e):
            try:
                clipboard = self.page.get_clipboard()
                if not clipboard:
                    status_text.value = "Буфер обмена пуст"
                    status_text.color = theme.WARNING
                    try:
                        status_text.update()
                    except Exception:
                        pass
                    return

                normalized = normalize_key(str(clipboard).strip())
                if not normalized:
                    status_text.value = ("В буфере нет ключа формата "
                                         "XXXX-XXXX-XXXX-XXXX")
                    status_text.color = theme.WARNING
                    try:
                        status_text.update()
                    except Exception:
                        pass
                    return

                key_field.value = normalized
                status_text.value = "Ключ вставлен из буфера"
                status_text.color = theme.SUCCESS
                try:
                    key_field.update()
                    status_text.update()
                except Exception:
                    pass

            except Exception as ex:
                print(f"[PASTE] error: {ex}")
                status_text.value = "Не удалось прочитать буфер"
                status_text.color = theme.DANGER
                try:
                    status_text.update()
                except Exception:
                    pass

        paste_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CONTENT_PASTE_ROUNDED, size=18,
                            color=theme.PRIMARY),
                    ft.Text("Вставить из буфера", size=13,
                            color=theme.PRIMARY,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=8, tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=_paste_from_clipboard,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, theme.PRIMARY),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
            ),
        )

        # ================= ПРОВЕРИТЬ И АКТИВИРОВАТЬ =================
        check_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_ROUNDED, size=18,
                            color=ft.Colors.WHITE),
                    ft.Text("Проверить и активировать", size=14,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=8, tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=theme.PRIMARY,
            on_click=lambda e: self._do_check(
                key_field, status_text, check_btn, paste_btn
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.padding.symmetric(horizontal=24, vertical=16),
            ),
        )

        # ================= ИНСТРУКЦИЯ =================
        instruction = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=14,
                                    color=theme.TEXT_SECONDARY),
                            ft.Text(
                                "Как получить ключ:",
                                size=12, weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_PRIMARY,
                            ),
                        ],
                        spacing=6, tight=True,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        "1. Открой раздел Premium в сайдбаре\n"
                        "2. Выбери тариф\n"
                        "3. Нажми «Оплатить на FunPay»\n"
                        "4. Оплати лот — получишь ключ в чате\n"
                        "5. Вернись сюда и вставь ключ",
                        size=11, color=theme.TEXT_SECONDARY,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.all(14),
            bgcolor=ft.Colors.with_opacity(0.5, theme.SURFACE),
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            border_radius=12,
        )

        # ================= КАРТОЧКА =================
        card_controls = []
        if current_status.content is not None:
            card_controls.append(current_status)
            card_controls.append(ft.Container(height=14))

        card_controls.extend([
            key_field,
            ft.Container(height=10),
            ft.Row(
                controls=[paste_btn, check_btn],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
                wrap=True,
            ),
            ft.Container(height=12),
            status_text,
            ft.Container(height=20),
            instruction,
        ])

        card = ft.Container(
            content=ft.Column(
                controls=card_controls,
                spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.all(20),
            bgcolor=theme.SURFACE,
            border_radius=18,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            width=540 if not self.mobile else None,
        )

        content_col = ft.Column(
            controls=[
                header,
                ft.Container(content=card,
                             padding=ft.padding.symmetric(horizontal=24)),
                ft.Container(height=60),
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
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

    # ---------- Логика проверки ----------

    def _do_check(self, key_field, status_text, check_btn, paste_btn) -> None:
        if self._is_checking:
            return

        raw = (key_field.value or "").strip()
        normalized = normalize_key(raw)

        if not normalized:
            status_text.value = "Неверный формат. XXXX-XXXX-XXXX-XXXX"
            status_text.color = theme.DANGER
            try:
                status_text.update()
            except Exception:
                pass
            return

        key_field.value = normalized
        try:
            key_field.update()
        except Exception:
            pass

        self._is_checking = True
        status_text.value = "Проверяю ключ на сервере..."
        status_text.color = theme.TEXT_SECONDARY
        try:
            status_text.update()
        except Exception:
            pass

        import threading

        def _worker():
            ok, days, err = activate_premium_key(normalized)

            def _done():
                self._is_checking = False

                if not ok:
                    status_text.value = f"❌ {err}"
                    status_text.color = theme.DANGER
                    try:
                        status_text.update()
                    except Exception:
                        pass
                    self.page.open(ft.SnackBar(
                        content=ft.Text(err),
                        duration=3000,
                        bgcolor=theme.DANGER,
                    ))
                    return

                # Активируем Premium
                p = get_current()
                if p:
                    p.premium_active = True
                    p.premium_key = normalized
                    p.premium_since = datetime.now().isoformat()

                    if days == -1:
                        p.premium_until = ""
                    else:
                        until = date.today() + timedelta(days=days)
                        p.premium_until = until.isoformat()

                    p.save()

                if days == -1:
                    status_text.value = "✅ Premium активирован навсегда!"
                else:
                    status_text.value = f"✅ Premium активирован на {days} дней!"

                status_text.color = theme.SUCCESS
                try:
                    status_text.update()
                except Exception:
                    pass

                self.page.open(ft.SnackBar(
                    content=ft.Text("Premium активирован!"),
                    duration=3000,
                    bgcolor=theme.SUCCESS,
                ))

            threading.Timer(0, _done).start()

        threading.Thread(target=_worker, daemon=True).start()