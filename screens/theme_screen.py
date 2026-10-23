"""Экран выбора цветовой темы."""

import flet as ft
import threading
import time
from ui import theme
from services.user_profile import get_current


class ThemeScreen:
    def __init__(self, page: ft.Page, on_close=None) -> None:
        self.page = page
        self.on_close = on_close
        self.profile = get_current()

        # Текущий цвет
        self.current_color = getattr(self.profile, "ui_theme", "dark_purple") if self.profile else "dark_purple"

        self.cards_row = ft.Row(
            spacing=16,
            alignment=ft.MainAxisAlignment.CENTER,
            wrap=True,
            run_spacing=16
        )

    def build(self) -> ft.Control:
        # Шапка с крестиком слева
        top_bar = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_color=theme.TEXT_SECONDARY,
                    icon_size=20,
                    tooltip="Закрыть",
                    on_click=lambda e: self._close_dialog(),
                ),
                ft.Container(expand=True),
            ],
            alignment=ft.MainAxisAlignment.START,
        )

        header = ft.Column(
            controls=[
                ft.Text("Цветовая тема", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                ft.Text("Выбери цветовую гамму. Применится после нажатия.", size=13, color=theme.TEXT_SECONDARY),
            ],
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self._render_cards()

        # Одна общая кнопка
        btn_apply = ft.ElevatedButton(
            "Применить тему",
            bgcolor="#E53935",  # Ярко-красный
            color=ft.Colors.WHITE,
            on_click=self._apply_theme,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=32, vertical=16),
            ),
            width=300,
        )

        content = ft.Column(
            controls=[
                top_bar,
                header,
                ft.Container(height=24),
                self.cards_row,
                ft.Container(height=32),
                ft.Row([btn_apply], alignment=ft.MainAxisAlignment.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        )

        # Чуть расширил контейнер, чтобы вытянутые карточки влезали
        return ft.Container(content=content, padding=ft.padding.all(10), width=700)

    def _render_cards(self):
        self.cards_row.controls.clear()

        for key, palette in theme.get_themes():
            is_active = (key == self.current_color)
            self.cards_row.controls.append(self._make_theme_card(key, palette, is_active))

        try:
            self.cards_row.update()
        except:
            pass

    def _make_theme_card(self, key: str, palette: dict, is_active: bool) -> ft.Container:
        c_primary = palette["PRIMARY"]
        c_bg = palette["BG_DARK"]

        # 1. УВЕЛИЧИЛИ РАЗМЕРЫ (чтобы были вытянутые)
        W, H = 180, 110

        # 2. Создаем визуальный блок.
        # Так как мы добавили clip_behavior родителю,
        # градиент растянется на весь блок и обрежется по краям ровно.
        preview_block = ft.Container(
            width=W,
            height=H,
            # Градиент от левого верхнего к правому нижнему углу.
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[c_primary, c_primary, c_bg, c_bg],
                stops=[0.0, 0.5, 0.5, 1.0],
            ),
        )

        title_text = ft.Text(
            palette["label"],
            size=13,
            weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY,
            text_align=ft.TextAlign.CENTER,
            max_lines=2
        )

        def on_click(e):
            self.current_color = key
            self._render_cards()

        border = ft.border.all(3, theme.PRIMARY) if is_active else ft.border.all(1, theme.DRAWER_ITEM_BORDER)

        # 3. УБРАЛИ АНИМАЦИЮ РАЗМЕРА (on_hover и animate_scale),
        # чтобы карточка не «прыгала» при наведении.
        card = ft.Container(
            content=ft.Column(
                controls=[
                    # Оборачиваем превью в контейнер с clip_behavior,
                    # чтобы градиент обрезался по скругленным краям карточки
                    ft.Container(
                        content=preview_block,
                        width=W,
                        height=H,
                        border_radius=ft.border_radius.only(top_left=14, top_right=14),
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    ),
                    ft.Container(
                        content=title_text,
                        padding=ft.padding.symmetric(horizontal=8, vertical=12),
                        alignment=ft.alignment.center,
                    )
                ],
                spacing=0,
                tight=True,
            ),
            width=W,  # Ширина карточки = ширине превью
            bgcolor=theme.SURFACE,
            border=border,
            border_radius=14,
            on_click=on_click,
            ink=True,
            # Убрал animate_scale и scale, чтобы не было дерганья
        )

        return card

    def _close_dialog(self):
        if self.on_close:
            self.on_close()
        else:
            try:
                for control in self.page.overlay:
                    if isinstance(control, ft.AlertDialog):
                        self.page.close(control)
                        break
            except:
                pass

    def _apply_theme(self, e):
        if not self.profile:
            return

        self.profile.ui_theme = self.current_color
        self.profile.ui_style = "classic"
        self.profile.save()

        theme.apply(self.current_color)

        self.page.open(ft.SnackBar(
            content=ft.Text(f"Тема {theme.THEMES[self.current_color]['label']} применена!"),
            duration=1500,
        ))

        self._close_dialog()
        self._reload_app_async()

    def _reload_app_async(self):
        def _reload():
            time.sleep(0.3)
            try:
                from screens.chat_screen import ChatScreen
                self.page.controls.clear()
                new_screen = ChatScreen(self.page)
                setattr(self.page, "_vagent_chat_screen", new_screen)
                self.page.add(new_screen.build())
                self.page.update()
            except Exception as ex:
                print(f"[THEME] reload error: {ex}")

        threading.Thread(target=_reload, daemon=True).start()