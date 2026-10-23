"""Экран настроек.

Пункты:
  • Профиль
  • Cloudflare ключ
  • Premium подписка
  • Ключ активации
  • Тема оформления
  • Фон приложения
  • Выйти
"""

from typing import Callable

import flet as ft

from services.user_profile import UserProfile, get_current
from ui import theme


BG_OPTIONS = [
    ("snow",      ft.Icons.AC_UNIT_ROUNDED,          "Снежинки",   "❄ зимний фон"),
    ("bubbles",   ft.Icons.BUBBLE_CHART_ROUNDED,     "Пузыри",     "◉ плавающие пузыри"),
    ("rain",      ft.Icons.WATER_DROP_ROUNDED,       "Дождь",      "💧 капли дождя"),
    ("stars",     ft.Icons.STAR_ROUNDED,             "Звёзды",     "✦ мерцающее небо"),
    ("matrix",    ft.Icons.GRID_ON_ROUNDED,          "Матрица",    "01 падающие символы"),
    ("fireflies", ft.Icons.LIGHT_MODE_ROUNDED,       "Светлячки",  "✨ тёплые точки"),
    ("sakura",    ft.Icons.LOCAL_FLORIST_ROUNDED,    "Сакура",     "🌸 падающие лепестки"),
    ("neon",      ft.Icons.BOLT_ROUNDED,             "Неон",       "⚡ светящиеся линии"),
    ("particles", ft.Icons.BLUR_ON_ROUNDED,          "Частицы",    "• точки и линии"),
    ("none",      ft.Icons.BLOCK_ROUNDED,            "Без фона",   "чёрный фон"),
]


