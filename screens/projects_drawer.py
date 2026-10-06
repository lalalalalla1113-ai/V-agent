"""Шторка «Мои проекты» — встроенная в Flet, справа.

Дизайн в стиле логотипа V-AGENT: глубокий чёрный (#050505) + фиолетовые
акценты. Карточки проектов — тёмно-серые, аккуратно отделены от фона.

При удалении проекта — «пузырёк лопается» и строка плавно сжимается,
остальные проекты плавно съезжают на освободившееся место.

ВАЖНО: NavigationDrawer создаётся заново при каждом open(),
иначе Flet кэширует uid и шторка зависает.
"""

import threading
from typing import Callable, Optional

import flet as ft

from services import storage
from services.models import Project
from state import state
from ui import theme


class ProjectsDrawer:
    """Шторка справа через ft.NavigationDrawer."""

    def __init__(
        self,
        page: ft.Page,
        on_select_project: Callable[[str], None],
        on_new_project: Callable[[], None],
        on_current_deleted: Optional[Callable[[], None]] = None,
    ) -> None:
        self.page = page
        self.on_select_project = on_select_project
        self.on_new_project = on_new_project
        self.on_current_deleted = on_current_deleted

        self.is_open = False
        self._busy = False
        self._current_drawer: Optional[ft.NavigationDrawer] = None
        self._pending_timers: list[threading.Timer] = []

        # Флаг: клик по проекту уже обрабатывается — защита от двойного срабатывания
        self._selecting = False

        # Контейнер со списком — пересоздаётся каждый раз при open()
        self.list_column = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=8,
        )

    # ------------------------------------------------------------------
    # Публичные методы
    # ------------------------------------------------------------------

    def build(self) -> ft.Container:
        """Пустой контейнер-заглушка (шторка открывается через page.open)."""
        return ft.Container(width=0, height=0, visible=False)

    def toggle(self) -> None:
        """Открыть, если закрыто. Закрыть, если открыто."""
        if self._busy:
            return
        if self.is_open:
            self.close()
        else:
            self.open()

    def open(self) -> None:
        """Открывает шторку."""
        if self.is_open or self._busy:
            return
        self._busy = True
        try:
            self._selecting = False

            # 1. Готовим список
            self._refresh_list()

            # 2. Создаём НОВЫЙ NavigationDrawer (Flet кэширует uid!)
            self._current_drawer = self._make_drawer()

            # 3. Открываем через page.open и сразу update
            try:
                self.page.open(self._current_drawer)
            except Exception as ex:
                print(f"[DRAWER] page.open error: {ex}")

            try:
                self.page.update()
            except Exception as ex:
                print(f"[DRAWER] update error: {ex}")

            self.is_open = True

        finally:
            self._busy = False

    def close(self, silent: bool = False) -> None:
        """Закрывает шторку.

        silent=True — закрываем без логов (при выборе проекта,
        чтобы не мешать обработке клика).
        """
        if not self.is_open:
            return
        drawer = self._current_drawer
        self.is_open = False
        self._current_drawer = None
        try:
            if drawer is not None:
                self.page.close(drawer)
        except Exception as ex:
            if not silent:
                print(f"[DRAWER] close error: {ex}")
        try:
            self.page.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Сборка шторки
    # ------------------------------------------------------------------

    def _make_drawer(self) -> ft.NavigationDrawer:
        """Создаёт НОВЫЙ NavigationDrawer каждый раз."""

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                            size=20,
                            color=ft.Colors.WHITE,
                        ),
                        width=40,
                        height=40,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.18, theme.PRIMARY),
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "Мои чаты",
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY,
                                ),
                                ft.Text(
                                    "Все ваши проекты",
                                    size=11,
                                    color=theme.TEXT_MUTED,
                                ),
                            ],
                            spacing=0,
                            tight=True,
                        ),
                        margin=ft.margin.only(left=12),
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        icon_color=theme.TEXT_SECONDARY,
                        tooltip="Закрыть",
                        on_click=lambda e: self.close(),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=16, right=8, top=20, bottom=16),
        )

        new_btn = ft.Container(
            content=ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.ADD_ROUNDED,
                            size=18,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Text(
                            "Новый проект",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(vertical=14),
                border_radius=12,
                bgcolor=theme.PRIMARY,
                on_click=self._handle_new_project,
                ink=True,
                alignment=ft.alignment.center,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
        )

        divider = ft.Container(
            height=1,
            bgcolor=theme.DIVIDER,
            margin=ft.margin.symmetric(horizontal=16, vertical=12),
        )

        list_block = ft.Container(
            content=self.list_column,
            expand=True,
            padding=ft.padding.symmetric(horizontal=12),
        )

        return ft.NavigationDrawer(
            position=ft.NavigationDrawerPosition.END,
            bgcolor=theme.DRAWER_BG,
            on_dismiss=self._on_dismiss,
            controls=[
                header,
                new_btn,
                divider,
                list_block,
            ],
        )

    def _on_dismiss(self, e: ft.ControlEvent) -> None:
        self.is_open = False
        self._current_drawer = None

    def _handle_new_project(self, e: ft.ControlEvent) -> None:
        self.close()
        self.on_new_project()

    # ------------------------------------------------------------------
    # Список проектов
    # ------------------------------------------------------------------

    def _refresh_list(self) -> None:
        # Пересоздаём колонку
        self.list_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=8,
        )

        projects = storage.list_projects()

        if not projects:
            self.list_column.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(
                                ft.Icons.INBOX_OUTLINED,
                                size=40,
                                color=ft.Colors.with_opacity(
                                    0.3, theme.TEXT_SECONDARY
                                ),
                            ),
                            ft.Container(height=8),
                            ft.Text(
                                "Пока пусто",
                                color=theme.TEXT_PRIMARY,
                                size=14,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "Создай первый проект",
                                color=theme.TEXT_SECONDARY,
                                size=12,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                    ),
                    padding=ft.padding.symmetric(vertical=40, horizontal=16),
                    alignment=ft.alignment.center,
                )
            )
            return

        for project in projects:
            self.list_column.controls.append(
                self._build_project_item(project)
            )

    def _build_project_item(self, project: Project) -> ft.Container:
        date_label = project.updated_at.split("T")[0]

        # Выделяем активный проект
        is_active = (
            state.current_project is not None
            and state.current_project.id == project.id
        )

        # Кнопка удаления — создаём отдельно, чтобы можно было
        # передать в неё wrapper (создаётся ниже)
        wrapper_holder: dict = {}

        def _on_delete_click(e):
            w = wrapper_holder.get("wrapper")
            self._ask_delete(project, w)

        inner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.FOLDER_ROUNDED,
                            size=18,
                            color=ft.Colors.WHITE if is_active else theme.PRIMARY,
                        ),
                        width=36,
                        height=36,
                        border_radius=10,
                        bgcolor=(
                            theme.PRIMARY if is_active
                            else ft.Colors.with_opacity(0.15, theme.PRIMARY)
                        ),
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    project.title or "Новый проект",
                                    color=theme.TEXT_PRIMARY,
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    date_label,
                                    color=theme.TEXT_MUTED,
                                    size=11,
                                ),
                            ],
                            spacing=2,
                            tight=True,
                        ),
                        expand=True,
                        margin=ft.margin.only(left=12),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_color=theme.TEXT_MUTED,
                        icon_size=16,
                        on_click=_on_delete_click,
                        tooltip="Удалить",
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border_radius=12,
            bgcolor=(
                ft.Colors.with_opacity(0.18, theme.PRIMARY) if is_active
                else theme.DRAWER_ITEM_BG
            ),
            border=ft.border.all(
                1,
                theme.PRIMARY if is_active else theme.DRAWER_ITEM_BORDER,
            ),
            ink=True,
            on_click=lambda e, pid=project.id: self._handle_select(pid),
            animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
        )

        wrapper = ft.Container(
            content=inner,
            animate=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
            height=None,
        )

        wrapper_holder["wrapper"] = wrapper

        return wrapper

    # ------------------------------------------------------------------
    # Выбор проекта
    # ------------------------------------------------------------------

    def _handle_select(self, project_id: str) -> None:
        """Обработка клика по проекту.

        ВАЖНО: сначала переключаем проект (перерисовываем ленту),
        потом асинхронно закрываем шторку. Иначе page.close() перебьёт
        обновление и UI не поменяется.
        """
        if self._selecting:
            return
        self._selecting = True

        # 1. Переключаем проект — синхронно, чтобы state обновился
        try:
            self.on_select_project(project_id)
        except Exception as ex:
            print(f"[DRAWER] on_select_project error: {ex}")

        # 2. Закрываем шторку — асинхронно, после отрисовки
        def _close_later():
            try:
                self.close(silent=True)
            except Exception as ex:
                print(f"[DRAWER] close after select error: {ex}")

        t = threading.Timer(0.05, _close_later)
        t.daemon = True
        t.start()

    # ------------------------------------------------------------------
    # Удаление проекта (с анимацией)
    # ------------------------------------------------------------------

    def _ask_delete(self, project: Project, wrapper: Optional[ft.Container]) -> None:
        title = project.title or "Новый проект"

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
        )

        def do_delete(e):
            try:
                self.page.close(dialog)
            except Exception:
                pass
            self._animate_delete(project, wrapper)

        def do_cancel(e):
            try:
                self.page.close(dialog)
            except Exception:
                pass

        dialog.title = ft.Text("Удалить проект?", color=theme.TEXT_PRIMARY)
        dialog.content = ft.Text(
            f"«{title}»\nЭто действие нельзя отменить.",
            color=theme.TEXT_SECONDARY,
        )
        dialog.actions = [
            ft.TextButton(
                "Нет",
                on_click=do_cancel,
                style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
            ),
            ft.ElevatedButton(
                "Да",
                bgcolor=theme.DANGER,
                color=ft.Colors.WHITE,
                on_click=do_delete,
            ),
        ]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        try:
            self.page.open(dialog)
            self.page.update()
        except Exception as ex:
            print(f"[DRAWER] delete dialog error: {ex}")

    def _schedule(self, delay: float, fn) -> None:
        t = threading.Timer(delay, fn)
        t.daemon = True
        self._pending_timers.append(t)
        t.start()

    def _cancel_timers(self) -> None:
        for t in self._pending_timers:
            try:
                t.cancel()
            except Exception:
                pass
        self._pending_timers = []

    def _animate_delete(self, project: Project,
                        wrapper: Optional[ft.Container]) -> None:
        """Анимация удаления + обновление списка."""
        deleted_current = (
            state.current_project is not None
            and state.current_project.id == project.id
        )

        def stage_lopnut():
            try:
                if wrapper is not None and wrapper.content is not None:
                    wrapper.content.opacity = 0.0
                    wrapper.content.update()
            except Exception:
                pass

        def stage_squeeze():
            try:
                if wrapper is None:
                    return
                current_height = wrapper.height or 60
                wrapper.height = current_height
                wrapper.update()

                def _to_zero():
                    try:
                        wrapper.height = 0
                        wrapper.update()
                    except Exception:
                        pass

                self._schedule(0.05, _to_zero)
            except Exception:
                pass

        def stage_remove():
            try:
                storage.delete_project(project.id)
            except Exception as ex:
                print(f"[DRAWER] delete error: {ex}")

            # Обновляем список в открытой шторке
            try:
                if self.is_open:
                    self._refresh_list()
                    if self._current_drawer is not None and self._current_drawer.controls:
                        self._current_drawer.controls[-1].content = self.list_column
                self.page.update()
            except Exception as ex:
                print(f"[DRAWER] refresh after delete error: {ex}")

            if deleted_current and self.on_current_deleted is not None:
                self.on_current_deleted()

        if wrapper is not None:
            try:
                if wrapper.content is not None:
                    wrapper.content.opacity = 0.6
                    wrapper.content.update()
            except Exception:
                pass

            self._schedule(0.15, stage_lopnut)
            self._schedule(0.55, stage_squeeze)
            self._schedule(1.1, stage_remove)
        else:
            # Без анимации — сразу удаляем и обновляем список
            stage_remove()