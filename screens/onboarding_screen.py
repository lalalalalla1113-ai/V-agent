"""Экран регистрации (онбординг) — 6 шагов.

Шаги: Имя → Возраст → Пол → Интересы → Аудитория → Токен Cloudflare.
Адаптивно под мобильные экраны + красная рамка на ошибке поля.
"""

import threading
from typing import Callable, Optional

import flet as ft

from services.user_profile import UserProfile
from ui import theme


TOTAL_STEPS = 6


INTERESTS = [
    ("tech",       "📱", "Технологии"),
    ("sport",      "💪", "Спорт и здоровье"),
    ("food",       "🍳", "Кулинария"),
    ("travel",     "✈️", "Путешествия"),
    ("games",      "🎮", "Игры"),
    ("art",        "🎨", "Искусство"),
    ("books",      "📚", "Книги"),
    ("music",      "🎵", "Музыка"),
    ("business",   "💼", "Бизнес"),
    ("selfdev",    "🌱", "Саморазвитие"),
    ("pets",       "🐾", "Питомцы"),
    ("cinema",     "🎬", "Кино"),
    ("photo",      "📸", "Фотография"),
    ("auto",       "🚗", "Авто"),
]


def _is_mobile(page: ft.Page) -> bool:
    """Определяет, мобильное ли устройство."""
    try:
        if page.platform in ("android", "ios"):
            return True
    except Exception:
        pass
    try:
        w = int(page.width or 0)
        return w > 0 and w < 700
    except Exception:
        return False


