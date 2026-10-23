"""Роутер приложения V-AGENT."""

import asyncio
import os
import threading

import flet as ft

from services.user_profile import UserProfile, set_current
from services import tg_scheduler
from screens.chat_screen import ChatScreen
from screens.onboarding_screen import OnboardingScreen
from screens.auth_screen import AuthScreen
from state import state
from ui import theme


def _is_mobile(page: ft.Page) -> bool:
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


def _hard_exit(page=None) -> None:
    try:
        s = tg_scheduler.get_global()
        if s is not None:
            s.stop()
    except Exception:
        pass

    if page is not None:
        try:
            page.window.prevent_close = False
        except Exception:
            pass
        try:
            page.window.close()
        except Exception:
            pass

    def _force():
        try:
            os._exit(0)
        except Exception:
            pass

    t = threading.Timer(0.1, _force)
    t.daemon = True
    t.start()


def main(page: ft.Page) -> None:
    page.title = "V-AGENT"

    # --- ОКНО ПРИ СТАРТЕ ---
    page.window.maximized = True
    page.window.min_width = 1024
    page.window.min_height = 768
    page.update()

    theme.apply("dark_purple")
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.bgcolor = ft.Colors.BLACK

    mobile = _is_mobile(page)

    try:
        page.window.icon = "logo_v_only.webp"
    except Exception:
        pass

    # ---------- Обработчик разворота окна ----------
    _resize_timer = {"t": None}

    def _do_rebuild():
        try:
            chat = getattr(page, "_vagent_chat_screen", None)
            if chat is None:
                return
            if chat.current_chat_id != "menu":
                return
            chat._screen_cache.pop("menu", None)
            chat._handle_nav("menu", force=True)
        except Exception as ex:
            print(f"[APP] resize rebuild error: {ex}")

    def _on_resize(e):
        try:
            if _resize_timer["t"] is not None:
                _resize_timer["t"].cancel()
        except Exception:
            pass
        t = threading.Timer(0.3, _do_rebuild)
        t.daemon = True
        t.start()
        _resize_timer["t"] = t

    try:
        page.on_resize = _on_resize
    except Exception:
        pass

    # ---------- Планировщик Telegram ----------
    try:
        scheduler = tg_scheduler.TgScheduler(page)
        scheduler.start()
        tg_scheduler.set_global(scheduler)
        print("[APP] Telegram scheduler started")
    except Exception as ex:
        print(f"[APP] scheduler start error: {ex}")

    # ---------- Умный крестик (десктоп) ----------
    if not mobile:
        def _show_exit_dialog():
            dialog = ft.AlertDialog(
                modal=True,
                bgcolor=theme.SURFACE,
                title=ft.Text("Закрыть V-AGENT?", color=theme.TEXT_PRIMARY),
            )

            def do_minimize(ev):
                try:
                    page.close(dialog)
                except Exception:
                    pass
                try:
                    page.window.minimized = True
                    page.update()
                except Exception:
                    pass

            def do_exit(ev):
                try:
                    page.close(dialog)
                except Exception:
                    pass
                _hard_exit(page)

            def do_cancel(ev):
                try:
                    page.close(dialog)
                except Exception:
                    pass

            dialog.content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Если свернуть — V-AGENT продолжит работать "
                            "в фоне. Посты в Telegram будут уходить "
                            "по расписанию, пока компьютер включён.",
                            size=13, color=theme.TEXT_PRIMARY,
                        ),
                        ft.Container(height=10),
                        ft.Text(
                            "Полностью закрыть — планировщик остановится, "
                            "и посты перестанут отправляться.",
                            size=12, color=theme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=0, tight=True,
                ),
                width=440,
            )

            cancel_btn = ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CLOSE_ROUNDED, size=16, color=ft.Colors.BLACK),
                        ft.Text("Отмена", size=13, color=ft.Colors.BLACK, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8, tight=True,
                ),
                bgcolor="#9E9E9E",
                on_click=do_cancel,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                ),
            )

            minimize_btn = ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Text("–", size=18, color=ft.Colors.BLACK, weight=ft.FontWeight.BOLD),
                        ft.Text("Свернуть", size=13, color=ft.Colors.BLACK, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8, tight=True,
                ),
                bgcolor=theme.PRIMARY,
                on_click=do_minimize,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                ),
            )

            exit_btn = ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=16, color=ft.Colors.BLACK),
                        ft.Text("Выйти", size=13, color=ft.Colors.BLACK, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8, tight=True,
                ),
                bgcolor=theme.DANGER,
                on_click=do_exit,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                ),
            )

            dialog.actions = [
                ft.Row(
                    controls=[cancel_btn, ft.Container(expand=True), minimize_btn, ft.Container(expand=True), exit_btn],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ]
            dialog.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN

            page.open(dialog)
            try:
                page.update()
            except Exception:
                pass

        def _on_window_event(e):
            try:
                data = getattr(e, "data", None) or getattr(e, "type", None)
                if data == "close":
                    _show_exit_dialog()
            except Exception as ex:
                print(f"[APP] window event error: {ex}")

        try:
            page.window.prevent_close = True
            page.window.on_event = _on_window_event
        except Exception as ex:
            print(f"[APP] prevent_close error: {ex}")

    # ------------------------------------------------------------------
    # ЭКРАНЫ
    # ------------------------------------------------------------------

    def show_auth():
        page.controls.clear()

        def on_login_success():
            existing = UserProfile.load()
            if existing is None:
                existing = UserProfile()

            # СТАВИМ ФЛАГ, ЧТО МЫ ВОШЛИ
            existing.is_logged_in = True
            existing.save()

            show_main(existing)

        def go_register():
            show_onboarding()

        auth = AuthScreen(
            page=page,
            on_success=on_login_success,
            on_register=go_register
        )
        page.add(auth.build())
        page.update()

    def show_main(profile: UserProfile) -> None:
        page.window.maximized = True
        page.update()

        set_current(profile)
        page.controls.clear()
        screen = ChatScreen(page)
        try:
            setattr(page, "_vagent_chat_screen", screen)
        except Exception:
            pass
        page.add(screen.build())
        page.update()

    def show_onboarding() -> None:
        page.controls.clear()

        def _on_finish(profile: UserProfile) -> None:
            # После регистрации тоже ставим флаг
            profile.is_logged_in = True
            profile.save()
            show_main(profile)

        onboarding = OnboardingScreen(
            page=page,
            on_finish=_on_finish,
            on_go_login=show_auth,
            edit_mode=False,
        )
        page.add(onboarding.build())
        page.update()

    # --- ЛОГИКА ЗАПУСКА ---
    state.current_project = None
    state.current_style = None

    existing = UserProfile.load()

    # ПРОВЕРКА ФЛАГА ПРИ СТАРТЕ
    if existing and getattr(existing, "is_logged_in", False):
        print("[APP] Пользователь уже авторизован, заходим сразу.")
        show_main(existing)
    else:
        print("[APP] Требуется авторизация.")
        show_auth()
