"""Экран управления Telegram-ботами + планировщик публикаций."""

import threading
from datetime import datetime
from typing import Optional

import flet as ft

from services import telegram
from services import tg_scheduler
from services.telegram import strip_html
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


MAX_BOTS = 3
MAX_SAMPLES = 10


class TelegramScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._bg_effect = None
        self._active_tab = "history"
        self._current_dialog = None
        self.editing_bot_id: Optional[str] = None
        self.is_testing = False

        self.token_field = ft.TextField(
            hint_text="1234567890:AAH...",
            password=True, can_reveal_password=True,
            filled=True, fill_color=theme.BG_DARK, color=theme.TEXT_PRIMARY,
            border_radius=10, text_size=14,
        )
        self.channel_field = ft.TextField(
            hint_text="-1001234567890 или @channel",
            filled=True, fill_color=theme.BG_DARK, color=theme.TEXT_PRIMARY,
            border_radius=10, text_size=14,
        )
        self.status_text = ft.Text("", size=12,
                                   color=theme.TEXT_SECONDARY,
                                   selectable=True)

        self.bots_container = ft.Column(controls=[], spacing=10, tight=True)
        self.plan_container = ft.Column(controls=[], spacing=10, tight=True)
        self.tabs_container = ft.Column(controls=[], spacing=8, tight=True)
        self.content_container = ft.Column(controls=[], spacing=10, tight=True)

    def stop_effect(self) -> None:
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None

    # ------------------------------------------------------------------
    # Сборка
    # ------------------------------------------------------------------

    def build(self) -> ft.Container:
        profile = get_current()
        effect_key = (profile.bg_effect if profile else "snow") or "snow"

        try:
            ww = int(self.page.window.width or self.page.width or 1920)
            wh = int(self.page.window.height or self.page.height or 1080)
        except Exception:
            ww, wh = 1920, 1080

        self._bg_effect = create_effect(
            effect_key, self.page, width=ww, height=wh,
        )
        bg_layer = self._bg_effect.build()
        self._bg_effect.start()

        self._refresh_bots()
        self._refresh_plan()
        self._refresh_tabs()
        self._refresh_content()

        main_col = ft.Column(
            controls=[
                self._build_header(),
                ft.Container(height=12),
                self._vpn_hint(),
                ft.Container(height=16),
                self.bots_container,
                ft.Container(height=24),
                self.plan_container,
                ft.Container(height=24),
                self.tabs_container,
                ft.Container(height=12),
                self.content_container,
                ft.Container(height=32),
            ],
            spacing=0,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        main_layer = ft.Container(
            content=main_col,
            expand=True,
            padding=ft.padding.symmetric(horizontal=24),
            bgcolor=ft.Colors.with_opacity(0.6, theme.BG_DARK),
        )

        return ft.Container(
            content=ft.Stack(
                controls=[bg_layer, main_layer],
                expand=True,
            ),
            expand=True,
        )

    def _build_header(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.SEND_ROUNDED, size=24,
                                        color=ft.Colors.WHITE),
                        width=48, height=48, border_radius=14,
                        bgcolor=theme.PRIMARY,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Telegram", size=22,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text("Боты и автопостинг", size=11,
                                        color=theme.TEXT_SECONDARY),
                            ],
                            spacing=0, tight=True,
                        ),
                        margin=ft.margin.only(left=14),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(top=20, bottom=8),
        )

    # ------------------------------------------------------------------
    # Постоянное предупреждение про VPN
    # ------------------------------------------------------------------

    def _vpn_hint(self) -> ft.Container:
        def close_hint(ev):
            try:
                profile = get_current()
                if profile:
                    profile.tg_vpn_hint_hidden = True
                    profile.save()
                self._refresh_plan()
                self.page.update()
            except Exception:
                pass

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16,
                            color=theme.WARNING),
                    ft.Container(
                        content=ft.Text(
                            "Telegram может быть заблокирован провайдером. "
                            "Если пост не отправится — включите VPN или прокси.",
                            size=11, color=theme.TEXT_PRIMARY,
                        ),
                        expand=True,
                        margin=ft.margin.only(left=10),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=16,
                        icon_color=theme.TEXT_MUTED,
                        tooltip="Скрыть подсказку",
                        on_click=close_hint,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            bgcolor=ft.Colors.with_opacity(0.1, theme.WARNING),
            border=ft.border.all(1, ft.Colors.with_opacity(0.3, theme.WARNING)),
            border_radius=12,
        )

    # ------------------------------------------------------------------
    # Боты
    # ------------------------------------------------------------------

    def _refresh_bots(self) -> None:
        self.bots_container.controls.clear()

        profile = get_current()
        if not profile:
            return

        bots = profile.tg_bots or []
        can_add = len(bots) < MAX_BOTS

        cards_row = ft.Row(spacing=12, wrap=True, run_spacing=12)

        for bot in bots:
            cards_row.controls.append(self._make_bot_card(bot, profile))

        def open_add(ev):
            if not can_add:
                return
            self.editing_bot_id = None
            self._open_bot_form()

        cards_row.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.ADD_ROUNDED, size=28,
                                            color=ft.Colors.WHITE if can_add
                                            else theme.TEXT_MUTED),
                            width=48, height=48, border_radius=14,
                            bgcolor=ft.Colors.with_opacity(0.15, theme.PRIMARY),
                            alignment=ft.alignment.center,
                        ),
                        ft.Container(height=6),
                        ft.Text("Добавить", size=12,
                                weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_PRIMARY if can_add
                                else theme.TEXT_MUTED),
                        ft.Text(f"{len(bots)}/{MAX_BOTS}", size=10,
                                color=theme.TEXT_MUTED),
                    ],
                    spacing=0, tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                width=140, height=140,
                padding=ft.padding.all(8),
                bgcolor=theme.SURFACE,
                border=ft.border.all(
                    2, ft.Colors.with_opacity(0.5, theme.PRIMARY)
                    if can_add else theme.DRAWER_ITEM_BORDER,
                ),
                border_radius=18,
                alignment=ft.alignment.center,
                on_click=open_add if can_add else None,
                ink=can_add,
                animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                on_hover=self._hover_scale,
                scale=1.0,
            )
        )

        self.bots_container.controls.append(cards_row)

    def _hover_scale(self, e: ft.ControlEvent) -> None:
        try:
            ctrl = e.control
            if e.data == "true":
                ctrl.scale = 1.04
            else:
                ctrl.scale = 1.0
            ctrl.update()
        except Exception:
            pass

    def _make_bot_card(self, bot: dict, profile) -> ft.Container:
        is_active = bot.get("id") == profile.tg_active_id
        name = bot.get("name", "Бот")
        username = bot.get("username", "")

        def on_tap(ev):
            if is_active:
                self.editing_bot_id = bot.get("id")
                self._open_bot_form()
                return
            profile.set_active_bot(bot.get("id"))
            profile.save()
            self._refresh_bots()
            self._refresh_content()
            try:
                self.page.update()
            except Exception:
                pass

        if is_active:
            border_color = theme.SUCCESS
            bg_color = ft.Colors.with_opacity(0.12, theme.SUCCESS)
            badge_bg = theme.SUCCESS
            badge_text = "активен"
            dot_color = theme.SUCCESS
        else:
            border_color = theme.DRAWER_ITEM_BORDER
            bg_color = theme.SURFACE
            badge_bg = theme.TEXT_MUTED
            badge_text = "нажми"
            dot_color = theme.TEXT_MUTED

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=10, height=10, border_radius=5,
                                bgcolor=dot_color,
                            ),
                            ft.Container(expand=True),
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.SMART_TOY_ROUNDED, size=18,
                                    color=ft.Colors.WHITE,
                                ),
                                width=32, height=32, border_radius=10,
                                bgcolor=ft.Colors.with_opacity(
                                    0.15, theme.PRIMARY
                                ),
                                alignment=ft.alignment.center,
                            ),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=6),
                    ft.Text(name, size=13, weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_PRIMARY,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"@{username}" if username else "—",
                            size=10, color=theme.TEXT_MUTED,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Text(badge_text, size=9,
                                        color=ft.Colors.WHITE,
                                        weight=ft.FontWeight.BOLD),
                        padding=ft.padding.symmetric(horizontal=8,
                                                    vertical=3),
                        bgcolor=badge_bg,
                        border_radius=6,
                    ),
                ],
                spacing=2, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            width=140, height=140,
            padding=ft.padding.all(10),
            bgcolor=bg_color,
            border=ft.border.all(2, border_color),
            border_radius=18,
            on_click=on_tap,
            ink=True,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=10,
                color=ft.Colors.with_opacity(0.2, "#000000"),
                offset=ft.Offset(0, 3),
            ),
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            scale=1.0,
            on_hover=self._hover_scale,
        )

    # ------------------------------------------------------------------
    # Создание контент-плана
    # ------------------------------------------------------------------

    def _refresh_plan(self) -> None:
        self.plan_container.controls.clear()

        slots = tg_scheduler.load_slots()
        slots.sort(key=lambda s: (int(s.get("weekday", 0)),
                                  s.get("time", "")))

        header_row = ft.Row(
            controls=[
                ft.Container(width=4, height=18,
                            bgcolor=theme.PRIMARY, border_radius=2),
                ft.Text("Создание контент-плана", size=14,
                        weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY),
                ft.Container(expand=True),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ADD_ROUNDED, size=14,
                                    color=ft.Colors.WHITE),
                            ft.Text("Добавить", size=11,
                                    color=ft.Colors.WHITE,
                                    weight=ft.FontWeight.BOLD),
                        ],
                        spacing=4, tight=True,
                    ),
                    padding=ft.padding.symmetric(horizontal=12,
                                                vertical=8),
                    bgcolor=theme.PRIMARY,
                    border_radius=8,
                    on_click=lambda e: self._open_post_form(None),
                    ink=True,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.plan_container.controls.append(header_row)

        if slots:
            for s in slots:
                self.plan_container.controls.append(
                    self._make_post_row(s)
                )
        else:
            self.plan_container.controls.append(
                ft.Container(
                    content=ft.Text("Пока нет запланированных постов",
                                    size=12,
                                    color=theme.TEXT_MUTED,
                                    italic=True),
                    padding=ft.padding.symmetric(vertical=20),
                    alignment=ft.alignment.center,
                    bgcolor=theme.SURFACE,
                    border_radius=12,
                )
            )

    def _make_post_row(self, slot: dict) -> ft.Container:
        weekday = int(slot.get("weekday", 0))
        weekday_short = tg_scheduler.WEEKDAYS_SHORT[weekday] \
            if 0 <= weekday < 7 else "?"
        time_str = slot.get("time", "00:00")
        topic = strip_html(slot.get("topic", "")) or "(без темы)"
        enabled = bool(slot.get("enabled", True))

        day_colors = {
            0: "#9C27B0", 1: "#7E57C2", 2: "#5C6BC0",
            3: "#26A69A", 4: "#66BB6A", 5: "#FFA726", 6: "#EF5350",
        }
        day_color = day_colors.get(weekday, theme.PRIMARY)

        def toggle(ev):
            all_slots = tg_scheduler.load_slots()
            for s in all_slots:
                if s.get("id") == slot.get("id"):
                    s["enabled"] = not bool(s.get("enabled", True))
                    break
            tg_scheduler.save_slots(all_slots)
            self._refresh_plan()
            try:
                self.page.update()
            except Exception:
                pass

        def edit(ev):
            self._open_post_form(slot)

        def remove(ev):
            all_slots = tg_scheduler.load_slots()
            all_slots = [s for s in all_slots
                         if s.get("id") != slot.get("id")]
            tg_scheduler.save_slots(all_slots)
            self._refresh_plan()
            try:
                self.page.update()
            except Exception:
                pass

        publish_status = ft.Text(
            "", size=10, color=theme.TEXT_SECONDARY, italic=True,
        )
        publish_spinner = ft.ProgressRing(
            width=14, height=14,
            stroke_width=2,
            color=theme.PRIMARY,
            visible=False,
        )
        publish_play_icon = ft.Icon(
            ft.Icons.PLAY_ARROW_ROUNDED,
            size=18,
            color=theme.PRIMARY,
        )
        publish_btn_content = ft.Stack(
            controls=[publish_play_icon, publish_spinner],
            width=20, height=20,
            alignment=ft.alignment.center,
        )

        def publish_now(ev):
            sched = tg_scheduler.get_global()
            if not sched:
                self.page.open(ft.SnackBar(
                    content=ft.Text("Планировщик не запущен"),
                    duration=2000,
                ))
                return

            profile = get_current()
            if profile and not getattr(profile, "tg_vpn_hint_shown", False):
                self._confirm_vpn_and_publish(
                    slot=slot,
                    sched=sched,
                    publish_play_icon=publish_play_icon,
                    publish_spinner=publish_spinner,
                    publish_status=publish_status,
                    publish_btn_content=publish_btn_content,
                )
                return

            self._do_publish(
                slot=slot,
                sched=sched,
                publish_play_icon=publish_play_icon,
                publish_spinner=publish_spinner,
                publish_status=publish_status,
                publish_btn_content=publish_btn_content,
            )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(weekday_short, size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                        text_align=ft.TextAlign.CENTER),
                        width=44, height=44, border_radius=12,
                        bgcolor=day_color if enabled
                        else theme.TEXT_MUTED,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    f"{time_str} · {topic}",
                                    size=12,
                                    color=theme.TEXT_PRIMARY,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                publish_status,
                            ],
                            spacing=2, tight=True,
                        ),
                        expand=True,
                        margin=ft.margin.only(left=12),
                    ),
                    ft.Container(
                        content=publish_btn_content,
                        padding=ft.padding.all(8),
                        on_click=publish_now,
                        ink=True,
                        border_radius=8,
                        tooltip="Опубликовать сейчас",
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_ROUNDED,
                        icon_size=16,
                        icon_color=theme.TEXT_SECONDARY,
                        on_click=edit,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_size=16,
                        icon_color=theme.DANGER,
                        on_click=remove,
                    ),
                    ft.Switch(
                        value=enabled,
                        active_color=theme.PRIMARY,
                        scale=0.8,
                        on_change=toggle,
                    ),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            bgcolor=theme.SURFACE,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            border_radius=12,
            opacity=1.0 if enabled else 0.5,
        )

    # ------------------------------------------------------------------
    # Диалог «VPN?» + публикация
    # ------------------------------------------------------------------

    def _confirm_vpn_and_publish(self, slot, sched, publish_play_icon,
                                 publish_spinner, publish_status,
                                 publish_btn_content):
        dialog = ft.AlertDialog(modal=True, bgcolor=theme.SURFACE)

        def do_continue(ev):
            try:
                profile = get_current()
                if profile:
                    profile.tg_vpn_hint_shown = True
                    profile.save()
            except Exception:
                pass
            try:
                self.page.close(dialog)
            except Exception:
                pass
            self._do_publish(
                slot=slot, sched=sched,
                publish_play_icon=publish_play_icon,
                publish_spinner=publish_spinner,
                publish_status=publish_status,
                publish_btn_content=publish_btn_content,
            )

        def do_cancel(ev):
            try:
                self.page.close(dialog)
            except Exception:
                pass

        dialog.title = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED,
                                    size=20, color=ft.Colors.WHITE),
                    width=36, height=36, border_radius=10,
                    bgcolor=theme.WARNING,
                    alignment=ft.alignment.center,
                ),
                ft.Container(
                    content=ft.Text("Перед публикацией",
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY),
                    margin=ft.margin.only(left=10),
                ),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Telegram может быть заблокирован вашим "
                        "провайдером (РФ, Иран и др.).",
                        size=13, color=theme.TEXT_PRIMARY,
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        "Если пост не отправится — включите VPN "
                        "или настройте прокси. Без VPN пост "
                        "уйдёт только если провайдер не блокирует "
                        "api.telegram.org.",
                        size=12, color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(height=10),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, size=14,
                                        color=theme.PRIMARY),
                                ft.Text(
                                    "Если ошибка уже была раньше — "
                                    "включите VPN прямо сейчас.",
                                    size=11,
                                    color=theme.TEXT_SECONDARY,
                                ),
                            ],
                            spacing=6,
                        ),
                        padding=ft.padding.all(10),
                        bgcolor=ft.Colors.with_opacity(0.08, theme.PRIMARY),
                        border_radius=10,
                    ),
                ],
                spacing=0, tight=True,
            ),
            width=420,
        )

        cancel_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CLOSE_ROUNDED, size=14,
                            color=theme.TEXT_SECONDARY),
                    ft.Text("Отмена", size=12,
                            color=theme.TEXT_SECONDARY),
                ],
                spacing=6, tight=True,
            ),
            on_click=do_cancel,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, theme.DRAWER_ITEM_BORDER),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
            ),
        )

        continue_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SEND_ROUNDED, size=14,
                            color=ft.Colors.WHITE),
                    ft.Text("Продолжить", size=12,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=6, tight=True,
            ),
            bgcolor=theme.PRIMARY,
            on_click=do_continue,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=18, vertical=12),
            ),
        )

        dialog.actions = [cancel_btn, continue_btn]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        self._current_dialog = dialog
        self.page.open(dialog)
        try:
            self.page.update()
        except Exception:
            pass

    def _do_publish(self, slot, sched, publish_play_icon, publish_spinner,
                    publish_status, publish_btn_content):
        publish_play_icon.visible = False
        publish_spinner.visible = True
        publish_status.value = "Отправляется..."
        publish_status.color = theme.TEXT_SECONDARY
        try:
            publish_btn_content.update()
            publish_status.update()
            self.page.update()
        except Exception:
            pass

        def _worker():
            ok = sched.publish_now(slot)

            def _done():
                publish_spinner.visible = False
                if ok:
                    publish_play_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                    publish_play_icon.color = theme.SUCCESS
                    publish_play_icon.visible = True
                    publish_status.value = "✅ Отправлено"
                    publish_status.color = theme.SUCCESS
                else:
                    publish_play_icon.name = ft.Icons.ERROR_ROUNDED
                    publish_play_icon.color = theme.DANGER
                    publish_play_icon.visible = True
                    publish_status.value = "❌ Не удалось — включите VPN"
                    publish_status.color = theme.DANGER

                try:
                    publish_btn_content.update()
                    publish_status.update()
                    self.page.update()
                except Exception:
                    pass

                def _reset():
                    publish_play_icon.name = ft.Icons.PLAY_ARROW_ROUNDED
                    publish_play_icon.color = theme.PRIMARY
                    publish_play_icon.visible = True
                    publish_status.value = ""
                    try:
                        publish_btn_content.update()
                        publish_status.update()
                        self.page.update()
                    except Exception:
                        pass
                    if self._active_tab == "history":
                        self._refresh_content()
                        try:
                            self.page.update()
                        except Exception:
                            pass

                t = threading.Timer(2.5, _reset)
                t.daemon = True
                t.start()

            threading.Timer(0, _done).start()

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Вкладки
    # ------------------------------------------------------------------

    def _refresh_tabs(self) -> None:
        self.tabs_container.controls.clear()

        def make_tab(key, icon, label):
            is_active = self._active_tab == key

            def click(ev):
                self._active_tab = key
                self._refresh_tabs()
                self._refresh_content()
                try:
                    self.page.update()
                except Exception:
                    pass

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=16,
                                color=ft.Colors.WHITE if is_active
                                else theme.TEXT_PRIMARY),
                        ft.Text(label, size=12,
                                color=ft.Colors.WHITE if is_active
                                else theme.TEXT_PRIMARY,
                                weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8, tight=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                bgcolor=theme.PRIMARY if is_active else theme.SURFACE,
                border=ft.border.all(
                    1, theme.PRIMARY if is_active
                    else theme.DRAWER_ITEM_BORDER,
                ),
                border_radius=12,
                on_click=click,
                ink=True,
                expand=True,
            )

        tabs_row = ft.Row(
            controls=[
                make_tab("history", ft.Icons.HISTORY, "История"),
                make_tab("samples", ft.Icons.DESCRIPTION, "Примеры"),
            ],
            spacing=10,
        )
        self.tabs_container.controls.append(tabs_row)

    def _refresh_content(self) -> None:
        self.content_container.controls.clear()

        if self._active_tab == "history":
            self._build_history_content()
        else:
            self._build_samples_content()

    # ------------------------------------------------------------------
    # История
    # ------------------------------------------------------------------

    def _build_history_content(self) -> None:
        history = tg_scheduler.load_history()

        if not history:
            self.content_container.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.HISTORY, size=32,
                                    color=theme.TEXT_MUTED),
                            ft.Container(height=10),
                            ft.Text("Пока ничего не публиковалось",
                                    size=13, weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY),
                        ],
                        spacing=0, tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(vertical=30),
                    alignment=ft.alignment.center,
                    bgcolor=theme.SURFACE,
                    border_radius=12,
                )
            )
            return

        def clear_history(ev):
            tg_scheduler.clear_history()
            self._refresh_content()
            try:
                self.page.update()
            except Exception:
                pass

        self.content_container.controls.append(
            ft.Row(
                controls=[
                    ft.Text(f"Всего: {len(history)}", size=11,
                            color=theme.TEXT_MUTED),
                    ft.Container(expand=True),
                    ft.TextButton("Очистить", on_click=clear_history),
                ],
            )
        )

        for item in history[:50]:
            self.content_container.controls.append(
                self._make_history_row(item)
            )

    def _make_history_row(self, item: dict) -> ft.Container:
        ts = item.get("timestamp", "")
        text = item.get("text", "")
        status = item.get("status", "ok")
        topic = item.get("topic", "")
        error = item.get("error", "")

        try:
            dt = datetime.fromisoformat(ts)
            date_str = f"{dt.day:02d}.{dt.month:02d} {dt.hour:02d}:{dt.minute:02d}"
        except Exception:
            date_str = ts[:16]

        ok = status == "ok"
        preview = strip_html(text)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_ROUNDED if ok
                                else ft.Icons.ERROR_ROUNDED,
                                size=14,
                                color=theme.SUCCESS if ok
                                else theme.DANGER,
                            ),
                            ft.Text(date_str, size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY),
                            ft.Container(expand=True),
                            ft.Text(f"📌 {topic}", size=10,
                                    color=theme.TEXT_MUTED,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                        spacing=6,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        preview[:150] + ("…" if len(preview) > 150 else ""),
                        size=11, color=theme.TEXT_SECONDARY,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(
                        content=ft.Text(f"❌ {error}", size=10,
                                        color=theme.DANGER),
                        visible=bool(error) and not ok,
                        padding=ft.padding.only(top=6),
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.all(10),
            bgcolor=theme.SURFACE,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            border_radius=10,
        )

    # ------------------------------------------------------------------
    # Примеры
    # ------------------------------------------------------------------

    def _build_samples_content(self) -> None:
        profile = get_current()
        if not profile:
            return

        bot = profile.get_active_bot()
        if not bot:
            self.content_container.controls.append(
                ft.Text("Сначала добавь бота", size=12,
                        color=theme.TEXT_MUTED, italic=True),
            )
            return

        samples = profile.get_bot_samples(bot.get("id"))

        new_field = ft.TextField(
            hint_text=(
                "Вставь сюда текст поста из канала.\n\n"
                "Можно с HTML-разметкой Telegram:\n"
                "<b>жирный</b>  <i>курсив</i>  <u>подчёркнутый</u>\n"
                "<blockquote>цитата</blockquote>\n\n"
                "Ctrl+Enter или кнопка «Добавить» — сохранить."
            ),
            multiline=True,
            min_lines=8,
            max_lines=20,
            filled=True,
            fill_color=theme.BG_DARK,
            color=theme.TEXT_PRIMARY,
            border_radius=12,
            border_color=theme.DRAWER_ITEM_BORDER,
            focused_border_color=theme.PRIMARY,
            text_size=13,
            expand=True,
            shift_enter=True,
            on_submit=lambda e: self._add_sample_from_field(
                new_field, profile, bot
            ),
        )

        def add_sample(ev):
            self._add_sample_from_field(new_field, profile, bot)

        def clear_all(ev):
            profile.set_bot_samples([], bot.get("id"))
            profile.save()
            self._refresh_content()
            try:
                self.page.update()
            except Exception:
                pass

        add_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=16,
                            color=ft.Colors.WHITE),
                    ft.Text("Добавить", size=12,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=6, tight=True,
            ),
            bgcolor=theme.PRIMARY,
            on_click=add_sample,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=18, vertical=14),
            ),
        )

        counter_label = ft.Text(
            f"Примеры для бота · {len(samples)}/{MAX_SAMPLES}",
            size=12, weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY,
        )

        hint_label = ft.Text(
            "Совет: вставь 3–5 своих лучших постов — ИИ подстроится "
            "под твой стиль, длину и оформление.",
            size=11, color=theme.TEXT_SECONDARY, italic=True,
        )

        input_block = ft.Container(
            content=ft.Column(
                controls=[
                    counter_label,
                    ft.Container(height=6),
                    hint_label,
                    ft.Container(height=10),
                    new_field,
                    ft.Container(height=10),
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Enter — новая строка, кнопка ниже — сохранить",
                                size=10, color=theme.TEXT_MUTED,
                            ),
                            ft.Container(expand=True),
                            add_btn,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.all(14),
            bgcolor=theme.SURFACE,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            border_radius=14,
        )

        self.content_container.controls.append(input_block)

        if not samples:
            self.content_container.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=36,
                                    color=theme.TEXT_MUTED),
                            ft.Container(height=8),
                            ft.Text("Пока нет примеров",
                                    size=13, weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY),
                            ft.Text(
                                "Добавь хотя бы один пост из канала — "
                                "ИИ будет писать в похожем стиле.",
                                size=11, color=theme.TEXT_SECONDARY,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        spacing=0, tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(vertical=30),
                    alignment=ft.alignment.center,
                    bgcolor=theme.SURFACE,
                    border_radius=12,
                )
            )
            return

        self.content_container.controls.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text(
                            f"Сохранённые примеры ({len(samples)})",
                            size=12, weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_PRIMARY,
                        ),
                        ft.Container(expand=True),
                        ft.TextButton(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED,
                                            size=14,
                                            color=theme.DANGER),
                                    ft.Text("Очистить всё", size=11,
                                            color=theme.DANGER),
                                ],
                                spacing=4, tight=True,
                            ),
                            on_click=clear_all,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.only(top=14, bottom=6),
            )
        )

        for i, s in enumerate(samples, 1):
            self.content_container.controls.append(
                self._make_sample_card(i, s, bot.get("id"))
            )

    def _add_sample_from_field(self, field, profile, bot) -> None:
        txt = (field.value or "").strip()
        if not txt:
            self.page.open(ft.SnackBar(
                content=ft.Text("Вставь текст поста"),
                duration=1500,
            ))
            return

        current = profile.get_bot_samples(bot.get("id"))
        if len(current) >= MAX_SAMPLES:
            self.page.open(ft.SnackBar(
                content=ft.Text(
                    f"Достигнут лимит {MAX_SAMPLES} примеров. "
                    f"Удали ненужные."
                ),
                duration=2000,
            ))
            return

        current.append(txt)
        profile.set_bot_samples(current, bot.get("id"))
        profile.save()

        field.value = ""
        self._refresh_content()
        try:
            self.page.update()
        except Exception:
            pass

        self.page.open(ft.SnackBar(
            content=ft.Text(f"Пример добавлен ({len(current)}/{MAX_SAMPLES})"),
            duration=1500,
        ))

    def _make_sample_card(self, index: int, sample: str,
                          bot_id: str) -> ft.Container:
        profile = get_current()

        def remove(ev):
            if not profile:
                return
            current = profile.get_bot_samples(bot_id)
            if 0 <= index - 1 < len(current):
                current.pop(index - 1)
                profile.set_bot_samples(current, bot_id)
                profile.save()
                self._refresh_content()
                try:
                    self.page.update()
                except Exception:
                    pass

        preview_control = self._render_html_preview(sample)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(
                                    str(index), size=10,
                                    color=ft.Colors.WHITE,
                                    weight=ft.FontWeight.BOLD,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                width=24, height=24, border_radius=12,
                                bgcolor=theme.PRIMARY,
                                alignment=ft.alignment.center,
                            ),
                            ft.Text(
                                f"Пример #{index}",
                                size=11, weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_MUTED,
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_size=16,
                                icon_color=theme.DANGER,
                                tooltip="Удалить пример",
                                on_click=remove,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=6),
                    ft.Container(
                        content=preview_control,
                        padding=ft.padding.all(10),
                        bgcolor=theme.BG_DARK,
                        border_radius=10,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.all(12),
            bgcolor=theme.SURFACE,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            border_radius=12,
            margin=ft.margin.only(bottom=8),
        )

    def _render_html_preview(self, raw: str) -> ft.Control:
        import re as _re

        text = raw or ""

        blockquote_re = _re.compile(
            r"<blockquote(?:\s[^>]*)?>(.*?)</blockquote>",
            _re.DOTALL | _re.IGNORECASE,
        )

        parts: list = []
        last_end = 0
        for m in blockquote_re.finditer(text):
            if m.start() > last_end:
                parts.append(("plain", text[last_end:m.start()]))
            parts.append(("quote", m.group(1)))
            last_end = m.end()
        if last_end < len(text):
            parts.append(("plain", text[last_end:]))
        if not parts:
            parts = [("plain", text)]

        controls: list = []

        for kind, content in parts:
            if kind == "quote":
                controls.append(
                    ft.Container(
                        content=self._render_inline(content),
                        padding=ft.padding.only(
                            left=12, right=8, top=6, bottom=6
                        ),
                        border=ft.border.only(
                            left=ft.BorderSide(3, theme.PRIMARY),
                        ),
                        bgcolor=ft.Colors.with_opacity(0.06, theme.PRIMARY),
                        border_radius=6,
                        margin=ft.margin.symmetric(vertical=4),
                    )
                )
            else:
                cleaned = content.strip("\n")
                if cleaned:
                    controls.append(self._render_inline(cleaned))

        return ft.Column(controls=controls, spacing=4, tight=True)

    def _render_inline(self, text: str) -> ft.Control:
        import re as _re

        text = _re.sub(
            r'<tg-emoji[^>]*>(.*?)</tg-emoji>',
            r"\1", text, flags=_re.DOTALL | _re.IGNORECASE,
        )

        tag_re = _re.compile(
            r"<(/?)(b|strong|i|em|u|s|strike|code|pre|tg-spoiler)>",
            _re.IGNORECASE,
        )

        spans: list = []
        flags = {"b": 0, "i": 0, "u": 0, "s": 0, "code": 0, "spoiler": 0}
        pos = 0
        for m in tag_re.finditer(text):
            if m.start() > pos:
                spans.append({
                    "text": text[pos:m.start()],
                    "b": flags["b"] > 0,
                    "i": flags["i"] > 0,
                    "u": flags["u"] > 0,
                    "s": flags["s"] > 0,
                    "code": flags["code"] > 0,
                    "spoiler": flags["spoiler"] > 0,
                })
            closing = m.group(1) == "/"
            tag = m.group(2).lower()
            if tag == "strong":
                tag = "b"
            elif tag == "em":
                tag = "i"
            elif tag == "strike":
                tag = "s"
            elif tag == "pre":
                tag = "code"
            if tag in flags:
                flags[tag] += -1 if closing else 1
                if flags[tag] < 0:
                    flags[tag] = 0
            pos = m.end()
        if pos < len(text):
            spans.append({
                "text": text[pos:],
                "b": flags["b"] > 0,
                "i": flags["i"] > 0,
                "u": flags["u"] > 0,
                "s": flags["s"] > 0,
                "code": flags["code"] > 0,
                "spoiler": flags["spoiler"] > 0,
            })

        merged: list = []
        for sp in spans:
            if not sp["text"]:
                continue
            if merged and all(
                merged[-1][k] == sp[k]
                for k in ("b", "i", "u", "s", "code", "spoiler")
            ):
                merged[-1]["text"] += sp["text"]
            else:
                merged.append(sp)

        widgets: list = []
        for sp in merged:
            txt = sp["text"]
            if not txt:
                continue

            color = theme.TEXT_PRIMARY
            if sp["spoiler"]:
                color = theme.TEXT_MUTED

            widgets.append(ft.Text(
                txt,
                size=13 if not sp["code"] else 12,
                color=color,
                weight=ft.FontWeight.BOLD if sp["b"] else ft.FontWeight.NORMAL,
                italic=sp["i"],
                font_family="monospace" if sp["code"] else None,
                selectable=True,
                no_wrap=False,
            ))

        if not widgets:
            widgets = [ft.Text(" ", size=13)]

        return ft.Column(controls=widgets, spacing=0, tight=True)

    # ------------------------------------------------------------------
    # Форма поста
    # ------------------------------------------------------------------

    def _open_post_form(self, slot: Optional[dict]) -> None:
        self._close_dialog()

        is_new = slot is None
        if is_new:
            slot = {"id": "", "weekday": 0, "time": "09:00",
                    "topic": "", "style": "simple",
                    "add_hashtags": False, "auto_add": True,
                    "enabled": True}

        weekday_dd = ft.Dropdown(
            value=str(slot.get("weekday", 0)),
            options=[ft.dropdown.Option(str(n), text=name)
                     for n, name in tg_scheduler.WEEKDAYS],
            width=220,
            fill_color=theme.BG_DARK, color=theme.TEXT_PRIMARY,
            border_radius=8, text_size=13,
            menu_height=280,
        )

        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]
        cur_hh, cur_mm = "09", "00"
        try:
            p = str(slot.get("time", "09:00")).split(":")
            cur_hh = p[0]; cur_mm = p[1]
        except Exception:
            pass

        hour_dd = ft.Dropdown(
            value=cur_hh,
            options=[ft.dropdown.Option(h) for h in hours],
            width=80,
            fill_color=theme.BG_DARK, color=theme.TEXT_PRIMARY,
            border_radius=8, text_size=13, menu_height=220,
        )
        minute_dd = ft.Dropdown(
            value=cur_mm,
            options=[ft.dropdown.Option(m) for m in minutes],
            width=80,
            fill_color=theme.BG_DARK, color=theme.TEXT_PRIMARY,
            border_radius=8, text_size=13, menu_height=220,
        )

        topic_field = ft.TextField(
            value=slot.get("topic", ""),
            hint_text="Тема поста",
            multiline=True, min_lines=2, max_lines=4,
            filled=True, fill_color=theme.BG_DARK,
            color=theme.TEXT_PRIMARY, border_radius=10,
            text_size=13,
        )

        styles = [
            ("simple", ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED),
            ("complex", ft.Icons.SCHOOL_ROUNDED),
            ("anti_ai", ft.Icons.PSYCHOLOGY_ROUNDED),
            ("humor", ft.Icons.SENTIMENT_VERY_SATISFIED_ROUNDED),
            ("scientific", ft.Icons.SCIENCE_ROUNDED),
        ]
        current_style = slot.get("style", "simple")
        style_containers = []

        def select_style(key):
            nonlocal current_style
            current_style = key
            for k, c in style_containers:
                active = k == key
                c.bgcolor = theme.PRIMARY if active else theme.SURFACE
                c.border = ft.border.all(2, theme.PRIMARY if active
                                         else theme.DRAWER_ITEM_BORDER)
                c.content.color = (ft.Colors.WHITE if active
                                   else theme.TEXT_PRIMARY)
            try:
                self.page.update()
            except Exception:
                pass

        styles_row = ft.Row(spacing=6)
        for k, icon in styles:
            is_active = k == current_style
            c = ft.Container(
                content=ft.Icon(icon, size=20,
                                color=ft.Colors.WHITE if is_active
                                else theme.TEXT_PRIMARY),
                width=44, height=44,
                bgcolor=theme.PRIMARY if is_active else theme.SURFACE,
                border=ft.border.all(2, theme.PRIMARY if is_active
                                     else theme.DRAWER_ITEM_BORDER),
                border_radius=10,
                alignment=ft.alignment.center,
                on_click=lambda e, kk=k: select_style(kk),
                ink=True,
            )
            style_containers.append((k, c))
            styles_row.controls.append(c)

        hashtags_switch = ft.Switch(
            value=bool(slot.get("add_hashtags", False)),
            active_color=theme.PRIMARY,
        )

        auto_add_switch = ft.Switch(
            value=bool(slot.get("auto_add", True)),
            active_color=theme.PRIMARY,
        )

        dialog = ft.AlertDialog(modal=False, bgcolor=theme.SURFACE)

        def save(ev):
            topic = (topic_field.value or "").strip()
            if not topic:
                self.page.open(ft.SnackBar(
                    content=ft.Text("Введи тему"), duration=1500,
                ))
                return
            time_str = f"{hour_dd.value or '09'}:{minute_dd.value or '00'}"
            weekday = int(weekday_dd.value or "0")

            all_slots = tg_scheduler.load_slots()
            if is_new:
                all_slots.append(tg_scheduler.make_slot(
                    weekday=weekday, time_str=time_str, topic=topic,
                    style=current_style,
                    add_hashtags=bool(hashtags_switch.value),
                    auto_add=bool(auto_add_switch.value),
                ))
            else:
                for s in all_slots:
                    if s.get("id") == slot.get("id"):
                        s.update(weekday=weekday, time=time_str,
                                 topic=topic, style=current_style,
                                 add_hashtags=bool(hashtags_switch.value),
                                 auto_add=bool(auto_add_switch.value))
                        break
            tg_scheduler.save_slots(all_slots)
            try:
                self.page.close(dialog)
            except Exception:
                pass
            self._refresh_plan()
            try:
                self.page.update()
            except Exception:
                pass

        def close(ev):
            try:
                self.page.close(dialog)
            except Exception:
                pass

        dialog.title = ft.Text("Новый пост" if is_new else "Изменить",
                               color=theme.TEXT_PRIMARY)
        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("День", size=11,
                            weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    weekday_dd,
                    ft.Container(height=10),
                    ft.Text("Время", size=11,
                            weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    ft.Row([hour_dd, ft.Text(":"), minute_dd],
                           spacing=6),
                    ft.Container(height=10),
                    ft.Text("Тема", size=11,
                            weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    topic_field,
                    ft.Container(height=10),
                    ft.Text("Стиль", size=11,
                            weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    styles_row,
                    ft.Container(height=10),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TAG_ROUNDED, size=16,
                                    color=theme.TEXT_MUTED),
                            ft.Text("Хештеги", size=12,
                                    color=theme.TEXT_PRIMARY),
                            ft.Container(expand=True),
                            hashtags_switch,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=6),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED,
                                    size=16, color=theme.TEXT_MUTED),
                            ft.Text("Автодобавление", size=12,
                                    color=theme.TEXT_PRIMARY),
                            ft.Container(expand=True),
                            auto_add_switch,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=4, tight=True,
            ),
            width=440,
        )

        dialog.actions = [
            ft.TextButton("Отмена", on_click=close),
            ft.ElevatedButton("Сохранить", bgcolor=theme.PRIMARY,
                              color=ft.Colors.WHITE, on_click=save),
        ]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        self._current_dialog = dialog
        self.page.open(dialog)
        try:
            self.page.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Форма бота
    # ------------------------------------------------------------------

    def _open_bot_form(self) -> None:
        self._close_dialog()
        title = "Изменить бота" if self.editing_bot_id else "Новый бот"

        if self.editing_bot_id:
            profile = get_current()
            if profile:
                for b in profile.tg_bots:
                    if b.get("id") == self.editing_bot_id:
                        self.token_field.value = b.get("token", "")
                        self.channel_field.value = b.get("channel", "")
                        break
        else:
            self.token_field.value = ""
            self.channel_field.value = ""
        self.status_text.value = ""

        def do_save(ev):
            profile = get_current()
            if not profile:
                return
            token = (self.token_field.value or "").strip()
            channel = (self.channel_field.value or "").strip()
            if not token or not channel:
                self.status_text.value = "❌ Заполни всё"
                self.status_text.color = theme.DANGER
                self.page.update()
                return

            ok, info, err = telegram.get_bot_info(token)
            if not ok:
                self.status_text.value = f"❌ {err}"
                self.status_text.color = theme.DANGER
                self.page.update()
                return

            name = info.get("first_name", "Бот")
            username = info.get("username", "")
            if self.editing_bot_id:
                profile.update_bot(self.editing_bot_id, token, channel,
                                   name, username)
            else:
                profile.add_bot(token, channel, name, username)
            profile.save()
            self.editing_bot_id = None
            self._close_dialog()
            self._refresh_bots()
            self._refresh_content()
            self.page.update()

        def do_delete(ev):
            profile = get_current()
            if profile and self.editing_bot_id:
                profile.remove_bot(self.editing_bot_id)
                profile.save()
            self.editing_bot_id = None
            self._close_dialog()
            self._refresh_bots()
            self._refresh_content()
            self.page.update()

        def do_test(ev):
            token = (self.token_field.value or "").strip()
            channel = (self.channel_field.value or "").strip()
            if not token or not channel:
                return
            ok, msg, bot = telegram.test_connection(token, channel)
            self.status_text.value = ("✅ " + msg) if ok else ("❌ " + msg)
            self.status_text.color = theme.SUCCESS if ok else theme.DANGER
            self.page.update()

        def close(ev):
            self._close_dialog()

        dialog = ft.AlertDialog(modal=False, bgcolor=theme.SURFACE)
        dialog.title = ft.Text(title, color=theme.TEXT_PRIMARY)
        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Токен", size=11,
                            weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    self.token_field,
                    ft.Container(height=8),
                    ft.Text("ID канала", size=11,
                            weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    self.channel_field,
                    ft.Container(height=8),
                    self.status_text,
                ],
                spacing=4, tight=True,
            ),
            width=420,
        )

        actions = []
        if self.editing_bot_id:
            actions.append(
                ft.TextButton("Удалить", on_click=do_delete)
            )
        actions.append(ft.TextButton("Отмена", on_click=close))
        actions.append(
            ft.TextButton("Проверить", on_click=do_test)
        )
        actions.append(
            ft.ElevatedButton("Сохранить", bgcolor=theme.PRIMARY,
                              color=ft.Colors.WHITE, on_click=do_save)
        )
        dialog.actions = actions
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