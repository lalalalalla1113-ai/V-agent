"""Главный экран-чат: боковая панель + лента + нижний блок + фон."""

import shutil
import threading
from pathlib import Path
from typing import Optional

import flet as ft

from screens.projects_drawer import ProjectsDrawer
from services import storage, text_ai
from services import paths as _paths
from services.models import Message
from state import state
from ui import theme
from ui.message_bubble import create_message_bubble, create_thinking_bubble
from ui.sidebar import Sidebar, SidebarItem
from ui.style_buttons import create_style_buttons
from ui.effects import create_effect


def _is_mobile(page: ft.Page) -> bool:
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


class ChatScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._ensure_project_loaded()
        self.mobile = _is_mobile(page)

        # Вложения храним в РЕАЛЬНОЙ папке данных
        self.attachments_dir = _paths.data_dir() / "attachments"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

        self.pending_attachments: list[str] = []
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self.file_picker)

        self._thinking_widget: Optional[ft.Control] = None
        self._thinking_state: Optional[dict] = None
        self._thinking_timer: Optional[threading.Timer] = None
        self._thinking_alive = False

        self.add_hashtags_flag = False
        self._pending_ai_attachments: list[str] = []

        self.current_chat_id = "home"
        self._bg_effect = None
        self._screen_cache: dict = {}

        # ---------- Sidebar (только для десктопа) ----------
        self.sidebar: Optional[Sidebar] = None
        if not self.mobile:
            self.sidebar = Sidebar(
                page=self.page,
                items=self._make_sidebar_items(),
                bottom_items=[
                    SidebarItem(
                        icon=ft.Icons.MENU_ROUNDED,
                        label="Панель проектов",
                        on_click=self._toggle_projects_panel,
                        item_id="projects",
                    ),
                ],
            )

        # ---------- Кнопка гамбургер (мобильный) ----------
        self.hamburger_btn = ft.IconButton(
            icon=ft.Icons.MENU_ROUNDED, icon_size=22,
            icon_color=theme.TEXT_PRIMARY, tooltip="Меню",
            on_click=self._open_mobile_menu, visible=self.mobile,
        )

        self.title_text = ft.Text(
            self._current_title(), size=15,
            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY,
            text_align=ft.TextAlign.CENTER,
        )

        self.messages_list = ft.ListView(
            expand=True, spacing=2, auto_scroll=True,
            padding=ft.padding.symmetric(horizontal=theme.PADDING, vertical=8),
        )

        self.current_style: Optional[str] = state.current_style

        self.style_panel = ft.Container(
            content=create_style_buttons(self._handle_style_change, self.current_style),
            visible=False,
            padding=ft.padding.symmetric(horizontal=theme.PADDING),
        )

        self.style_toggle_btn = self._make_toolbar_button(
            icon=ft.Icons.PALETTE_ROUNDED, label="Стиль",
            on_click=self._toggle_style_panel,
        )

        self.hashtags_btn = self._make_toolbar_button(
            icon=ft.Icons.TAG_ROUNDED, label="Хештеги",
            on_click=self._toggle_hashtags_flag,
        )

        self.finish_button = self._make_toolbar_button(
            icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, label="Завершить",
            on_click=self._handle_finish_chat,
        )

        self.new_project_btn = self._make_toolbar_button(
            icon=ft.Icons.ADD_ROUNDED, label="Новый проект",
            on_click=lambda e: self._handle_new_project(),
        )

        self.attachments_preview = ft.Row(
            controls=[], spacing=8, wrap=True, visible=False,
        )

        self.input_field = ft.TextField(
            hint_text="Напиши свою идею...",
            multiline=True, min_lines=2, max_lines=6,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=theme.RADIUS, border_color=theme.SURFACE, expand=True,
        )

        self.attach_button = ft.IconButton(
            icon=ft.Icons.ATTACH_FILE_ROUNDED, icon_size=20,
            icon_color=theme.TEXT_SECONDARY, tooltip="Прикрепить файл",
            on_click=self._handle_attach_click,
        )

        self.send_button = ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD_ROUNDED, icon_size=20,
            icon_color=theme.TEXT_PRIMARY, bgcolor=theme.PRIMARY,
            on_click=self._handle_send,
        )

        self.show_input = True
        self.input_container = ft.Container(
            content=ft.Row(
                controls=[self.attach_button, self.input_field, self.send_button],
                spacing=4, vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            padding=ft.padding.all(theme.PADDING), visible=True,
        )

        self.format_zone = ft.Container(visible=False)

        self.resume_button = ft.ElevatedButton(
            text="Возобновить чат", bgcolor=theme.PRIMARY,
            color=theme.TEXT_PRIMARY, on_click=self._handle_resume_chat,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
            ),
        )

        self.bottom_zone = ft.Container()

        self.finished_label = ft.Container(
            content=ft.Text("Чат завершён", color=theme.TEXT_SECONDARY,
                            size=13, italic=True),
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            visible=False,
        )

        self.drawer = ProjectsDrawer(
            page=self.page,
            on_select_project=self._handle_select_project,
            on_new_project=self._handle_new_project,
            on_current_deleted=self._handle_current_project_deleted,
        )

        self.page.on_keyboard_event = self._on_keyboard

        self.main_area = ft.Container(
            expand=True,
            animate_opacity=ft.Animation(180, ft.AnimationCurve.EASE_IN_OUT),
        )

        self._render_messages()
        self._refresh_bottom_zone()

    # ---------- Сайдбар ----------

    def _make_sidebar_items(self) -> list:
        return [
            SidebarItem(
                icon=ft.Icons.HOME_ROUNDED,
                label="Главная",
                on_click=lambda e: self._handle_nav("home"),
                item_id="home",
            ),
            SidebarItem(
                icon=ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                label="Чат с ИИ",
                on_click=lambda e: self._handle_nav("ai_chat"),
                item_id="ai_chat",
            ),
            SidebarItem(
                icon=ft.Icons.IMAGE_ROUNDED,
                label="Генерация картинки",
                on_click=lambda e: self._handle_nav("image"),
                item_id="image",
            ),
            SidebarItem(
                icon=ft.Icons.TAG_ROUNDED,
                label="Хештеги",
                on_click=lambda e: self._handle_nav("hashtags"),
                item_id="hashtags",
            ),
            SidebarItem(
                icon=ft.Icons.GRID_VIEW_ROUNDED,
                label="Шаблоны",
                on_click=lambda e: self._handle_nav("templates"),
                item_id="templates",
            ),
            SidebarItem(
                icon=ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
                label="Идеи для постов",
                on_click=lambda e: self._handle_nav("ideas"),
                item_id="ideas",
            ),
            SidebarItem(
                icon=ft.Icons.SEND_ROUNDED,
                label="Telegram",
                on_click=lambda e: self._handle_nav("telegram"),
                item_id="telegram",
            ),
            SidebarItem(
                icon=ft.Icons.SETTINGS_ROUNDED,
                label="Настройки",
                on_click=lambda e: self._handle_nav("settings"),
                item_id="settings",
            ),
        ]

    def _open_mobile_menu(self, e) -> None:
        items_def = [
            ("home", ft.Icons.HOME_ROUNDED, "Главная"),
            ("ai_chat", ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, "Чат с ИИ"),
            ("image", ft.Icons.IMAGE_ROUNDED, "Генерация картинки"),
            ("hashtags", ft.Icons.TAG_ROUNDED, "Хештеги"),
            ("templates", ft.Icons.GRID_VIEW_ROUNDED, "Шаблоны"),
            ("ideas", ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, "Идеи для постов"),
            ("telegram", ft.Icons.SEND_ROUNDED, "Telegram"),
            ("settings", ft.Icons.SETTINGS_ROUNDED, "Настройки"),
        ]

        def close_menu(ev=None):
            try:
                self.page.close(menu_drawer)
            except Exception:
                pass

        def make_item(chat_id, icon, label):
            def on_click(ev):
                close_menu()
                self._handle_nav(chat_id)

            active = chat_id == self.current_chat_id

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            icon, size=20,
                            color=ft.Colors.WHITE if active else theme.TEXT_PRIMARY,
                        ),
                        ft.Text(
                            label, size=14,
                            color=ft.Colors.WHITE if active else theme.TEXT_PRIMARY,
                            weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL,
                        ),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                border_radius=10,
                bgcolor=theme.PRIMARY if active else ft.Colors.TRANSPARENT,
                on_click=on_click,
                ink=True,
            )

        menu_drawer = ft.NavigationDrawer(
            position=ft.NavigationDrawerPosition.START,
            bgcolor=theme.SURFACE,
            controls=[
                ft.Container(
                    content=ft.Text(
                        "V-AGENT",
                        size=20, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY,
                    ),
                    padding=ft.padding.only(left=16, top=20, bottom=16),
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[make_item(*item) for item in items_def],
                        spacing=4,
                    ),
                    padding=ft.padding.symmetric(horizontal=8),
                ),
            ],
        )

        try:
            self.page.open(menu_drawer)
            self.page.update()
        except Exception as ex:
            print(f"[MOBILE MENU] error: {ex}")

    # ---------- Кнопка тулбара ----------

    def _make_toolbar_button(self, icon, label, on_click, active=False):
        if active:
            bg = ft.Colors.with_opacity(0.15, theme.PRIMARY)
            border_color = theme.PRIMARY
            text_color = theme.TEXT_PRIMARY
            icon_color = theme.PRIMARY
        else:
            bg = theme.SURFACE
            border_color = ft.Colors.with_opacity(0.15, theme.TEXT_SECONDARY)
            text_color = theme.TEXT_SECONDARY
            icon_color = theme.TEXT_SECONDARY

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=14, color=icon_color),
                    ft.Text(label, size=12, color=text_color),
                ],
                spacing=6, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border_radius=10, bgcolor=bg,
            border=ft.border.all(1, border_color),
            on_click=on_click, ink=True,
        )

    def _refresh_toolbar_buttons(self) -> None:
        self.style_toggle_btn = self._make_toolbar_button(
            icon=ft.Icons.PALETTE_ROUNDED, label="Стиль",
            on_click=self._toggle_style_panel,
            active=self.style_panel.visible,
        )
        self.hashtags_btn = self._make_toolbar_button(
            icon=ft.Icons.TAG_ROUNDED, label="Хештеги",
            on_click=self._toggle_hashtags_flag,
            active=self.add_hashtags_flag,
        )
        self.finish_button = self._make_toolbar_button(
            icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, label="Завершить",
            on_click=self._handle_finish_chat,
        )
        self.new_project_btn = self._make_toolbar_button(
            icon=ft.Icons.ADD_ROUNDED, label="Новый проект",
            on_click=lambda e: self._handle_new_project(),
        )

    # ---------- UI ----------

    def build(self) -> ft.Stack:
        self.main_area.content = self._build_home_content()

        if self.sidebar is not None:
            try:
                self.sidebar.set_active("home")
            except Exception:
                pass

        from services.user_profile import get_current
        profile = get_current()
        effect_key = (profile.bg_effect if profile else "snow") or "snow"
        count_scale = float(profile.bg_count_scale) if profile else 1.0
        size_scale = float(profile.bg_size_scale) if profile else 1.0

        try:
            ww = int(self.page.window.width or self.page.width or 1920)
            wh = int(self.page.window.height or self.page.height or 1080)
        except Exception:
            ww, wh = 1920, 1080

        self._bg_effect = create_effect(
            effect_key, self.page,
            width=ww, height=wh,
            count_scale=count_scale,
            size_scale=size_scale,
        )
        bg_layer = self._bg_effect.build()
        self._bg_effect.start()

        if self.sidebar is not None:
            main_row = ft.Row(
                controls=[
                    self.sidebar.build(),
                    self.main_area,
                ],
                spacing=0,
                expand=True,
            )
        else:
            main_row = ft.Row(
                controls=[self.main_area],
                spacing=0,
                expand=True,
            )

        main_layer = ft.Container(
            content=main_row,
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.55, theme.BG_DARK),
        )

        return ft.Stack(
            controls=[bg_layer, main_layer],
            expand=True,
        )

    def _build_home_content(self) -> ft.Container:
        if self.mobile:
            header = ft.Container(
                content=ft.Row(
                    controls=[
                        self.hamburger_btn,
                        ft.Container(content=self.title_text, expand=True),
                        ft.Container(width=40),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=8),
                height=52,
            )
        else:
            header = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(width=48),
                        ft.Container(content=self.title_text, expand=True),
                        ft.Container(width=48),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=8),
                height=52,
            )

        self._refresh_toolbar_buttons()

        top_buttons = ft.Container(
            content=ft.Row(
                controls=[
                    self.style_toggle_btn,
                    self.hashtags_btn,
                    self.new_project_btn,
                    self.finish_button,
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
                wrap=True,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
        )

        bottom_block = ft.Container(
            content=ft.Column(
                controls=[
                    top_buttons,
                    self.style_panel,
                    self.attachments_preview,
                    self.finished_label,
                    self.bottom_zone,
                ],
                spacing=0,
            ),
            bgcolor=ft.Colors.with_opacity(0.7, theme.BG_DARK),
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    header,
                    ft.Container(content=self.messages_list, expand=True),
                    bottom_block,
                ],
                spacing=0,
                expand=True,
            ),
            expand=True,
        )

    def _refresh_bottom_zone(self) -> None:
        project = state.current_project
        is_finished = project.is_finished if project else False

        if is_finished:
            self.bottom_zone.content = ft.Container(
                content=self.resume_button,
                padding=ft.padding.all(theme.PADDING),
                alignment=ft.alignment.center,
            )
            self.finished_label.visible = True
        else:
            self.input_container.visible = self.show_input
            if self.show_input:
                self.bottom_zone.content = self.input_container
            else:
                self.bottom_zone.content = self.format_zone
            self.finished_label.visible = False

        try:
            self.page.update()
        except Exception:
            pass

    def _on_keyboard(self, e: ft.KeyboardEvent) -> None:
        if e.key != "Enter":
            return
        if e.shift:
            return
        if self.current_chat_id != "home":
            return

        project = state.current_project
        if project and project.is_finished:
            return
        if self.show_input:
            self._handle_send(None)

    # ---------- Навигация ----------

    def _handle_nav(self, chat_id: str) -> None:
        print(f">>> [CHAT] nav to: {chat_id}")

        # Если уже на этой вкладке — ничего не делаем
        if chat_id == self.current_chat_id:
            return

        # Останавливаем/паузим старый экран
        prev = self._screen_cache.get(self.current_chat_id)
        if prev and hasattr(prev, "stop_effect"):
            try:
                prev.stop_effect()
            except Exception as ex:
                print(f"[NAV] stop_effect error: {ex}")

        for key, screen in self._screen_cache.items():
            if hasattr(screen, "_bg_effect") and screen._bg_effect is not None:
                try:
                    screen._bg_effect.pause()
                except Exception:
                    pass

        if self._bg_effect is not None:
            try:
                self._bg_effect.pause()
            except Exception:
                pass

        self.current_chat_id = chat_id

        if self.sidebar is not None:
            try:
                self.sidebar.set_active(chat_id)
            except Exception:
                pass

        self._refresh_main_area()

        if chat_id == "home" and self._bg_effect is not None:
            try:
                self._bg_effect.resume()
            except Exception:
                pass

    def _refresh_main_area(self) -> None:
        """Готовит контент под текущий chat_id и СРАЗУ применяет его.

        ВАЖНО: main_area.content меняем в главном потоке и вызываем
        page.update() один раз. Никаких threading.Timer — иначе UI
        не успевает перерисоваться и кажется, что вкладка не переключилась.
        """
        from screens.settings_screen import SettingsScreen

        print(f">>> [CHAT] _refresh_main_area: {self.current_chat_id}")

        def _get(key, factory):
            if key not in self._screen_cache:
                self._screen_cache[key] = factory()
            return self._screen_cache[key]

        content = None

        try:
            if self.current_chat_id == "home":
                content = self._build_home_content()

            elif self.current_chat_id == "ai_chat":
                from screens.ai_chat_screen import AiChatScreen
                screen = _get("ai_chat", lambda: AiChatScreen(self.page))
                content = screen.build()
                if getattr(screen, "_bg_effect", None) is not None:
                    try:
                        screen._bg_effect.resume()
                    except Exception:
                        pass

            elif self.current_chat_id == "image":
                from screens.image_screen import ImageScreen
                screen = _get(
                    "image",
                    lambda: ImageScreen(
                        self.page,
                        on_open_settings=lambda: self._handle_nav("settings"),
                    ),
                )
                content = screen.build()
                if getattr(screen, "_bg_effect", None) is not None:
                    try:
                        screen._bg_effect.resume()
                    except Exception:
                        pass

            elif self.current_chat_id == "telegram":
                from screens.telegram_screen import TelegramScreen
                screen = TelegramScreen(self.page)
                self._screen_cache["telegram"] = screen
                content = screen.build()
                if getattr(screen, "_bg_effect", None) is not None:
                    try:
                        screen._bg_effect.resume()
                    except Exception:
                        pass

            elif self.current_chat_id == "hashtags":
                from screens.hashtags_screen import HashtagsScreen
                screen = _get("hashtags", lambda: HashtagsScreen(self.page))
                content = screen.build()
                if getattr(screen, "_bg_effect", None) is not None:
                    try:
                        screen._bg_effect.resume()
                    except Exception:
                        pass

            elif self.current_chat_id == "templates":
                from screens.templates_screen import TemplatesScreen
                screen = _get("templates", lambda: TemplatesScreen(self.page))
                content = screen.build()
                if getattr(screen, "_bg_effect", None) is not None:
                    try:
                        screen._bg_effect.resume()
                    except Exception:
                        pass

            elif self.current_chat_id == "ideas":
                from screens.ideas_screen import IdeasScreen
                screen = _get("ideas", lambda: IdeasScreen(self.page))
                content = screen.build()
                if getattr(screen, "_bg_effect", None) is not None:
                    try:
                        screen._bg_effect.resume()
                    except Exception:
                        pass

            elif self.current_chat_id == "settings":
                settings = SettingsScreen(
                    page=self.page,
                    on_open_profile=self._open_profile,
                    on_logout=self._do_logout,
                )
                content = settings.build()

            else:
                content = self._build_home_content()

        except Exception as ex:
            import traceback
            traceback.print_exc()
            print(f">>> [CHAT] build screen error ({self.current_chat_id}): {ex}")
            content = self._build_home_content()

        # Применяем контент СРАЗУ, в главном потоке
        try:
            self.main_area.content = content
        except Exception as ex:
            print(f">>> [CHAT] set content error: {ex}")

        try:
            self.page.update()
        except Exception as ex:
            print(f">>> [CHAT] update error: {ex}")

    # ---------- Панель проектов ----------

    def _toggle_projects_panel(self, e=None) -> None:
        """Открывает/закрывает шторку проектов справа."""
        try:
            self.drawer.toggle()
        except Exception as ex:
            print(f"[CHAT] drawer toggle error: {ex}")

    # ---------- Профиль ----------

    def _open_profile(self) -> None:
        from screens.profile_screen import ProfileScreen
        profile_screen = ProfileScreen(
            page=self.page,
            on_edit_profile=self._open_profile_edit,
        )
        self.main_area.content = profile_screen.build()
        try:
            self.page.update()
        except Exception:
            pass

    def _open_profile_edit(self) -> None:
        from screens.onboarding_screen import OnboardingScreen
        from services.user_profile import UserProfile, set_current

        current = UserProfile.load()

        def _on_save(updated: UserProfile) -> None:
            set_current(updated)
            self._open_profile()

        onboarding = OnboardingScreen(
            page=self.page,
            on_finish=_on_save,
            edit_mode=True,
            initial_profile=current,
        )

        self.main_area.content = onboarding.build()
        try:
            self.page.update()
        except Exception:
            pass

    def _do_logout(self) -> None:
        """Полный выход из аккаунта: удаляем данные и перезапускаем онбординг."""
        state.current_project = None

        self._stop_thinking(remove_widget=True)
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None

        for screen in list(self._screen_cache.values()):
            if hasattr(screen, "stop_effect"):
                try:
                    screen.stop_effect()
                except Exception:
                    pass
        self._screen_cache.clear()

        try:
            content_dir = _paths.data_dir()
            if content_dir.exists():
                shutil.rmtree(content_dir, ignore_errors=True)
        except Exception as ex:
            print(f"Ошибка удаления данных: {ex}")

        try:
            from services.user_profile import set_current
            set_current(None)
        except Exception:
            pass

        from app import main as app_main
        self.page.controls.clear()
        app_main(self.page)

    # ---------- Хештеги ----------

    def _toggle_hashtags_flag(self, e: ft.ControlEvent) -> None:
        self.add_hashtags_flag = not self.add_hashtags_flag
        self._refresh_toolbar_buttons()
        self.main_area.content = self._build_home_content()
        try:
            self.page.update()
        except Exception:
            pass

    # ---------- Стиль ----------

    def _toggle_style_panel(self, e: ft.ControlEvent) -> None:
        self.style_panel.visible = not self.style_panel.visible
        self._refresh_toolbar_buttons()
        self.main_area.content = self._build_home_content()
        try:
            self.page.update()
        except Exception:
            pass

    def _handle_style_change(self, style_key: Optional[str]) -> None:
        if self.current_style == style_key:
            self.current_style = None
        else:
            self.current_style = style_key
        state.set_style(self.current_style)
        self.style_panel.content = create_style_buttons(
            self._handle_style_change, self.current_style
        )
        try:
            self.page.update()
        except Exception:
            pass

    # ---------- Завершение ----------

    def _handle_finish_chat(self, e: ft.ControlEvent) -> None:
        project = state.current_project
        if not project:
            return
        project.is_finished = True
        project.chosen_style = self.current_style
        storage.save_project(project)
        self._refresh_bottom_zone()

    def _handle_resume_chat(self, e: ft.ControlEvent) -> None:
        project = state.current_project
        if not project:
            return
        project.is_finished = False
        self.show_input = True
        storage.save_project(project)
        self._refresh_bottom_zone()

    # ---------- Файлы ----------

    def _handle_attach_click(self, e: ft.ControlEvent) -> None:
        self.file_picker.pick_files(
            allow_multiple=True,
            allowed_extensions=["png", "jpg", "jpeg", "webp", "gif", "txt", "md"],
        )

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        for f in e.files:
            src = Path(f.path)
            if not src.exists():
                continue
            dest = self.attachments_dir / src.name
            counter = 1
            while dest.exists():
                dest = self.attachments_dir / f"{src.stem}_{counter}{src.suffix}"
                counter += 1
            try:
                shutil.copy(src, dest)
                self.pending_attachments.append(str(dest))
            except Exception as ex:
                print(f"Ошибка копирования: {ex}")
        self._render_attachments_preview()

    def _render_attachments_preview(self) -> None:
        self.attachments_preview.controls.clear()
        if not self.pending_attachments:
            self.attachments_preview.visible = False
            try:
                self.page.update()
            except Exception:
                pass
            return
        for path in self.pending_attachments:
            p = Path(path)
            is_image = p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
            if is_image:
                thumb = ft.Container(
                    content=ft.Image(
                        src=str(p.resolve()),
                        width=56, height=56,
                        fit=ft.ImageFit.COVER, border_radius=8,
                    ),
                    width=64, height=64, border_radius=8,
                    bgcolor=theme.SURFACE, alignment=ft.alignment.center,
                    on_click=lambda e, pp=p: self._remove_attachment(pp),
                )
            else:
                thumb = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.DESCRIPTION_ROUNDED,
                                    color=theme.TEXT_SECONDARY, size=20),
                            ft.Text(p.name[:10], size=9,
                                    color=theme.TEXT_SECONDARY,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    width=64, height=64, border_radius=8,
                    bgcolor=theme.SURFACE, alignment=ft.alignment.center,
                    on_click=lambda e, pp=p: self._remove_attachment(pp),
                )
            self.attachments_preview.controls.append(thumb)
        self.attachments_preview.visible = True
        try:
            self.page.update()
        except Exception:
            pass

    def _remove_attachment(self, path: Path) -> None:
        s = str(path)
        if s in self.pending_attachments:
            self.pending_attachments.remove(s)
        self._render_attachments_preview()

    # ---------- Проект ----------

    def _ensure_project_loaded(self) -> None:
        if state.current_project is not None:
            return
        projects = storage.list_projects()
        if projects:
            state.load_project(projects[0].id)
        else:
            state.new_project()

    def _current_title(self) -> str:
        if state.current_project and state.current_project.messages:
            return state.current_project.title
        return "Новый проект"

    def _render_messages(self) -> None:
        from datetime import datetime, date

        # ОЧИЩАЕМ список ПЕРЕД отрисовкой — иначе новые пузыри
        # накладываются на старые при переключении проекта.
        try:
            self.messages_list.controls.clear()
        except Exception:
            pass

        def _fmt_date_header(d: date) -> str:
            today = date.today()
            delta = (today - d).days
            if delta == 0:
                return "Сегодня"
            if delta == 1:
                return "Вчера"
            months = [
                "января", "февраля", "марта", "апреля", "мая", "июня",
                "июля", "августа", "сентября", "октября", "ноября", "декабря",
            ]
            if d.year == today.year:
                return f"{d.day} {months[d.month - 1]}"
            return f"{d.day} {months[d.month - 1]} {d.year}"

        def _make_date_divider(text: str) -> ft.Container:
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Text(
                                text, size=11,
                                color=theme.TEXT_SECONDARY,
                                weight=ft.FontWeight.BOLD,
                            ),
                            padding=ft.padding.symmetric(horizontal=12, vertical=4),
                            bgcolor=ft.Colors.with_opacity(0.5, theme.SURFACE),
                            border_radius=10,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(vertical=8),
            )

        project = state.current_project

        if not project or not project.messages:
            try:
                self.page.update()
            except Exception:
                pass
            return

        last_date: Optional[date] = None

        for message in project.messages:
            try:
                dt = datetime.fromisoformat(message.timestamp)
                msg_date = dt.date()
            except Exception:
                msg_date = None

            if msg_date is not None and msg_date != last_date:
                self.messages_list.controls.append(
                    _make_date_divider(_fmt_date_header(msg_date))
                )
                last_date = msg_date

            self.messages_list.controls.append(
                create_message_bubble(
                    message,
                    on_edit=self._handle_edit_post,
                    on_change_format=self._handle_change_format,
                    on_next=self._handle_next,
                    on_cancel=self._handle_cancel,
                )
            )

        try:
            self.page.update()
        except Exception:
            pass

    # ---------- Отправка ----------

    def _handle_send(self, e) -> None:
        idea = (self.input_field.value or "").strip()

        if not idea and not self.pending_attachments:
            return

        self.add_hashtags_flag = False
        self._refresh_toolbar_buttons()

        if state.current_project and not state.current_project.messages:
            self.messages_list.controls.clear()

        attachments_copy = list(self.pending_attachments)

        user_message = Message(
            role="user",
            text=idea,
            style=self.current_style,
            attachments=attachments_copy,
        )
        state.append_message(user_message)
        self.messages_list.controls.append(create_message_bubble(user_message))

        self.input_field.value = ""
        try:
            self.input_field.update()
        except Exception:
            pass
        self.pending_attachments.clear()
        self._render_attachments_preview()

        self._show_thinking()

        self._pending_ai_attachments = attachments_copy

        def _worker():
            from services.user_profile import get_current
            variants = text_ai.generate_content(
                idea=idea,
                style=self.current_style or "simple",
                history=state.current_project.messages,
                profile=get_current(),
            )
            threading.Timer(0, lambda: self._finish_generation(variants)).start()

        threading.Thread(target=_worker, daemon=True).start()

        self.title_text.value = self._current_title()
        try:
            self.page.update()
        except Exception:
            pass

    def _show_thinking(self) -> None:
        self._stop_thinking(remove_widget=True)
        self._thinking_state = {
            "prefix": "Нейро придумывает контент",
            "dots": ".",
        }
        widget = create_thinking_bubble(self._thinking_state)
        self._thinking_widget = widget
        self.messages_list.controls.append(widget)
        self._thinking_alive = True
        try:
            self.page.update()
        except Exception:
            pass
        self._schedule_dots_tick()

    def _schedule_dots_tick(self) -> None:
        if not self._thinking_alive:
            return

        def _tick():
            if not self._thinking_alive or not self._thinking_state:
                return
            cur = self._thinking_state.get("dots", ".")
            if cur == ".":
                self._thinking_state["dots"] = ".."
            elif cur == "..":
                self._thinking_state["dots"] = "..."
            else:
                self._thinking_state["dots"] = "."
            widget = self._thinking_state.get("widget")
            if widget is not None:
                try:
                    widget.value = (
                        f"{self._thinking_state['prefix']}"
                        f"{self._thinking_state['dots']}"
                    )
                    widget.update()
                except Exception:
                    pass
            self._thinking_timer = threading.Timer(0.5, _tick)
            self._thinking_timer.daemon = True
            self._thinking_timer.start()

        self._thinking_timer = threading.Timer(0.5, _tick)
        self._thinking_timer.daemon = True
        self._thinking_timer.start()

    def _stop_thinking(self, remove_widget: bool = True) -> None:
        self._thinking_alive = False
        if self._thinking_timer:
            try:
                self._thinking_timer.cancel()
            except Exception:
                pass
            self._thinking_timer = None
        if remove_widget and self._thinking_widget is not None:
            try:
                if self._thinking_widget in self.messages_list.controls:
                    self.messages_list.controls.remove(self._thinking_widget)
            except Exception:
                pass
            self._thinking_widget = None
        self._thinking_state = None

    def _finish_generation(self, variants: list) -> None:
        self._stop_thinking(remove_widget=True)

        ai_attachments = getattr(self, "_pending_ai_attachments", []) or []
        self._pending_ai_attachments = []

        if self.add_hashtags_flag:
            try:
                idea = ""
                for m in state.current_project.messages:
                    if m.role == "user" and m.text.strip():
                        idea = m.text.strip()
                        break
                tags = text_ai.generate_hashtags(
                    idea, self.current_style or "simple"
                )
                if tags and variants:
                    variants = [v + "\n\n" + tags for v in variants]
            except Exception as ex:
                print(f"[HASHTAGS] error: {ex}")

        ai_message = Message(
            role="assistant",
            text=variants[0],
            variants=variants,
            attachments=ai_attachments,
        )
        state.append_message(ai_message)
        self.messages_list.controls.append(
            create_message_bubble(
                ai_message,
                on_edit=self._handle_edit_post,
                on_change_format=self._handle_change_format,
                on_next=self._handle_next,
                on_cancel=self._handle_cancel,
            )
        )

        self.show_input = False
        self._refresh_bottom_zone()

        self.title_text.value = self._current_title()
        try:
            self.page.update()
        except Exception:
            pass

        try:
            if self.messages_list.controls:
                self.messages_list.scroll_to(offset=-1, duration=200)
        except Exception:
            pass

    # ---------- Кнопки под ответом ИИ ----------

    def _handle_edit_post(self, message_id: str) -> None:
        self.show_input = True
        self._refresh_bottom_zone()

    def _handle_change_format(self, message_id: str) -> None:
        pass

    def _handle_next(self, message_id: str, kind: str) -> None:
        if kind == "edit":
            self.show_input = True
            self._refresh_bottom_zone()
        elif kind == "format":
            self.show_input = False
            self._refresh_bottom_zone()

    def _handle_cancel(self, message_id: str) -> None:
        self.show_input = False
        self._refresh_bottom_zone()

    # ---------- Проекты ----------

    def _handle_select_project(self, project_id: str) -> None:
        self._stop_thinking(remove_widget=True)
        state.load_project(project_id)
        self.pending_attachments.clear()
        self._pending_ai_attachments = []
        self._render_attachments_preview()
        self.current_style = state.current_project.chosen_style if state.current_project else None
        self.style_panel.content = create_style_buttons(
            self._handle_style_change, self.current_style
        )

        self.add_hashtags_flag = False

        project = state.current_project
        self.show_input = not (project and project.messages)
        self._render_messages()
        self.title_text.value = self._current_title()
        self._refresh_bottom_zone()

    def _handle_new_project(self) -> None:
        self._stop_thinking(remove_widget=True)
        state.new_project()
        self.pending_attachments.clear()
        self._pending_ai_attachments = []
        self._render_attachments_preview()
        self.current_style = None
        self.show_input = True

        self.add_hashtags_flag = False

        self.style_panel.content = create_style_buttons(
            self._handle_style_change, self.current_style
        )
        self._render_messages()
        self.title_text.value = self._current_title()
        self._refresh_bottom_zone()

    def _handle_current_project_deleted(self) -> None:
        self._stop_thinking(remove_widget=True)
        state.current_project = None
        projects = storage.list_projects()
        if projects:
            state.load_project(projects[0].id)
        else:
            state.new_project()

        self.add_hashtags_flag = False

        self.pending_attachments.clear()
        self._pending_ai_attachments = []
        self._render_attachments_preview()
        self.current_style = state.current_project.chosen_style if state.current_project else None
        self.show_input = True
        self.style_panel.content = create_style_buttons(
            self._handle_style_change, self.current_style
        )
        self._render_messages()
        self.title_text.value = self._current_title()
        self._refresh_bottom_zone()