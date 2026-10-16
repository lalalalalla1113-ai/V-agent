"""Главный экран-чат.

  • «Чат с ИИ» — обычный чат.
  • Остальные — отдельные экраны.

Кнопки Premium и «Новый чат» — справа в шапке.
Enter — отправить, Shift+Enter — новая строка.
В пустом чате — анимированный текст.
"""

import shutil
import threading
from pathlib import Path
from typing import Optional

import flet as ft

from screens.projects_drawer import ProjectsDrawer
from services import storage
from services import paths as _paths
from services import text_provider
from services.models import Message
from state import state
from ui import theme
from ui.message_bubble import create_thinking_bubble
from ui.sidebar import Sidebar, SidebarItem
from ui.effects import create_effect


_TYPING_FULL_TEXT = "V-Agent - твой собеседник в реальном времени"
_TYPING_SPEED = 0.06


def _is_mobile(page: ft.Page) -> bool:
    import os
    if os.environ.get("FLET_APP_STORAGE_DATA"):
        return True
    try:
        plat = str(page.platform or "").lower()
        if "android" in plat or "ios" in plat:
            return True
    except Exception:
        pass
    try:
        w = int(page.width or 0)
        if 0 < w < 700:
            return True
    except Exception:
        pass
    try:
        w = int(page.window.width or 0)
        if 0 < w < 700:
            return True
    except Exception:
        pass
    return False


class ChatScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.mobile = _is_mobile(page)

        self.attachments_dir = _paths.data_dir() / "attachments"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

        self.pending_attachments: list[str] = []
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self.file_picker)

        self._thinking_widget: Optional[ft.Control] = None
        self._thinking_state: Optional[dict] = None
        self._thinking_timer: Optional[threading.Timer] = None
        self._thinking_alive = False

        self._typing_alive = False
        self._typing_text_widget = None
        self._typing_thread = None

        self.current_chat_id = "menu"
        self._bg_effect = None
        self._screen_cache: dict = {}

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

        self.hamburger_btn = ft.IconButton(
            icon=ft.Icons.MENU_ROUNDED, icon_size=22,
            icon_color=theme.TEXT_PRIMARY, tooltip="Меню",
            on_click=self._open_mobile_menu, visible=self.mobile,
        )

        self.title_text = ft.Text(
            "Чат с ИИ", size=15,
            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY,
            text_align=ft.TextAlign.CENTER,
        )

        self.messages_list = ft.ListView(
            expand=True, spacing=2, auto_scroll=True,
            padding=ft.padding.symmetric(horizontal=theme.PADDING, vertical=8),
        )

        self.input_field = ft.TextField(
            hint_text="Напиши сообщение...",
            multiline=True,
            min_lines=1,
            max_lines=6,
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=theme.RADIUS,
            border_color=theme.SURFACE,
            expand=True,
            shift_enter=True,
            on_submit=self._handle_send,
        )

        self.send_button = ft.Container(
            content=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED,
                            size=20, color=ft.Colors.WHITE),
            width=48, height=48,
            bgcolor=theme.PRIMARY,
            border_radius=12,
            alignment=ft.alignment.center,
            on_click=self._handle_send,
            ink=True,
            tooltip="Отправить (Enter)",
        )
        self.input_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[self.input_field, self.send_button],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "Enter — отправить · Shift+Enter — новая строка",
                            size=10,
                            color=theme.TEXT_MUTED,
                            text_align=ft.TextAlign.RIGHT,
                        ),
                        padding=ft.padding.only(right=8, top=2),
                    ),
                ],
                spacing=2,
                tight=True,
            ),
            padding=ft.padding.only(left=24, right=24, top=10, bottom=6),
            visible=True,
        )

        self.bottom_zone = ft.Container()

        self.drawer = ProjectsDrawer(
            page=self.page,
            on_select_project=self._handle_select_project,
            on_new_project=self._handle_new_project,
            on_current_deleted=self._handle_current_project_deleted,
            on_project_renamed=self._handle_project_renamed,
        )

        self.page.on_keyboard_event = self._on_keyboard

        self.main_area = ft.Container(
            expand=True,
            opacity=1.0,
            animate_opacity=ft.Animation(150, ft.AnimationCurve.EASE_IN_OUT),
        )

        self._ensure_project_for_tab("chat")
        self._render_messages()
        self._refresh_bottom_zone()

    # ---------- Проект ----------

    def _ensure_project_for_tab(self, tab_id: str) -> None:
        proj = state.current_project
        if proj is not None and getattr(proj, "tab_id", "chat") == tab_id:
            return
        try:
            projects = storage.list_projects()
        except Exception:
            projects = []
        matching = [p for p in projects
                    if getattr(p, "tab_id", "chat") == tab_id]
        if matching:
            state.current_project = matching[0]
        else:
            try:
                new_proj = storage.create_project(
                    first_message_text="",
                    tab_id=tab_id,
                )
                new_proj.title = "Новый чат"
                storage.save_project(new_proj)
                state.current_project = new_proj
            except Exception as ex:
                print(f"[CHAT] create project error: {ex}")
                state.current_project = None

    # ---------- Сайдбар ----------

    def _make_sidebar_items(self) -> list:
        return [
            SidebarItem(icon=ft.Icons.HOME_ROUNDED, label="Главная",
                        on_click=lambda e: self._handle_nav("menu"),
                        item_id="menu"),
            SidebarItem(icon=ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, label="Чат с ИИ",
                        on_click=lambda e: self._handle_nav("chat"),
                        item_id="chat"),
            SidebarItem(icon=ft.Icons.IMAGE_ROUNDED, label="Генерация картинок",
                        on_click=lambda e: self._handle_nav("image"),
                        item_id="image"),
            SidebarItem(icon=ft.Icons.TAG_ROUNDED, label="Хештеги",
                        on_click=lambda e: self._handle_nav("hashtags"),
                        item_id="hashtags"),
            SidebarItem(icon=ft.Icons.GRID_VIEW_ROUNDED, label="Шаблоны",
                        on_click=lambda e: self._handle_nav("templates"),
                        item_id="templates"),
            SidebarItem(icon=ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, label="Идеи",
                        on_click=lambda e: self._handle_nav("ideas"),
                        item_id="ideas"),
            SidebarItem(icon=ft.Icons.AUTO_AWESOME_ROUNDED, label="Автосоздание",
                        on_click=lambda e: self._handle_nav("content"),
                        item_id="content"),
            SidebarItem(icon=ft.Icons.SEND_ROUNDED, label="Telegram",
                        on_click=lambda e: self._handle_nav("telegram"),
                        item_id="telegram"),
            SidebarItem(icon=ft.Icons.SETTINGS_ROUNDED, label="Настройки",
                        on_click=lambda e: self._handle_nav("settings"),
                        item_id="settings"),
        ]

    def _open_mobile_menu(self, e) -> None:
        items_def = [
            ("menu", ft.Icons.HOME_ROUNDED, "Главная"),
            ("chat", ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, "Чат с ИИ"),
            ("image", ft.Icons.IMAGE_ROUNDED, "Генерация картинок"),
            ("hashtags", ft.Icons.TAG_ROUNDED, "Хештеги"),
            ("templates", ft.Icons.GRID_VIEW_ROUNDED, "Шаблоны"),
            ("ideas", ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, "Идеи"),
            ("content", ft.Icons.AUTO_AWESOME_ROUNDED, "Автосоздание"),
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
                        ft.Icon(icon, size=20,
                                color=ft.Colors.WHITE if active else theme.TEXT_PRIMARY),
                        ft.Text(label, size=14,
                                color=ft.Colors.WHITE if active else theme.TEXT_PRIMARY,
                                weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL),
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
                    content=ft.Text("V-AGENT", size=20,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY),
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

    # ---------- Кнопки шапки ----------

    def _make_premium_button(self) -> ft.Container:
        try:
            from services.premium_guard import is_premium
            premium = is_premium()
        except Exception:
            premium = False

        if premium:
            color = "#4CAF50"
            text = "Premium ✓"
            tooltip = "Premium активен"
        else:
            color = "#FFD700"
            text = "Premium"
            tooltip = "Купить Premium"

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                            size=14, color=color),
                    ft.Text(text, size=11, color=color,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=4, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            bgcolor=ft.Colors.with_opacity(0.15, color),
            border=ft.border.all(1, ft.Colors.with_opacity(0.5, color)),
            border_radius=8,
            on_click=lambda e: self._handle_nav("subscription"),
            ink=True,
            tooltip=tooltip,
        )

    def _make_new_chat_button(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=14,
                            color=ft.Colors.WHITE),
                    ft.Text("Новый чат", size=11,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=4, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
            bgcolor=theme.PRIMARY,
            on_click=lambda e: self._handle_new_project(),
            ink=True,
            tooltip="Создать новый чат",
        )

    # ---------- UI ----------

    def build(self) -> ft.Stack:
        try:
            from screens.home_screen import HomeScreen
            home = HomeScreen(
                page=self.page,
                on_open_mode=self._handle_nav,
            )
            self._screen_cache["menu"] = home
            self.main_area.content = home.build()
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print(f"[CHAT] home_screen error: {ex}")
            self.main_area.content = self._build_chat_content()

        if self.sidebar is not None:
            try:
                self.sidebar.set_active("menu")
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
                controls=[self.sidebar.build(), self.main_area],
                spacing=0, expand=True,
            )
        else:
            main_row = ft.Row(
                controls=[self.main_area],
                spacing=0, expand=True,
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

    def _build_chat_content(self) -> ft.Container:
        premium_btn = self._make_premium_button()
        new_chat_btn = self._make_new_chat_button()

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        icon_size=20,
                        icon_color=theme.TEXT_PRIMARY,
                        tooltip="На главную",
                        on_click=lambda e: self._handle_nav("menu"),
                    ),
                    ft.Container(
                        content=self.title_text,
                        expand=True,
                        alignment=ft.alignment.center,
                    ),
                    premium_btn,
                    ft.Container(width=8),
                    new_chat_btn,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=8),
            height=52,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    header,
                    ft.Container(content=self.messages_list, expand=True),
                    self.bottom_zone,
                ],
                spacing=0,
                expand=True,
            ),
            expand=True,
        )

    def _refresh_bottom_zone(self) -> None:
        self.bottom_zone.content = self.input_container
        try:
            self.page.update()
        except Exception:
            pass

    def _on_keyboard(self, e: ft.KeyboardEvent) -> None:
        if e.key != "Enter":
            return
        if e.shift:
            return
        if self.current_chat_id != "chat":
            return
        self._handle_send(None)

    # ---------- Навигация ----------

    def _handle_nav(self, chat_id: str, force: bool = False) -> None:
        if chat_id == "home":
            chat_id = "menu"
        if chat_id == "ai_chat":
            chat_id = "chat"

        if chat_id == self.current_chat_id and not force:
            return

        self.current_chat_id = chat_id
        if self.sidebar is not None:
            try:
                self.sidebar.set_active(chat_id)
            except Exception:
                pass

        blocked_features = ["content", "telegram"]
        if chat_id in blocked_features:
            try:
                from services.premium_guard import is_premium, build_locked_screen
                if not is_premium():
                    locked = build_locked_screen(
                        page=self.page,
                        feature_key=chat_id,
                        on_buy_click=lambda e: self._handle_nav("subscription"),
                        on_close_click=lambda e: self._handle_nav("menu"),
                    )
                    self._swap_content_animated(locked)
                    return
            except Exception as ex:
                print(f">>> [CHAT] premium check error: {ex}")

        content = None
        try:
            content = self._build_screen_content(chat_id)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print(f">>> [CHAT] build error ({chat_id}): {ex}")
            content = self._build_chat_content()
            self.current_chat_id = "chat"
            if self.sidebar is not None:
                try:
                    self.sidebar.set_active("chat")
                except Exception:
                    pass

        if content is None:
            return

        self._swap_content_animated(content)

    def _swap_content_animated(self, new_content) -> None:
        import asyncio

        async def _do_swap():
            try:
                self.main_area.opacity = 0.0
                self.main_area.animate_opacity = ft.Animation(
                    150, ft.AnimationCurve.EASE_IN_OUT,
                )
                self.page.update()
            except Exception as ex:
                print(f">>> [CHAT] fade-out error: {ex}")

            await asyncio.sleep(0.15)

            try:
                self.main_area.content = new_content
                self.main_area.opacity = 1.0
                self.page.update()
            except Exception as ex:
                print(f">>> [CHAT] swap error: {ex}")

        try:
            self.page.run_task(_do_swap)
        except Exception as ex:
            print(f">>> [CHAT] run_task error: {ex}, fallback sync")
            try:
                self.main_area.content = new_content
                self.main_area.opacity = 1.0
                self.page.update()
            except Exception:
                pass

    def _build_screen_content(self, chat_id: str):
        if chat_id == "chat":
            self.title_text.value = "Чат с ИИ"
            self._ensure_project_for_tab("chat")
            self._render_messages()
            return self._build_chat_content()

        if chat_id == "menu":
            try:
                from screens.home_screen import HomeScreen
                if "menu" not in self._screen_cache:
                    self._screen_cache["menu"] = HomeScreen(
                        page=self.page,
                        on_open_mode=self._handle_nav,
                    )
                screen = self._screen_cache["menu"]
                try:
                    screen._bg_effect = None
                except Exception:
                    pass
                return screen.build()
            except Exception as ex:
                print(f"[CHAT] home build error: {ex}")
                return self._build_chat_content()

        if chat_id == "image":
            from screens.image_screen import ImageScreen
            if "image" not in self._screen_cache:
                self._screen_cache["image"] = ImageScreen(
                    self.page,
                    on_open_settings=lambda: self._handle_nav("settings"),
                )
            return self._screen_cache["image"].build()

        if chat_id == "hashtags":
            from screens.hashtags_screen import HashtagsScreen
            if "hashtags" not in self._screen_cache:
                self._screen_cache["hashtags"] = HashtagsScreen(self.page)
            return self._screen_cache["hashtags"].build()

        if chat_id == "templates":
            from screens.templates_screen import TemplatesScreen
            if "templates" not in self._screen_cache:
                self._screen_cache["templates"] = TemplatesScreen(self.page)
            return self._screen_cache["templates"].build()

        if chat_id == "ideas":
            from screens.ideas_screen import IdeasScreen
            if "ideas" not in self._screen_cache:
                self._screen_cache["ideas"] = IdeasScreen(self.page)
            return self._screen_cache["ideas"].build()

        if chat_id == "content":
            from screens.content_screen import ContentScreen
            if "content" not in self._screen_cache:
                self._screen_cache["content"] = ContentScreen(self.page)
            return self._screen_cache["content"].build()

        if chat_id == "telegram":
            from screens.telegram_screen import TelegramScreen
            old = self._screen_cache.get("telegram")
            if old is not None:
                try:
                    if hasattr(old, "_bg_effect") and old._bg_effect is not None:
                        old._bg_effect.stop()
                        old._bg_effect = None
                except Exception:
                    pass
            self._screen_cache["telegram"] = TelegramScreen(self.page)
            return self._screen_cache["telegram"].build()

        if chat_id == "activation":
            from screens.activation_screen import ActivationScreen
            if "activation" not in self._screen_cache:
                self._screen_cache["activation"] = ActivationScreen(self.page)
            return self._screen_cache["activation"].build()

        if chat_id == "subscription":
            from screens.subscription_screen import SubscriptionScreen
            if "subscription" not in self._screen_cache:
                self._screen_cache["subscription"] = SubscriptionScreen(self.page)
            return self._screen_cache["subscription"].build()

        if chat_id == "settings":
            from screens.settings_screen import SettingsScreen
            if "settings" not in self._screen_cache:
                self._screen_cache["settings"] = SettingsScreen(
                    page=self.page,
                    on_open_profile=self._open_profile,
                    on_logout=self._do_logout,
                )
            return self._screen_cache["settings"].build()

        return self._build_chat_content()

    # ---------- Панель проектов ----------

    def _toggle_projects_panel(self, e=None) -> None:
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

    def stop_effect(self) -> None:
        try:
            self._stop_thinking(remove_widget=True)
        except Exception:
            pass
        try:
            self._stop_typing_animation()
        except Exception:
            pass
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None
        for s in list(self._screen_cache.values()):
            if hasattr(s, "stop_effect"):
                try:
                    s.stop_effect()
                except Exception:
                    pass

    def _do_logout(self) -> None:
        state.current_project = None
        self.stop_effect()

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

        try:
            self.page.on_keyboard_event = None
        except Exception:
            pass
        try:
            setattr(self.page, "_vagent_chat_screen", None)
        except Exception:
            pass

        from app import main as app_main
        self.page.controls.clear()
        app_main(self.page)

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

    # ---------- Анимация печати ----------

    def _start_typing_animation(self) -> None:
        self._stop_typing_animation()

        text_widget = ft.Text(
            "",
            size=34,
            weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY,
            text_align=ft.TextAlign.CENTER,
        )
        self._typing_text_widget = text_widget
        self._typing_alive = True

        self.messages_list.controls.clear()
        self.messages_list.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        text_widget,
                        ft.Container(
                            content=ft.Text(
                                "Напиши сообщение ниже, чтобы начать",
                                size=13,
                                color=theme.TEXT_MUTED,
                                text_align=ft.TextAlign.CENTER,
                                italic=True,
                            ),
                            margin=ft.margin.only(top=20),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                alignment=ft.alignment.center,
                expand=True,
                padding=ft.padding.symmetric(vertical=180),
            )
        )
        try:
            self.page.update()
        except Exception:
            pass

        def _loop():
            import time
            for i in range(len(_TYPING_FULL_TEXT) + 1):
                if not self._typing_alive:
                    return
                try:
                    text_widget.value = _TYPING_FULL_TEXT[:i]
                    text_widget.update()
                except Exception:
                    pass
                time.sleep(_TYPING_SPEED)

        t = threading.Thread(target=_loop, daemon=True)
        self._typing_thread = t
        t.start()

    def _stop_typing_animation(self) -> None:
        self._typing_alive = False
        self._typing_thread = None
        self._typing_text_widget = None

    # ---------- Лента ----------

    def _render_messages(self) -> None:
        from datetime import datetime, date

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
                            content=ft.Text(text, size=11,
                                            color=theme.TEXT_SECONDARY,
                                            weight=ft.FontWeight.BOLD),
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
            self._start_typing_animation()
            try:
                self.page.update()
            except Exception:
                pass
            return

        self._stop_typing_animation()

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
                self._make_simple_bubble(message)
            )
        try:
            self.page.update()
        except Exception:
            pass

    def _make_simple_bubble(self, message: Message) -> ft.Container:
        from datetime import datetime
        from ui.message_bubble import get_dynamic_width
        width = get_dynamic_width()

        is_user = message.role == "user"
        text = (message.text or "").strip() or " "

        try:
            dt = datetime.fromisoformat(message.timestamp)
            time_str = f"{dt.hour}:{dt.minute:02d}"
        except Exception:
            time_str = ""

        if is_user:
            bubble = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(text, size=14, color=ft.Colors.WHITE,
                                selectable=True, no_wrap=False),
                        ft.Container(
                            content=ft.Text(
                                time_str, size=10,
                                color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
                            ) if time_str else ft.Container(),
                            alignment=ft.alignment.bottom_right,
                            padding=ft.padding.only(top=4),
                        ),
                    ],
                    spacing=0, tight=True,
                ),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                bgcolor=theme.USER_BUBBLE,
                border_radius=theme.RADIUS,
                width=width,
            )
            return ft.Container(
                content=ft.Row(
                    controls=[bubble],
                    alignment=ft.MainAxisAlignment.END,
                ),
                margin=ft.margin.only(left=20, top=4, bottom=4),
            )

        bubble = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(text, size=14, color=theme.TEXT_PRIMARY,
                            selectable=True, no_wrap=False),
                    ft.Container(
                        content=ft.Text(
                            time_str, size=10, color=theme.TEXT_SECONDARY,
                        ) if time_str else ft.Container(),
                        alignment=ft.alignment.bottom_right,
                        padding=ft.padding.only(top=6),
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.all(14),
            bgcolor=theme.AI_BUBBLE,
            border_radius=theme.RADIUS,
            width=width,
        )
        return ft.Container(
            content=ft.Row(
                controls=[bubble],
                alignment=ft.MainAxisAlignment.START,
            ),
            margin=ft.margin.only(right=20, top=4, bottom=4),
        )

    # ---------- Отправка ----------

    def _handle_send(self, e) -> None:
        idea = (self.input_field.value or "").strip()
        if not idea:
            return

        self._stop_typing_animation()

        proj = state.current_project
        if proj is None or getattr(proj, "tab_id", "chat") != "chat":
            try:
                project = storage.create_project(
                    first_message_text=idea,
                    tab_id="chat",
                )
                state.current_project = project
            except Exception as ex:
                print(f"[CHAT] create project error: {ex}")
                return

        if state.current_project and not state.current_project.messages:
            self.messages_list.controls.clear()

        user_message = Message(role="user", text=idea)
        state.append_message(user_message)
        self.messages_list.controls.append(self._make_simple_bubble(user_message))

        self.input_field.value = ""
        try:
            self.input_field.update()
        except Exception:
            pass

        self._show_thinking()

        def _worker():
            context_lines = []
            try:
                for h in state.current_project.messages[-10:]:
                    role = "User" if h.role == "user" else "Assistant"
                    context_lines.append(f"{role}: {h.text}")
            except Exception:
                pass
            context = "\n".join(context_lines)

            reply = text_provider.ask(
                context,
                system=(
                    "Ты — полезный ассистент. Отвечай кратко и по делу, "
                    "на русском языке. Помогаешь писать тексты, отвечать на "
                    "вопросы, объяснять сложное простыми словами. "
                    "Не используй Markdown-разметку."
                ),
                max_tokens=1500,
            )
            if not reply:
                reply = "❌ Не удалось получить ответ. Проверь ключ Cloudflare в Настройках."

            threading.Timer(0, lambda: self._finish_generation(reply)).start()

        threading.Thread(target=_worker, daemon=True).start()

        try:
            self.page.update()
        except Exception:
            pass

    def _show_thinking(self) -> None:
        self._stop_thinking(remove_widget=True)
        self._thinking_state = {
            "prefix": "Нейро думает",
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

    def _finish_generation(self, reply: str) -> None:
        self._stop_thinking(remove_widget=True)

        ai_message = Message(role="assistant", text=reply)
        state.append_message(ai_message)
        self.messages_list.controls.append(self._make_simple_bubble(ai_message))

        try:
            self.page.update()
        except Exception:
            pass
        try:
            if self.messages_list.controls:
                self.messages_list.scroll_to(offset=-1, duration=200)
        except Exception:
            pass

    # ---------- Проекты ----------

    def _handle_select_project(self, project_id: str) -> None:
        self._stop_thinking(remove_widget=True)
        self._stop_typing_animation()
        state.load_project(project_id)
        project = state.current_project
        self._render_messages()
        self._refresh_bottom_zone()

        if project is not None:
            tab_id = getattr(project, "tab_id", "chat") or "chat"
            if tab_id in ("chat", "image", "hashtags", "templates", "ideas",
                          "content", "telegram", "settings"):
                if tab_id != self.current_chat_id:
                    self.current_chat_id = tab_id
                    if self.sidebar is not None:
                        try:
                            self.sidebar.set_active(tab_id)
                        except Exception:
                            pass
                    if tab_id != "chat":
                        try:
                            self._handle_nav(tab_id, force=True)
                        except Exception:
                            pass

    def _handle_new_project(self) -> None:
        """Создаёт НОВЫЙ проект во вкладке «Чат с ИИ» и открывает его."""
        print("[CHAT] new project requested")
        try:
            self._stop_thinking(remove_widget=True)
        except Exception as ex:
            print(f"[CHAT] stop thinking error: {ex}")
        try:
            self._stop_typing_animation()
        except Exception as ex:
            print(f"[CHAT] stop typing error: {ex}")

        if self.current_chat_id != "chat":
            self.current_chat_id = "chat"
            if self.sidebar is not None:
                try:
                    self.sidebar.set_active("chat")
                except Exception:
                    pass

        try:
            new_proj = storage.create_project(
                first_message_text="",
                tab_id="chat",
            )
            new_proj.title = "Новый чат"
            storage.save_project(new_proj)
            state.current_project = new_proj
            print(f"[CHAT] created project {new_proj.id}")
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print(f"[CHAT] create error: {ex}")
            return

        try:
            self.messages_list.controls.clear()
        except Exception:
            pass

        try:
            self._render_messages()
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print(f"[CHAT] render error: {ex}")

        try:
            self._refresh_bottom_zone()
        except Exception as ex:
            print(f"[CHAT] refresh bottom error: {ex}")

        try:
            self.main_area.content = self._build_chat_content()
            self.main_area.opacity = 1.0
            self.page.update()
        except Exception as ex:
            print(f"[CHAT] swap to chat error: {ex}")

        print("[CHAT] new project OK")

    def _handle_current_project_deleted(self) -> None:
        self._stop_thinking(remove_widget=True)
        self._stop_typing_animation()
        state.current_project = None
        projects = storage.list_projects()
        if projects:
            state.load_project(projects[0].id)
        self._render_messages()
        self._refresh_bottom_zone()

    def _handle_project_renamed(self) -> None:
        try:
            self.page.update()
        except Exception:
            pass