class SettingsScreen:
    def __init__(
        self,
        page: ft.Page,
        on_open_profile: Callable[[], None],
        on_logout: Callable[[], None],
    ) -> None:
        self.page = page
        self.on_open_profile = on_open_profile
        self.on_logout = on_logout
        self._current_dialog = None

    def _close_current_dialog(self) -> None:
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

    # ------------------------------------------------------------------
    # Построение
    # ------------------------------------------------------------------

    def build(self) -> ft.Container:
        title = ft.Text(
            "Настройки", size=26, weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY, text_align=ft.TextAlign.CENTER,
        )
        subtitle = ft.Text(
            "Управляй профилем и параметрами приложения",
            size=13, color=theme.TEXT_SECONDARY,
            text_align=ft.TextAlign.CENTER,
        )

        profile = get_current()
        cf_status = (
            "✅ Ключ подключён" if profile and profile.cf_token
            else "⚠️ Не задан — генерация не работает"
        )
        cf_color = theme.SUCCESS if profile and profile.cf_token else theme.WARNING

        # ---------- Premium ----------
        premium_active = False
        premium_subtitle = "Не активна — открой, чтобы купить"
        premium_color = theme.TEXT_SECONDARY
        premium_badge_visible = False
        premium_badge_text = ""

        if profile and hasattr(profile, "is_premium") and profile.is_premium():
            premium_active = True
            days = profile.premium_days_left()
            premium_badge_visible = True
            if days == -1:
                premium_subtitle = "Навсегда · без ограничений"
                premium_badge_text = "∞"
            elif days > 30:
                months = days // 30
                premium_subtitle = f"Осталось {days} дней (~{months} мес)"
                premium_badge_text = f"{days} дн"
            else:
                premium_subtitle = f"Осталось {days} дней"
                premium_badge_text = f"{days} дн"
            premium_color = theme.SUCCESS

        # ---------- Пункты ----------
        profile_item = self._make_item(
            icon=ft.Icons.PERSON_ROUNDED, title="Профиль",
            subtitle="Имя, возраст, пол, интересы",
            on_click=lambda e: self.on_open_profile(),
            color=theme.PRIMARY,
        )
        cf_item = self._make_item(
            icon=ft.Icons.CLOUD_ROUNDED, title="Cloudflare ключ",
            subtitle=cf_status,
            on_click=lambda e: self._open_cf_editor(),
            color=theme.PRIMARY, subtitle_color=cf_color,
        )

        premium_item = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                            size=22, color="#FFC107",
                        ),
                        width=44, height=44,
                        bgcolor=ft.Colors.with_opacity(0.15, "#FFC107"),
                        border_radius=12,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            "Premium подписка", size=16,
                                            weight=ft.FontWeight.BOLD,
                                            color="#FFC107",
                                        ),
                                        ft.Container(
                                            content=ft.Text(
                                                premium_badge_text,
                                                size=10,
                                                weight=ft.FontWeight.BOLD,
                                                color=ft.Colors.WHITE,
                                            ),
                                            padding=ft.padding.symmetric(
                                                horizontal=8, vertical=3),
                                            bgcolor=theme.SUCCESS,
                                            border_radius=8,
                                            visible=premium_badge_visible,
                                        ),
                                    ],
                                    spacing=8, tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Text(
                                    premium_subtitle, size=12,
                                    color=premium_color,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=2, tight=True,
                        ),
                        expand=True,
                        margin=ft.margin.only(left=16),
                    ),
                    ft.Icon(
                        ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        size=20, color=theme.TEXT_MUTED,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            bgcolor=theme.SURFACE,
            border_radius=14,
            on_click=lambda e: self._open_subscription(),
            ink=True,
        )

        activation_item = self._make_item(
            icon=ft.Icons.KEY_ROUNDED,
            title="Ключ активации",
            subtitle="Введи ключ, полученный после оплаты",
            on_click=lambda e: self._open_activation(),
            color=theme.PRIMARY,
        )
        theme_item = self._make_item(
            icon=ft.Icons.PALETTE_ROUNDED, title="Тема оформления",
            subtitle=self._theme_label(),
            on_click=lambda e: self._open_theme_editor(),
            color=theme.PRIMARY,
        )
        bg_item = self._make_item(
            icon=ft.Icons.WALLPAPER_ROUNDED, title="Фон приложения",
            subtitle=self._bg_label(),
            on_click=lambda e: self._open_bg_editor(),
            color=theme.PRIMARY,
        )

        divider = ft.Container(
            height=1, bgcolor=theme.DIVIDER,
            margin=ft.margin.symmetric(vertical=8),
        )

        logout_item = self._make_item(
            icon=ft.Icons.LOGOUT_ROUNDED, title="Выйти",
            subtitle="Удалить профиль и выйти из аккаунта",
            on_click=lambda e: self._confirm_logout(),
            color=theme.DANGER, is_danger=True,
        )

        content = ft.Column(
            controls=[
                ft.Container(height=32),
                title,
                ft.Container(height=8),
                subtitle,
                ft.Container(height=32),
                profile_item,
                ft.Container(height=8),
                cf_item,
                ft.Container(height=8),
                premium_item,
                ft.Container(height=8),
                activation_item,
                ft.Container(height=8),
                theme_item,
                ft.Container(height=8),
                bg_item,
                ft.Container(height=8),
                divider,
                ft.Container(height=8),
                logout_item,
                ft.Container(height=32),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

        return ft.Container(
            content=ft.Container(
                content=ft.Column(
                    controls=[content],
                    scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=24),
                width=520,
            ),
            alignment=ft.alignment.top_center,
            padding=ft.padding.all(16),
            expand=True,
        )

    # ------------------------------------------------------------------
    # Переходы
    # ------------------------------------------------------------------

    def _open_subscription(self) -> None:
        try:
            chat = getattr(self.page, "_vagent_chat_screen", None)
            if chat is not None:
                chat._handle_nav("subscription")
                return
        except Exception as ex:
            print(f"[SETTINGS] open subscription error: {ex}")

    def _open_activation(self) -> None:
        try:
            chat = getattr(self.page, "_vagent_chat_screen", None)
            if chat is not None:
                chat._handle_nav("activation")
                return
        except Exception as ex:
            print(f"[SETTINGS] open activation error: {ex}")

    def _bg_label(self) -> str:
        profile = get_current()
        key = (profile.bg_effect if profile else "snow") or "snow"
        cs = float(profile.bg_count_scale) if profile else 1.0
        ss = float(profile.bg_size_scale) if profile else 1.0
        for k, _icon, name, _sub in BG_OPTIONS:
            if k == key:
                return f"{name} · x{cs:.1f} · {int(ss * 100)}%"
        return "Снежинки"

    def _theme_label(self) -> str:
        profile = get_current()
        key = getattr(profile, "ui_theme", "dark_purple") if profile else "dark_purple"
        palette = theme.THEMES.get(key, theme.THEMES["dark_purple"])
        return f"{palette['icon']} {palette['label']}"

    def _make_item(self, icon, title, subtitle, on_click,
                   color=theme.TEXT_PRIMARY, is_danger=False, subtitle_color=None):
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, size=22, color=color),
                        width=44, height=44,
                        bgcolor=(
                            ft.Colors.with_opacity(0.15, color)
                            if not is_danger
                            else ft.Colors.with_opacity(0.15, theme.DANGER)
                        ),
                        border_radius=12,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    title, size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=color,
                                ),
                                ft.Text(
                                    subtitle, size=12,
                                    color=subtitle_color or theme.TEXT_SECONDARY,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=2, tight=True,
                        ),
                        expand=True,
                        margin=ft.margin.only(left=16),
                    ),
                    ft.Icon(
                        ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        size=20, color=theme.TEXT_MUTED,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            bgcolor=theme.SURFACE,
            border_radius=14,
            on_click=on_click,
            ink=True,
        )

    # ------------------------------------------------------------------
    # Тема оформления
    # ------------------------------------------------------------------

    def _open_theme_editor(self) -> None:
        self._close_current_dialog()

        from screens.theme_screen import ThemeScreen
        import flet as ft

        # Передаем функцию закрытия, чтобы крестик внутри экрана работал
        screen = ThemeScreen(self.page, on_close=self._close_current_dialog)
        content = screen.build()

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            title=None,
            content=content,
            # Убрали actions, так как кнопки теперь внутри ThemeScreen
            actions=[],
        )

        self._current_dialog = dialog
        self.page.open(dialog)
        try:
            self.page.update()
        except Exception:
            pass
    # ------------------------------------------------------------------
    # Cloudflare ключ
    # ------------------------------------------------------------------

    def _open_cf_editor(self) -> None:
        self._close_current_dialog()
        profile = get_current()
        if not profile:
            return

        # --- Поля ввода ---
        field = ft.TextField(
            value=profile.cf_token or "",
            hint_text="cfut_...",
            password=True, can_reveal_password=True,
            filled=True, fill_color=theme.BG_DARK, color=theme.TEXT_PRIMARY,
            border_radius=12, border_color=theme.DRAWER_ITEM_BORDER,
            focused_border_color=theme.PRIMARY, text_size=14,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
        )

        account_field = ft.TextField(
            value=profile.cf_account or "",
            hint_text="Вставь 32 символа",
            filled=True, fill_color=theme.BG_DARK, color=theme.TEXT_PRIMARY,
            border_radius=12, border_color=theme.DRAWER_ITEM_BORDER,
            focused_border_color=theme.PRIMARY, text_size=14,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
        )

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CLOUD_ROUNDED, size=24, color=theme.PRIMARY),
                    ft.Text("Настройка Cloudflare", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY)
                ],
                spacing=10,
            ),
        )

        # --- Инструкция для Токена ---
        token_help = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Шаг 1. Получи API Токен", size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Container(height=6),
                    self._step_row("1", "Перейди на страницу API токенов:"),
                    ft.Row([
                        ft.Container(width=26),
                        ft.TextButton(
                            "dash.cloudflare.com/profile/api-tokens",
                            on_click=lambda e: self.page.launch_url("https://dash.cloudflare.com/profile/api-tokens"),
                            style=ft.ButtonStyle(color=theme.PRIMARY, padding=0),
                        )
                    ]),
                    self._step_row("2", "Нажми «Create Token» (Создать токен)."),
                    self._step_row("3", "Найди шаблон «Workers AI» и нажми «Use template»."),
                    self._step_row("4", "Пролистай вниз, нажми «Continue to summary», затем «Create Token»."),
                    self._step_row("5", "Скопируй токен (он показывается один раз) и вставь в поле ниже."),
                ],
                spacing=2,
            ),
            padding=16,
            bgcolor=ft.Colors.with_opacity(0.4, theme.BG_DARK),
            border_radius=12,
        )

        # --- Инструкция для Account ID ---
        account_help = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Шаг 2. Найди Account ID", size=15, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Container(height=6),
                    self._step_row("1", "Зайди на главную страницу Cloudflare:"),
                    ft.Row([
                        ft.Container(width=26),
                        ft.TextButton(
                            "dash.cloudflare.com",
                            on_click=lambda e: self.page.launch_url("https://dash.cloudflare.com/"),
                            style=ft.ButtonStyle(color=theme.PRIMARY, padding=0),
                        )
                    ]),
                    self._step_row("2", "Посмотри на адресную строку браузера."),
                    ft.Container(
                        content=ft.Text(
                            "dash.cloudflare.com/1234567890abcdef1234567890abcdef/home",
                            size=12, color=theme.TEXT_SECONDARY, font_family="monospace"
                        ),
                        padding=ft.padding.only(left=26, top=4, bottom=4),
                    ),
                    self._step_row("3", "Скопируй 32 символа (буквы и цифры) между .com/ и /home."),
                    self._step_row("4",
                                   "Вставь их в поле ниже. Можно вставить всю ссылку целиком — программа сама вытащит ID."),
                ],
                spacing=2,
            ),
            padding=16,
            bgcolor=ft.Colors.with_opacity(0.4, theme.BG_DARK),
            border_radius=12,
            margin=ft.margin.only(top=16),
        )

        # --- Сборка контента ---
        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Ключ нужен для работы ИИ (текст и картинки). "
                        "Данные сохраняются только на твоём устройстве.",
                        size=13, color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(height=16),

                    token_help,
                    ft.Container(height=8),
                    ft.Text("API Токен", size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    field,

                    account_help,
                    ft.Container(height=8),
                    ft.Text("Account ID", size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    account_field,
                ],
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=540,
            height=600,
        )

        def save(ev):
            from services import cf_config
            profile.cf_token = (field.value or "").strip()
            profile.cf_account = cf_config.parse_account_id(account_field.value or "")
            profile.save()
            self._close_current_dialog()
            self._reload_app()

        def close(ev):
            self._close_current_dialog()

        cancel_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CLOSE_ROUNDED, size=16, color=theme.TEXT_SECONDARY),
                    ft.Text("Отмена", size=13, color=theme.TEXT_SECONDARY),
                ],
                spacing=6, tight=True,
            ),
            on_click=close,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
            ),
        )

        save_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text("Сохранить", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                ],
                spacing=6, tight=True,
            ),
            bgcolor=theme.PRIMARY,
            on_click=save,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
        )

        dialog.actions = [cancel_btn, save_btn]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        self._current_dialog = dialog
        self.page.open(dialog)
        try:
            self.page.update()
        except Exception:
            pass
    def _step_row(self, num, text):
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            num, size=11, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        width=20, height=20, bgcolor=theme.PRIMARY,
                        border_radius=10, alignment=ft.alignment.center,
                    ),
                    ft.Text(text, size=12, color=theme.TEXT_SECONDARY),
                ],
                spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=3),
        )

    def _step_link_row(self, num, prefix, link_text, url):
        def open_url(e):
            try:
                self.page.launch_url(url)
            except Exception as ex:
                print(f"launch_url error: {ex}")
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            num, size=11, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        width=20, height=20, bgcolor=theme.PRIMARY,
                        border_radius=10, alignment=ft.alignment.center,
                    ),
                    ft.Text(prefix, size=12, color=theme.TEXT_SECONDARY),
                    ft.Container(
                        content=ft.Text(
                            link_text, size=12, color=theme.PRIMARY,
                            weight=ft.FontWeight.BOLD,
                        ),
                        on_click=open_url, ink=True,
                        tooltip=f"Открыть {url}",
                    ),
                ],
                spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=3),
        )

    # ------------------------------------------------------------------
    # Фон приложения
    # ------------------------------------------------------------------

    def _open_bg_editor(self) -> None:
        self._close_current_dialog()
        profile = get_current()
        if not profile:
            return

        current_key = profile.bg_effect or "snow"
        count_val = float(profile.bg_count_scale or 1.0)
        size_val = float(profile.bg_size_scale or 1.0)

        count_label = ft.Text(
            f"Количество: x{count_val:.1f}",
            size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY,
        )
        count_slider = ft.Slider(
            min=0.2, max=3.0, divisions=28, value=count_val,
            active_color=theme.PRIMARY,
            inactive_color=ft.Colors.with_opacity(0.2, theme.TEXT_SECONDARY),
            label="{value}",
        )

        def on_count(ev):
            v = float(ev.control.value)
            count_label.value = f"Количество: x{v:.1f}"
            try:
                count_label.update()
            except Exception:
                pass
        count_slider.on_change = on_count

        size_label = ft.Text(
            f"Размер: {int(size_val * 100)}%",
            size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY,
        )
        size_slider = ft.Slider(
            min=0.5, max=2.0, divisions=15, value=size_val,
            active_color=theme.PRIMARY,
            inactive_color=ft.Colors.with_opacity(0.2, theme.TEXT_SECONDARY),
            label="{value}",
        )

        def on_size(ev):
            v = float(ev.control.value)
            size_label.value = f"Размер: {int(v * 100)}%"
            try:
                size_label.update()
            except Exception:
                pass
        size_slider.on_change = on_size

        def make_option(key, icon, name, sub):
            is_active = key == current_key
            bg = (ft.Colors.with_opacity(0.2, theme.PRIMARY)
                  if is_active else theme.BG_DARK)
            border = theme.PRIMARY if is_active else theme.DRAWER_ITEM_BORDER
            icon_c = ft.Colors.WHITE if is_active else theme.TEXT_PRIMARY
            name_c = ft.Colors.WHITE if is_active else theme.TEXT_PRIMARY

            def pick(ev):
                profile.bg_effect = key
                profile.bg_count_scale = float(count_slider.value or 1.0)
                profile.bg_size_scale = float(size_slider.value or 1.0)
                profile.save()
                self._close_current_dialog()
                self._reload_app()

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(icon, size=22, color=icon_c),
                            width=44, height=44,
                            bgcolor=ft.Colors.with_opacity(0.15, theme.PRIMARY),
                            border_radius=12, alignment=ft.alignment.center,
                        ),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text(name, size=14,
                                            weight=ft.FontWeight.BOLD, color=name_c),
                                    ft.Text(sub, size=11, color=theme.TEXT_SECONDARY),
                                ],
                                spacing=2, tight=True,
                            ),
                            expand=True, margin=ft.margin.only(left=12),
                        ),
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED, size=20,
                            color=theme.PRIMARY if is_active else ft.Colors.TRANSPARENT,
                        ),
                    ],
                    spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=10),
                bgcolor=bg, border=ft.border.all(2, border),
                border_radius=12, on_click=pick, ink=True,
                margin=ft.margin.only(bottom=8),
            )

        options_col = ft.Column(
            controls=[make_option(k, i, n, s) for k, i, n, s in BG_OPTIONS],
            spacing=0, tight=True,
        )

        def apply_only(ev):
            profile.bg_count_scale = float(count_slider.value or 1.0)
            profile.bg_size_scale = float(size_slider.value or 1.0)
            profile.save()
            self._close_current_dialog()
            self._reload_app()

        def close(ev):
            self._close_current_dialog()

        dialog = ft.AlertDialog(modal=True, bgcolor=theme.SURFACE)
        dialog.title = ft.Text("Фон приложения", color=theme.TEXT_PRIMARY)
        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Эффект", size=12, color=theme.TEXT_SECONDARY,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(height=8),
                    options_col,
                    ft.Container(height=14),
                    ft.Container(height=1, bgcolor=theme.DIVIDER),
                    ft.Container(height=10),
                    count_label,
                    ft.Container(height=4),
                    count_slider,
                    ft.Container(height=14),
                    size_label,
                    ft.Container(height=4),
                    size_slider,
                ],
                spacing=0, tight=True, scroll=ft.ScrollMode.AUTO,
            ),
            width=460, height=520,
        )

        cancel_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CLOSE_ROUNDED, size=16,
                            color=theme.TEXT_SECONDARY),
                    ft.Text("Отмена", size=13,
                            color=theme.TEXT_SECONDARY),
                ],
                spacing=6, tight=True,
            ),
            on_click=close,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, theme.DRAWER_ITEM_BORDER),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
            ),
        )

        apply_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_ROUNDED, size=16,
                            color=ft.Colors.WHITE),
                    ft.Text("Применить", size=13,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=6, tight=True,
            ),
            bgcolor=theme.PRIMARY,
            on_click=apply_only,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=18, vertical=12),
            ),
        )

        dialog.actions = [cancel_btn, apply_btn]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        self._current_dialog = dialog
        self.page.open(dialog)
        try:
            self.page.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Перезагрузка и выход
    # ------------------------------------------------------------------

    def _reload_app(self) -> None:
        try:
            old_screen = getattr(self.page, "_vagent_chat_screen", None)
            if old_screen is not None:
                try:
                    if hasattr(old_screen, "stop_effect"):
                        old_screen.stop_effect()
                except Exception:
                    pass
                try:
                    if hasattr(old_screen, "_stop_thinking"):
                        old_screen._stop_thinking(remove_widget=True)
                except Exception:
                    pass
                try:
                    if getattr(old_screen, "_bg_effect", None) is not None:
                        old_screen._bg_effect.stop()
                        old_screen._bg_effect = None
                except Exception:
                    pass
                try:
                    for s in list(getattr(old_screen, "_screen_cache", {}).values()):
                        if hasattr(s, "stop_effect"):
                            s.stop_effect()
                except Exception:
                    pass

            from screens.chat_screen import ChatScreen
            from services.user_profile import get_current, set_current
            p = get_current()
            if p:
                set_current(p)

            self.page.controls.clear()
            new_screen = ChatScreen(self.page)
            try:
                setattr(self.page, "_vagent_chat_screen", new_screen)
            except Exception:
                pass
            self.page.add(new_screen.build())
            self.page.update()
        except Exception as ex:
            print(f"[SETTINGS] reload error: {ex}")

    def _confirm_logout(self) -> None:
        self._close_current_dialog()

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=24, color=theme.DANGER),
                    ft.Text("Выход из аккаунта", size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY)
                ],
                spacing=10,
            ),
        )

        def do_logout(e):
            self._close_current_dialog()
            self.on_logout()

        def do_cancel(e):
            self._close_current_dialog()

        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Вы уверены, что хотите выйти?",
                        size=15, color=theme.TEXT_PRIMARY, weight=ft.FontWeight.W_500
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        "Профиль и все проекты будут удалены с этого устройства. "
                        "При следующем входе придётся создавать аккаунт заново.",
                        size=13, color=theme.TEXT_SECONDARY,
                    ),
                ],
                spacing=0,
                tight=True,
            ),
            width=420,
            padding=ft.padding.only(top=10, bottom=10),
        )

        # Стильные кнопки
        cancel_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CLOSE_ROUNDED, size=16, color=theme.TEXT_SECONDARY),
                    ft.Text("Отмена", size=14, color=theme.TEXT_SECONDARY),
                ],
                spacing=6, tight=True,
            ),
            on_click=do_cancel,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        logout_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text("Выйти", size=14, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                ],
                spacing=6, tight=True,
            ),
            bgcolor=theme.DANGER,
            on_click=do_logout,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),
        )

        dialog.actions = [cancel_btn, logout_btn]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        self._current_dialog = dialog
        self.page.open(dialog)
        try:
            self.page.update()
        except Exception:
            pass