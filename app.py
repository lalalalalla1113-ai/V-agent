"""Роутер приложения V-AGENT.

Планировщик Telegram запускается здесь и работает всё время,
пока приложение в памяти (даже если окно свёрнуто).

Логика первого входа:
  • Если пользователь только что прошёл онбординг — показываем
    экран Premium-подписки ОДИН РАЗ (флаг premium_shown_at_start).
  • При следующих запусках — сразу чат.

Окно при старте:
  • На Android — full_screen
  • На десктопе — maximized (или размер 1600×900)
"""

import asyncio
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
    """Определяет мобильное устройство."""
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
    """Корректный выход.

    1. Останавливает планировщик Telegram.
    2. Снимает prevent_close, чтобы окно могло закрыться.
    3. Разрушает окно Flet через window.destroy().
    4. Через 100 мс жёстко убивает процесс через os._exit(0).

    os._exit гарантирует, что процесс НЕ останется в диспетчере задач
    (в отличие от sys.exit, который может зависнуть на потоках Flet).
    """
    # 1. Планировщик
    try:
        s = tg_scheduler.get_global()
        if s is not None:
            s.stop()
    except Exception:
        pass

    # 2. Flet: разрешаем закрытие, разрушаем окно
    if page is not None:
        try:
            page.window.prevent_close = False
        except Exception:
            pass
        try:
            page.window.destroy()
        except Exception:
            pass
        # Некоторые версии Flet ещё понимают close()
        try:
            page.window.close()
        except Exception:
            pass

    # 3. Жёсткое убийство процесса через 0.1 сек
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

    # ==================================================================
    # РАЗМЕР ОКНА ПРИ СТАРТЕ
    # ==================================================================
    if mobile:
        try:
            page.window.full_screen = True
        except Exception as ex:
            print(f"[APP] fullscreen error: {ex}")
    else:
        try:
            page.window.maximized = True
            print("[APP] окно развёрнуто (maximized=True)")
        except Exception as ex:
            print(f"[APP] maximized error: {ex}")

        try:
            page.window.width = 1600
            page.window.height = 900
            page.window.min_width = 800
            page.window.min_height = 600
        except Exception as ex:
            print(f"[APP] window size error: {ex}")

    # ==================================================================
    # ОБРАБОТЧИК РАЗВОРОТА ОКНА
    # ==================================================================
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
            print("[APP] resize → rebuild home_screen")
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
        print("[APP] on_resize handler установлен")
    except Exception as ex:
        print(f"[APP] on_resize setup error: {ex}")

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
                    print("[APP] окно свёрнуто")
                except Exception as ex:
                    print(f"[APP] minimize error: {ex}")
                    try:
                        page.window.visible = False
                        page.update()
                    except Exception as ex2:
                        print(f"[APP] minimize fallback error: {ex2}")

            def do_exit(ev):
                # Закрываем диалог и выходим корректно
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

            # ============================================================
            # КНОПКИ: Отмена слева, Свернуть в центре, Выйти справа
            # ============================================================

            # ОТМЕНА — серая заливка, чёрный текст
            cancel_btn = ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CLOSE_ROUNDED, size=16,
                                color=ft.Colors.BLACK),
                        ft.Text("Отмена", size=13,
                                color=ft.Colors.BLACK,
                                weight=ft.FontWeight.BOLD),
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

            # СВЕРНУТЬ — синий фон, чёрный текст, иконка «–»
            minimize_btn = ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Text("–", size=18,
                                color=ft.Colors.BLACK,
                                weight=ft.FontWeight.BOLD),
                        ft.Text("Свернуть", size=13,
                                color=ft.Colors.BLACK,
                                weight=ft.FontWeight.BOLD),
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

            # ВЫЙТИ — красный фон, чёрный текст
            exit_btn = ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=16,
                                color=ft.Colors.BLACK),
                        ft.Text("Выйти", size=13,
                                color=ft.Colors.BLACK,
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

            # Итог: Отмена слева, Свернуть в центре, Выйти справа
            dialog.actions = [
                ft.Row(
                    controls=[
                        cancel_btn,
                        ft.Container(expand=True),
                        minimize_btn,
                        ft.Container(expand=True),
                        exit_btn,
                    ],
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
    # Экраны
    # ------------------------------------------------------------------

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

        # При ПЕРВОМ входе — показываем экран Premium-подписки ОДИН РАЗ
        try:
            first_time = not getattr(profile, "premium_shown_at_start", False)
            if first_time:
                async def _delayed_subscription():
                    await asyncio.sleep(0.8)
                    try:
                        screen._handle_nav("subscription")
                        profile.premium_shown_at_start = True
                        profile.save()
                        print("[APP] Premium-экран показан при первом входе")
                    except Exception as ex:
                        print(f"[APP] show subscription error: {ex}")

                try:
                    page.run_task(_delayed_subscription)
                except Exception as ex:
                    print(f"[APP] run_task error: {ex}")
                    t = threading.Timer(
                        0.8, lambda: screen._handle_nav("subscription")
                    )
                    t.daemon = True
                    t.start()
        except Exception as ex:
            print(f"[APP] first-launch subscription error: {ex}")

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
