"""Роутер приложения V-AGENT."""

import os
import threading

import flet as ft

from services.user_profile import UserProfile, set_current
from services import tg_scheduler
from screens.chat_screen import ChatScreen
from screens.onboarding_screen import OnboardingScreen
from state import state
from ui import theme


def _is_mobile(page: ft.Page) -> bool:
    try:
        if page.platform in ("android", "ios"):
            return True
    except Exception:
        pass
    try:
        w = int(page.width or 0)
        return 0 < w < 700
    except Exception:
        return False


def _hard_exit() -> None:
    """Мгновенный выход без зависания.

    Не вызываем page.window.destroy() — он блокирует поток.
    Просто останавливаем планировщик и убиваем процесс.
    """
    try:
        s = tg_scheduler.get_global()
        if s is not None:
            s.stop()
    except Exception:
        pass

    # Даём 100 мс на закрытие диалога, потом убиваем
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

    try:
        _existing_profile = UserProfile.load()
        _theme_key = (
            getattr(_existing_profile, "ui_theme", "dark_purple")
            if _existing_profile else "dark_purple"
        )
    except Exception:
        _theme_key = "dark_purple"
    theme.apply(_theme_key)

    try:
        page.theme_mode = (
            ft.ThemeMode.DARK if theme.IS_DARK else ft.ThemeMode.LIGHT
        )
    except Exception:
        page.theme_mode = ft.ThemeMode.DARK

    page.padding = 0
    page.bgcolor = theme.BG_DARK

    mobile = _is_mobile(page)

    try:
        page.window.icon = "logo_v_only.webp"
    except Exception:
        pass

    if mobile:
        try:
            page.window.full_screen = True
        except Exception as ex:
            print(f"[APP] fullscreen error: {ex}")

    # ---------- Планировщик Telegram ----------
    try:
        scheduler = tg_scheduler.TgScheduler(page)
        scheduler.start()
        tg_scheduler.set_global(scheduler)
        print("[APP] Telegram scheduler started")
    except Exception as ex:
        print(f"[APP] scheduler start error: {ex}")

    # ---------- Умный крестик ----------
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
                    page.window.visible = False
                    page.update()
                except Exception as ex:
                    print(f"[APP] minimize error: {ex}")

            def do_exit(ev):
                # Мгновенный выход, БЕЗ page.window.destroy()
                _hard_exit()

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

            minimize_btn = ft.OutlinedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.MINIMIZE_ROUNDED, size=16,
                                color=theme.PRIMARY),
                        ft.Text("Свернуть", size=13,
                                color=theme.PRIMARY,
                                weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8, tight=True,
                ),
                on_click=do_minimize,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    side=ft.BorderSide(1, theme.PRIMARY),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                ),
            )

            exit_btn = ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=16,
                                color=ft.Colors.WHITE),
                        ft.Text("Выйти", size=13,
                                color=ft.Colors.WHITE,
                                weight=ft.FontWeight.BOLD),
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

            cancel_btn = ft.TextButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CLOSE_ROUNDED, size=14,
                                color=theme.TEXT_SECONDARY),
                        ft.Text("Отмена", size=13,
                                color=theme.TEXT_SECONDARY),
                    ],
                    spacing=6, tight=True,
                ),
                on_click=do_cancel,
            )

            dialog.actions = [cancel_btn, minimize_btn, exit_btn]
            dialog.actions_alignment = ft.MainAxisAlignment.END

            page.open(dialog)
            try:
                page.update()
            except Exception:
                pass

        def _on_window_event(e):
            try:
                if e.data == "close":
                    _show_exit_dialog()
            except Exception as ex:
                print(f"[APP] window event error: {ex}")

        try:
            page.window.prevent_close = True
            page.window.on_event = _on_window_event
        except Exception as ex:
            print(f"[APP] prevent_close error: {ex}")

    # ---------- Экраны ----------

    def show_main(profile: UserProfile) -> None:
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
            show_main(profile)

        onboarding = OnboardingScreen(
            page=page, on_finish=_on_finish, edit_mode=False,
        )
        page.add(onboarding.build())
        page.update()

    state.current_project = None
    state.current_style = None

    existing = UserProfile.load()
    if existing is not None:
        print(f"Профиль найден: {existing.name}, {existing.age}")
        show_main(existing)
    else:
        print("Профиля нет — показываем онбординг")
        show_onboarding()
