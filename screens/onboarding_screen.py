"""Экран регистрации (упрощенный)."""

import flet as ft
from services.user_profile import UserProfile
from services import auth_manager
from ui import theme


class OnboardingScreen:
    def __init__(
            self,
            page: ft.Page,
            on_finish,
            on_go_login=None,
            edit_mode: bool = False,
            initial_profile=None,
    ) -> None:
        self.page = page
        self.on_finish = on_finish
        self.on_go_login = on_go_login
        self.edit_mode = edit_mode

        self.name_value = ""
        if initial_profile:
            self.name_value = initial_profile.name

    def build(self) -> ft.Container:
        # Поля ввода с иконками
        self.login_field = ft.TextField(
            hint_text="Придумай логин",
            prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=10, border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY, text_size=15,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=12), height=48,
        )

        self.password_field = ft.TextField(
            hint_text="Придумай пароль",
            prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
            password=True, can_reveal_password=True,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=10, border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY, text_size=15,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=12), height=48,
        )

        self.confirm_field = ft.TextField(
            hint_text="Подтверди пароль",
            prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
            password=True, can_reveal_password=True,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=10, border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY, text_size=15,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=12), height=48,
        )

        self.name_field = ft.TextField(
            value=self.name_value,
            hint_text="Как тебя зовут?",
            prefix_icon=ft.Icons.BADGE_OUTLINED,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=10, border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY,
            text_size=15,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=12), height=48,
        )

        self.error_text = ft.Text("", color=theme.DANGER, size=13, visible=False)

        def on_register(e):
            user = self.login_field.value.strip()
            pwd = self.password_field.value.strip()
            conf = self.confirm_field.value.strip()
            name = self.name_field.value.strip()

            if not user or not pwd or not name:
                self.error_text.value = "Заполни все поля"
                self.error_text.visible = True
                self.error_text.update()
                return

            if pwd != conf:
                self.error_text.value = "Пароли не совпадают"
                self.error_text.visible = True
                self.error_text.update()
                return

            if len(pwd) < 4:
                self.error_text.value = "Пароль минимум 4 символа"
                self.error_text.visible = True
                self.error_text.update()
                return

            ok, msg = auth_manager.create_account(user, pwd)
            if not ok:
                self.error_text.value = msg
                self.error_text.visible = True
                self.error_text.update()
                return

            profile = UserProfile.load() or UserProfile()
            profile.name = name
            profile.save()

            self.on_finish(profile)

        register_btn = ft.ElevatedButton(
            "Зарегистрироваться",
            bgcolor=theme.SURFACE_HOVER,
            color=ft.Colors.WHITE,
            on_click=on_register,
            width=340,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=16
            )
        )

        def go_login(e):
            if self.on_go_login:
                self.on_go_login()

        login_link = ft.TextButton(
            "Уже есть аккаунт? Войти",
            on_click=go_login,
            style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)
        )

        # Карточка регистрации
        card = ft.Container(
            content=ft.Column(
                controls=[
                    # Блок с логотипом и текстом
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Image(src="logo_text.png", width=340, height=100, fit=ft.ImageFit.CONTAIN),
                                ft.Container(
                                    content=ft.Text(
                                        "Автоматизируй ведение соцсетей",
                                        size=14,
                                        color=theme.TEXT_SECONDARY,
                                        text_align=ft.TextAlign.CENTER
                                    ),
                                    margin=ft.margin.only(top=-35),
                                ),
                            ],
                            spacing=0,
                            tight=True,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        margin=ft.margin.only(top=-10),
                    ),

                    ft.Container(height=20),
                    self.login_field,
                    self.password_field,
                    self.confirm_field,
                    self.name_field,
                    self.error_text,
                    ft.Container(height=10),
                    register_btn,
                    ft.Container(height=5),
                    login_link,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                tight=True,
            ),
            padding=40,
            bgcolor=theme.BG_DARK,
            border_radius=24,
            border=ft.border.all(1, theme.SURFACE_HOVER),
            width=450,
        )

        return ft.Container(
            content=card,
            alignment=ft.alignment.center,
            expand=True,
            bgcolor=ft.Colors.BLACK,
        )