class OnboardingScreen:
    """Экран пошаговой регистрации."""

    def __init__(
        self,
        page: ft.Page,
        on_finish: Callable[[UserProfile], None],
        edit_mode: bool = False,
        initial_profile: Optional[UserProfile] = None,
    ) -> None:
        self.page = page
        self.on_finish = on_finish
        self.edit_mode = edit_mode
        self.mobile = _is_mobile(page)

        if initial_profile:
            self.name_value = initial_profile.name
            self.age_value = str(initial_profile.age) if initial_profile.age else ""
            self.gender_value = initial_profile.gender
            self.interests_value = list(initial_profile.interests)
            self.audience_value = initial_profile.audience
            self.cf_token_value = getattr(initial_profile, "cf_token", "")
        else:
            self.name_value = ""
            self.age_value = ""
            self.gender_value = ""
            self.interests_value = []
            self.audience_value = ""
            self.cf_token_value = ""

        self.current_step = 1

        self.step_container = ft.Container(
            expand=True,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
            opacity=1,
        )

        self.progress_container = ft.Container()

        self.back_button = ft.ElevatedButton(
            text="← Назад",
            bgcolor=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            on_click=self._handle_back,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=20, vertical=14),
            ),
            visible=False,
        )

        self.next_button = ft.ElevatedButton(
            text="Далее →",
            bgcolor=theme.PRIMARY,
            color=theme.TEXT_PRIMARY,
            on_click=self._handle_next,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=20, vertical=14),
            ),
        )

        self.step_label = ft.Text(
            "",
            size=12,
            color=theme.TEXT_SECONDARY,
            text_align=ft.TextAlign.CENTER,
        )

        self._current_field_ref: list = []

    # ---------- Построение ----------

    def build(self) -> ft.Container:
        self._render_progress()
        self._render_step()

        buttons_row = ft.Row(
            controls=[self.back_button, self.next_button],
            spacing=12,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        if self.mobile:
            bottom_pad = 90
            top_pad = 20
            bottom_block_pad = 20
        else:
            bottom_pad = 24
            top_pad = 32
            bottom_block_pad = 24

        bottom_block = ft.Container(
            content=ft.Column(
                controls=[self.step_label, buttons_row],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(
                horizontal=16, vertical=bottom_block_pad,
            ),
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=self.progress_container,
                        padding=ft.padding.only(top=top_pad, bottom=12),
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "Привет! Давай познакомимся"
                                    if not self.edit_mode else "Профиль",
                                    size=22 if self.mobile else 24,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Container(height=4),
                                ft.Text(
                                    "Это поможет ИИ писать тексты специально для тебя"
                                    if not self.edit_mode
                                    else "Можешь изменить любые данные",
                                    size=12 if self.mobile else 13,
                                    color=theme.TEXT_SECONDARY,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            spacing=0,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=16),
                    ),
                    ft.Container(height=12 if self.mobile else 24),
                    ft.Container(
                        content=self.step_container,
                        expand=True,
                        padding=ft.padding.symmetric(
                            horizontal=16 if self.mobile else 24,
                        ),
                    ),
                    bottom_block,
                    ft.Container(height=bottom_pad),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            bgcolor=theme.BG_DARK,
            expand=True,
        )

    # ---------- Прогресс ----------

    def _render_progress(self) -> None:
        controls = []
        for i in range(1, TOTAL_STEPS + 1):
            if i == self.current_step:
                state = "active"
            elif i < self.current_step:
                state = "done"
            else:
                state = "future"

            controls.append(self._make_circle(i, state))

            if i < TOTAL_STEPS:
                line_color = (
                    ft.Colors.with_opacity(0.3, theme.TEXT_SECONDARY)
                    if i < self.current_step
                    else ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY)
                )
                controls.append(ft.Container(
                    width=14 if self.mobile else 18,
                    height=2, bgcolor=line_color, border_radius=1,
                ))

        self.progress_container.content = ft.Row(
            controls=controls,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        )

    def _make_circle(self, num: int, state: str) -> ft.Control:
        if state == "active":
            bg = theme.SURFACE
            border_color = theme.TEXT_SECONDARY
            text_color = theme.TEXT_PRIMARY
        elif state == "done":
            bg = ft.Colors.with_opacity(0.3, theme.TEXT_SECONDARY)
            border_color = ft.Colors.TRANSPARENT
            text_color = theme.TEXT_PRIMARY
        else:
            bg = ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY)
            border_color = ft.Colors.TRANSPARENT
            text_color = theme.TEXT_SECONDARY

        size = 24 if self.mobile else 28

        return ft.Container(
            content=ft.Container(
                content=ft.Text(
                    str(num), size=11 if self.mobile else 12,
                    weight=ft.FontWeight.BOLD,
                    color=text_color, text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.alignment.center,
            ),
            width=size, height=size, border_radius=size // 2,
            bgcolor=bg,
            border=ft.border.all(2, border_color),
            alignment=ft.alignment.center,
        )

    # ---------- Рендер шага ----------

    def _render_step(self) -> None:
        self._current_field_ref.clear()

        if self.current_step == 1:
            new_content = self._step_name()
            self.step_label.value = f"Шаг 1 из {TOTAL_STEPS} · Имя"
        elif self.current_step == 2:
            new_content = self._step_age()
            self.step_label.value = f"Шаг 2 из {TOTAL_STEPS} · Возраст"
        elif self.current_step == 3:
            new_content = self._step_gender()
            self.step_label.value = f"Шаг 3 из {TOTAL_STEPS} · Пол"
        elif self.current_step == 4:
            new_content = self._step_interests()
            self.step_label.value = f"Шаг 4 из {TOTAL_STEPS} · Интересы"
        elif self.current_step == 5:
            new_content = self._step_audience()
            self.step_label.value = f"Шаг 5 из {TOTAL_STEPS} · Аудитория"
        else:
            new_content = self._step_cf_token()
            self.step_label.value = f"Шаг 6 из {TOTAL_STEPS} · Cloudflare"

        self.step_container.content = new_content
        self.step_container.opacity = 0

        self.back_button.visible = self.current_step > 1

        if self.current_step == TOTAL_STEPS:
            self.next_button.text = (
                "Сохранить ✓" if self.edit_mode else "Завершить 🚀"
            )
        else:
            self.next_button.text = "Далее →"

        self._render_progress()

        try:
            self.page.update()
        except Exception:
            pass

        def _fade_in():
            self.step_container.opacity = 1
            try:
                self.step_container.update()
            except Exception:
                pass

        threading.Timer(0.02, _fade_in).start()

    # ---------- Ошибка поля ----------

    def _shake_and_red(self, field, error_text: str = "") -> None:
        if field is not None:
            try:
                field.border_color = "#FF5252"
                field.focused_border_color = "#FF5252"
                field.update()
            except Exception:
                pass

            def _reset_color():
                try:
                    field.border_color = theme.SURFACE
                    field.focused_border_color = theme.PRIMARY
                    field.update()
                except Exception:
                    pass

            threading.Timer(1.5, _reset_color).start()

        if error_text:
            try:
                self.page.open(ft.SnackBar(
                    content=ft.Text(error_text, color=ft.Colors.WHITE),
                    bgcolor="#FF5252",
                    duration=2000,
                ))
            except Exception:
                pass

        if self.mobile:
            try:
                if hasattr(self.page, "vibrate_light"):
                    self.page.vibrate_light()
            except Exception:
                pass

    # ---------- Шаги ----------

    def _step_name(self) -> ft.Control:
        field = ft.TextField(
            value=self.name_value,
            hint_text="Например, Аня",
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=12, border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY,
            text_size=16,
            autofocus=True,
            on_change=self._on_name_change,
        )
        self._current_field_ref.append(field)

        return ft.Column(
            controls=[
                ft.Text("Как тебя зовут?", size=16,
                        color=theme.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(height=12),
                field,
                ft.Container(height=4),
                ft.Text("Так тебя будет звать ИИ", size=11,
                        color=theme.TEXT_SECONDARY, italic=True),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _step_age(self) -> ft.Control:
        field = ft.TextField(
            value=self.age_value,
            hint_text="Например, 27",
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=12, border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY,
            text_size=16,
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True,
            on_change=self._on_age_change,
        )
        self._current_field_ref.append(field)

        return ft.Column(
            controls=[
                ft.Text("Сколько тебе лет?", size=16,
                        color=theme.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(height=12),
                field,
                ft.Container(height=4),
                ft.Text("Это поможет подобрать стиль общения", size=11,
                        color=theme.TEXT_SECONDARY, italic=True),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _step_gender(self) -> ft.Control:
        male_active = self.gender_value == "male"
        female_active = self.gender_value == "female"

        def card(gender, label, icon, active, color):
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=32,
                                color=ft.Colors.WHITE if active else theme.TEXT_SECONDARY),
                        ft.Container(width=14),
                        ft.Text(label, size=16, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE if active else theme.TEXT_PRIMARY),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                ),
                width=260 if self.mobile else 280,
                height=72,
                padding=ft.padding.symmetric(horizontal=20),
                bgcolor=(ft.Colors.with_opacity(0.2, color) if active else theme.SURFACE),
                border=ft.border.all(2, color if active else ft.Colors.TRANSPARENT),
                border_radius=16,
                alignment=ft.alignment.center_left,
                on_click=lambda e: self._on_gender_change(gender),
                ink=True,
            )

        return ft.Column(
            controls=[
                ft.Text("Твой пол", size=16,
                        color=theme.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(height=12),
                ft.Column(
                    controls=[
                        card("male", "Мужчина", ft.Icons.MAN_ROUNDED,
                             male_active, ft.Colors.BLUE),
                        card("female", "Женщина", ft.Icons.WOMAN_ROUNDED,
                             female_active, theme.PRIMARY),
                    ],
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _step_interests(self) -> ft.Control:
        cards = []
        for key, emoji, label in INTERESTS:
            is_active = key in self.interests_value
            cards.append(ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(emoji, size=20 if self.mobile else 26),
                        ft.Container(height=2),
                        ft.Text(label, size=9 if self.mobile else 11,
                                color=theme.TEXT_PRIMARY,
                                text_align=ft.TextAlign.CENTER, max_lines=2),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=0,
                ),
                width=72 if self.mobile else 95,
                height=72 if self.mobile else 95,
                bgcolor=(ft.Colors.with_opacity(0.15, theme.PRIMARY)
                         if is_active else theme.SURFACE),
                border=ft.border.all(2, theme.PRIMARY
                                     if is_active else ft.Colors.TRANSPARENT),
                border_radius=14,
                alignment=ft.alignment.center,
                on_click=lambda e, k=key: self._toggle_interest(k),
                ink=True,
            ))

        grid = ft.Row(
            controls=cards,
            spacing=8,
            run_spacing=8,
            wrap=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        return ft.Column(
            controls=[
                ft.Text("Что тебе интересно?", size=16,
                        color=theme.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                ft.Text("Можно выбрать несколько", size=12,
                        color=theme.TEXT_SECONDARY),
                ft.Container(height=12),
                grid,
                ft.Container(height=20),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

    def _step_audience(self) -> ft.Control:
        field = ft.TextField(
            value=self.audience_value,
            hint_text="Например, мамы 20-35 лет, IT-специалисты…",
            multiline=True, min_lines=3, max_lines=5,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=12, border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY,
            text_size=14,
            on_change=self._on_audience_change,
        )
        return ft.Column(
            controls=[
                ft.Text("Под какую аудиторию работаешь?", size=16,
                        color=theme.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                ft.Text("Необязательно — можно пропустить",
                        size=12, color=theme.TEXT_SECONDARY),
                ft.Container(height=12),
                field,
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _step_cf_token(self) -> ft.Control:
        instruction = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Как получить ключ:", size=13,
                            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Container(height=8),
                    self._step_link_row("1", "Открой",
                                        "dash.cloudflare.com/profile/api-tokens",
                                        "https://dash.cloudflare.com/profile/api-tokens"),
                    self._step_row("2", "Найди «API token templates»"),
                    self._step_row("3", "Нажми Use template → Workers AI"),
                    self._step_row("4", "Continue to summary → Create Token"),
                    self._step_row("5", "Скопируй и вставь сюда"),
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.padding.all(12),
            bgcolor=theme.SURFACE, border_radius=12,
        )

        key_field = ft.TextField(
            value=self.cf_token_value,
            hint_text="cfut_...",
            password=True, can_reveal_password=True,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=12, border_color=theme.SURFACE,
            focused_border_color=theme.PRIMARY,
            text_size=14,
            on_change=self._on_cf_token_change,
        )

        return ft.Column(
            controls=[
                ft.Text("Подключи Cloudflare", size=16,
                        color=theme.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                ft.Text("Ключ нужен для картинок и текста",
                        size=12, color=theme.TEXT_SECONDARY),
                ft.Container(height=12),
                instruction,
                ft.Container(height=12),
                key_field,
                ft.Container(height=8),
                ft.Text("Необязательно. Можно добавить позже в Настройках.",
                        size=11, color=theme.TEXT_SECONDARY, italic=True),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _step_row(self, num, text):
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(num, size=10, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                        text_align=ft.TextAlign.CENTER),
                        width=18, height=18, bgcolor=theme.PRIMARY,
                        border_radius=9, alignment=ft.alignment.center,
                    ),
                    ft.Text(text, size=11, color=theme.TEXT_SECONDARY),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
                        content=ft.Text(num, size=10, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                        text_align=ft.TextAlign.CENTER),
                        width=18, height=18, bgcolor=theme.PRIMARY,
                        border_radius=9, alignment=ft.alignment.center,
                    ),
                    ft.Text(prefix, size=11, color=theme.TEXT_SECONDARY),
                    ft.Container(
                        content=ft.Text(link_text, size=11, color=theme.PRIMARY,
                                        weight=ft.FontWeight.BOLD),
                        on_click=open_url, ink=True,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=3),
        )

    # ---------- Обработчики ----------

    def _on_name_change(self, e) -> None:
        self.name_value = e.control.value or ""

    def _on_age_change(self, e) -> None:
        v = "".join(ch for ch in (e.control.value or "") if ch.isdigit())
        if v != e.control.value:
            e.control.value = v
            try:
                e.control.update()
            except Exception:
                pass
        self.age_value = v

    def _on_audience_change(self, e) -> None:
        self.audience_value = e.control.value or ""

    def _on_cf_token_change(self, e) -> None:
        self.cf_token_value = (e.control.value or "").strip()

    def _on_gender_change(self, gender: str) -> None:
        self.gender_value = gender
        self.step_container.opacity = 0
        try:
            self.page.update()
        except Exception:
            pass

        def _set_and_fade():
            self.step_container.content = self._step_gender()
            self.step_container.opacity = 1
            try:
                self.page.update()
            except Exception:
                pass

        threading.Timer(0.05, _set_and_fade).start()

    def _toggle_interest(self, key: str) -> None:
        if key in self.interests_value:
            self.interests_value.remove(key)
        else:
            self.interests_value.append(key)
        self.step_container.content = self._step_interests()
        try:
            self.page.update()
        except Exception:
            pass

    # ---------- Навигация ----------

    def _handle_next(self, e) -> None:
        if not self._validate_current_step():
            return

        if self.current_step == TOTAL_STEPS:
            self._finish()
            return

        self.current_step += 1
        self._render_step()

    def _handle_back(self, e) -> None:
        if self.current_step > 1:
            self.current_step -= 1
            self._render_step()

    def _validate_current_step(self) -> bool:
        field = self._current_field_ref[0] if self._current_field_ref else None

        if self.current_step == 1:
            if not self.name_value.strip():
                self._shake_and_red(field, "Введи своё имя")
                return False
        elif self.current_step == 2:
            if not self.age_value.strip():
                self._shake_and_red(field, "Введи свой возраст")
                return False
            try:
                age = int(self.age_value)
                if age < 5 or age > 120:
                    self._shake_and_red(field, "Возраст от 5 до 120")
                    return False
            except ValueError:
                self._shake_and_red(field, "Возраст — это число")
                return False
        elif self.current_step == 3:
            if not self.gender_value:
                self._show_error("Выбери пол")
                return False
        elif self.current_step == 4:
            if not self.interests_value:
                self._show_error("Выбери хотя бы один интерес")
                return False
        return True

    def _show_error(self, text: str) -> None:
        try:
            self.page.open(ft.SnackBar(
                content=ft.Text(text, color=ft.Colors.WHITE),
                bgcolor="#FF5252",
                duration=2000,
            ))
        except Exception:
            pass

    def _finish(self) -> None:
        """Сохраняет профиль. При редактировании — НЕ теряет настройки."""
        initial = None
        try:
            initial = UserProfile.load()
        except Exception:
            pass

        if initial is not None:
            # Редактирование — обновляем ТОЛЬКО анкетные поля,
            # все остальные настройки (тема, фон, боты, Account ID и т.д.)
            # остаются нетронутыми.
            initial.name = self.name_value.strip()
            initial.age = int(self.age_value) if self.age_value.strip() else 0
            initial.gender = self.gender_value
            initial.interests = list(self.interests_value)
            initial.audience = self.audience_value.strip()
            initial.cf_token = self.cf_token_value.strip()
            profile = initial
        else:
            # Первая регистрация — создаём с дефолтами
            profile = UserProfile(
                name=self.name_value.strip(),
                age=int(self.age_value) if self.age_value.strip() else 0,
                gender=self.gender_value,
                interests=list(self.interests_value),
                audience=self.audience_value.strip(),
                cf_token=self.cf_token_value.strip(),
            )

        profile.save()
        self.on_finish(profile)