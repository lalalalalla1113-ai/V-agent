import flet as ft
from services import auth_manager
from ui import theme


class AuthScreen:
    def __init__(self, page: ft.Page, on_success, on_register) -> None:
        self.page = page
        self.on_success = on_success
        self.on_register = on_register

    def build(self) -> ft.Container:
        # Поля ввода с иконками
        self.login_field = ft.TextField(
            hint_text="Логин",
            prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=10,
            border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY,
            text_size=15,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=12),
            height=48,
        )

        self.password_field = ft.TextField(
            hint_text="Пароль",
            prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
            password=True,
            can_reveal_password=True,
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=10,
            border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY,
            text_size=15,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=12),
            height=48,
        )

        self.error_text = ft.Text("", color=theme.DANGER, size=13, visible=False)

        def on_login(e):
            user = self.login_field.value
            pwd = self.password_field.value
            ok, result = auth_manager.login(user, pwd)

            if ok:
                self.on_success()
            else:
                self.password_field.value = ""
                self.password_field.update()
                self.error_text.value = result
                self.error_text.visible = True
                self.error_text.update()

        login_btn = ft.ElevatedButton(
            "Войти",
            bgcolor=theme.SURFACE_HOVER,
            color=ft.Colors.WHITE,
            on_click=on_login,
            width=340,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=16
            )
        )

        register_btn = ft.TextButton(
            "Нет аккаунта? Создать",
            on_click=lambda e: self.on_register(),
            style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)
        )

        # Карточка входа
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

                    ft.Container(height=30),
                    self.login_field,
                    self.password_field,
                    self.error_text,
                    ft.Container(height=10),
                    login_btn,
                    ft.Container(height=10),
                    register_btn,
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