"""Шторка «Мои чаты» — встроенная в Flet, справа.

Проекты группируются по вкладкам:
  • 💬 Чат с ИИ
  • 🖼️ Генерация картинок
  • #️⃣ Хештеги
  • 📋 Шаблоны
  • 💡 Идеи
  • 🎨 Автосоздание
  • 📤 Telegram
  • 📁 Другое

По умолчанию все группы СВЁРНУТЫ.
Клик по группе — раскрыть/свернуть список её проектов.
"""

import threading
from typing import Callable, Optional

import flet as ft

from services import storage
from services.models import Project
from state import state
from ui import theme


TAB_GROUPS = [
    {
        "id": "chat",
        "title": "Чат с ИИ",
        "icon": ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
        "color": "#9C27B0",
    },
    {
        "id": "image",
        "title": "Генерация картинок",
        "icon": ft.Icons.IMAGE_ROUNDED,
        "color": "#2196F3",
    },
    {
        "id": "hashtags",
        "title": "Хештеги",
        "icon": ft.Icons.TAG_ROUNDED,
        "color": "#00BCD4",
    },
    {
        "id": "templates",
        "title": "Шаблоны постов",
        "icon": ft.Icons.GRID_VIEW_ROUNDED,
        "color": "#4CAF50",
    },
    {
        "id": "ideas",
        "title": "Идеи для постов",
        "icon": ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
        "color": "#FFC107",
    },
    {
        "id": "content",
        "title": "Автосоздание",
        "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
        "color": "#FF9800",
    },
    {
        "id": "telegram",
        "title": "Telegram",
        "icon": ft.Icons.SEND_ROUNDED,
        "color": "#229ED9",
    },
    {
        "id": "other",
        "title": "Другое",
        "icon": ft.Icons.FOLDER_ROUNDED,
        "color": "#607D8B",
    },
]


class ProjectsDrawer:
    def __init__(
        self,
        page: ft.Page,
        on_select_project: Callable[[str], None],
        on_new_project: Callable[[], None],
        on_current_deleted: Optional[Callable[[], None]] = None,
        on_project_renamed: Optional[Callable[[], None]] = None,
    ) -> None:
        self.page = page
        self.on_select_project = on_select_project
        self.on_new_project = on_new_project
        self.on_current_deleted = on_current_deleted
        self.on_project_renamed = on_project_renamed

        self.is_open = False
        self._busy = False
        self._current_drawer: Optional[ft.NavigationDrawer] = None
        self._pending_timers: list[threading.Timer] = []
        self._selecting = False

        # По умолчанию все группы СВЁРНУТЫ
        self._expanded: dict = {g["id"]: False for g in TAB_GROUPS}

        self.list_column = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=8,
        )

    # ---------- Публичные ----------

    def build(self) -> ft.Container:
        return ft.Container(width=0, height=0, visible=False)

    def toggle(self) -> None:
        if self._busy:
            return
        if self.is_open:
            self.close()
        else:
            self.open()

    def open(self) -> None:
        if self.is_open or self._busy:
            return
        self._busy = True
        try:
            self._selecting = False
            self._refresh_list()
            self._current_drawer = self._make_drawer()
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

    # ---------- Сборка шторки ----------

    def _make_drawer(self) -> ft.NavigationDrawer:
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                            size=20, color=ft.Colors.WHITE,
                        ),
                        width=40, height=40, border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.18, theme.PRIMARY),
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Мои проекты", size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text("Нажми на раздел, чтобы раскрыть",
                                        size=11,
                                        color=theme.TEXT_MUTED),
                            ],
                            spacing=0, tight=True,
                        ),
                        margin=ft.margin.only(left=12),
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED, icon_size=18,
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

        divider = ft.Container(
            height=1, bgcolor=theme.DIVIDER,
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
            controls=[header, divider, list_block],
        )

    def _on_dismiss(self, e: ft.ControlEvent) -> None:
        self.is_open = False
        self._current_drawer = None

    # ---------- Список ----------

    def _refresh_list(self) -> None:
        self.list_column = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=8,
        )

        try:
            all_projects = storage.list_projects()
        except Exception:
            all_projects = []

        grouped: dict = {g["id"]: [] for g in TAB_GROUPS}
        for p in all_projects:
            tab_id = getattr(p, "tab_id", None) or "other"
            if tab_id not in grouped:
                tab_id = "other"
            grouped[tab_id].append(p)

        total = sum(len(v) for v in grouped.values())

        if total == 0:
            self.list_column.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.INBOX_OUTLINED, size=40,
                                    color=ft.Colors.with_opacity(0.3,
                                                                 theme.TEXT_SECONDARY)),
                            ft.Container(height=8),
                            ft.Text("Пока пусто", color=theme.TEXT_PRIMARY,
                                    size=14, weight=ft.FontWeight.BOLD),
                            ft.Text("Напиши сообщение в любой вкладке",
                                    color=theme.TEXT_SECONDARY, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                    ),
                    padding=ft.padding.symmetric(vertical=40, horizontal=16),
                    alignment=ft.alignment.center,
                )
            )
            return

        for group in TAB_GROUPS:
            projects = grouped.get(group["id"], [])
            if not projects:
                continue
            self.list_column.controls.append(
                self._make_group_header(group, len(projects))
            )
            if self._expanded.get(group["id"], False):
                for p in projects:
                    self.list_column.controls.append(
                        self._build_project_item(p, group)
                    )

    def _make_group_header(self, group: dict, count: int) -> ft.Container:
        color = group["color"]
        is_expanded = self._expanded.get(group["id"], False)

        def _toggle(e, gid=group["id"]):
            self._expanded[gid] = not self._expanded.get(gid, False)
            self._refresh_list()
            if self._current_drawer is not None and self._current_drawer.controls:
                self._current_drawer.controls[-1].content = self.list_column
            try:
                self.page.update()
            except Exception:
                pass

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.EXPAND_MORE_ROUNDED if is_expanded
                        else ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        size=18, color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(
                        content=ft.Icon(group["icon"], size=16,
                                        color=ft.Colors.WHITE),
                        width=32, height=32, border_radius=10,
                        bgcolor=color,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Text(group["title"], size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                        margin=ft.margin.only(left=10),
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(str(count), size=11,
                                        color=theme.TEXT_SECONDARY,
                                        weight=ft.FontWeight.BOLD),
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        bgcolor=ft.Colors.with_opacity(0.15, color),
                        border_radius=10,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            margin=ft.margin.only(top=6, bottom=2),
            border_radius=8,
            on_click=_toggle,
            ink=True,
        )

    def _build_project_item(self, project: Project, group: dict) -> ft.Container:
        date_label = project.updated_at.split("T")[0]
        color = group["color"]

        is_active = (
            state.current_project is not None
            and state.current_project.id == project.id
        )

        wrapper_holder: dict = {}

        def _on_delete_click(e):
            w = wrapper_holder.get("wrapper")
            self._ask_delete(project, w)

        def _on_rename_click(e):
            self._open_rename_dialog(project)

        inner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.FOLDER_ROUNDED, size=18,
                            color=ft.Colors.WHITE if is_active else color,
                        ),
                        width=36, height=36, border_radius=10,
                        bgcolor=(color if is_active
                                 else ft.Colors.with_opacity(0.15, color)),
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    project.title or "Новый проект",
                                    color=theme.TEXT_PRIMARY,
                                    size=13, weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(date_label,
                                        color=theme.TEXT_MUTED, size=10),
                            ],
                            spacing=2, tight=True,
                        ),
                        expand=True,
                        margin=ft.margin.only(left=10),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_ROUNDED,
                        icon_color=theme.TEXT_SECONDARY,
                        icon_size=15,
                        on_click=_on_rename_click,
                        tooltip="Изменить",
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_color=theme.TEXT_MUTED,
                        icon_size=15,
                        on_click=_on_delete_click,
                        tooltip="Удалить",
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=10,
            bgcolor=(ft.Colors.with_opacity(0.15, color) if is_active
                     else theme.DRAWER_ITEM_BG),
            border=ft.border.all(
                1,
                color if is_active else theme.DRAWER_ITEM_BORDER,
            ),
            ink=True,
            on_click=lambda e, pid=project.id: self._handle_select(pid),
            animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
        )

        wrapper = ft.Container(
            content=inner,
            animate=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
            height=None,
            margin=ft.margin.only(left=20),
        )
        wrapper_holder["wrapper"] = wrapper
        return wrapper

    # ---------- Переименование ----------

    def _open_rename_dialog(self, project: Project) -> None:
        current_title = project.title or "Новый проект"

        field = ft.TextField(
            value=current_title,
            hint_text="Название проекта",
            filled=True,
            fill_color=theme.BG_DARK,
            color=theme.TEXT_PRIMARY,
            border_radius=10,
            border_color=theme.DRAWER_ITEM_BORDER,
            focused_border_color=theme.PRIMARY,
            text_size=14,
            autofocus=True,
        )

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            title=ft.Text("Изменить название", color=theme.TEXT_PRIMARY),
        )

        def _save(ev):
            new_title = (field.value or "").strip() or "Новый проект"
            try:
                p = storage.load_project(project.id) or project
                p.title = new_title
                storage.save_project(p)

                if (state.current_project is not None
                        and state.current_project.id == project.id):
                    state.current_project.title = new_title

                self._refresh_list()
                if self._current_drawer is not None and self._current_drawer.controls:
                    self._current_drawer.controls[-1].content = self.list_column

                try:
                    self.page.close(dialog)
                except Exception:
                    pass
                try:
                    self.page.update()
                except Exception:
                    pass

                if self.on_project_renamed is not None:
                    self.on_project_renamed()

                self.page.open(ft.SnackBar(
                    content=ft.Text(f"Переименовано в «{new_title}»"),
                    duration=1800,
                ))
            except Exception as ex:
                print(f"[DRAWER] rename error: {ex}")

        def _cancel(ev):
            try:
                self.page.close(dialog)
            except Exception:
                pass

        field.on_submit = _save

        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Введи новое название:",
                            size=12, color=theme.TEXT_SECONDARY),
                    ft.Container(height=10),
                    field,
                ],
                spacing=0, tight=True,
            ),
            width=380,
        )

        dialog.actions = [
            ft.TextButton("Отмена", on_click=_cancel,
                          style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
            ft.ElevatedButton("Сохранить", bgcolor=theme.PRIMARY,
                              color=ft.Colors.WHITE, on_click=_save),
        ]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        try:
            self.page.open(dialog)
            self.page.update()
        except Exception as ex:
            print(f"[DRAWER] rename dialog error: {ex}")

    # ---------- Выбор ----------

    def _handle_select(self, project_id: str) -> None:
        if self._selecting:
            return
        self._selecting = True
        try:
            self.on_select_project(project_id)
        except Exception as ex:
            print(f"[DRAWER] on_select_project error: {ex}")

        def _close_later():
            try:
                self.close(silent=True)
            except Exception:
                pass

        t = threading.Timer(0.05, _close_later)
        t.daemon = True
        t.start()

    # ---------- Удаление ----------

    def _ask_delete(self, project: Project,
                    wrapper: Optional[ft.Container]) -> None:
        title = project.title or "Новый проект"
        dialog = ft.AlertDialog(modal=True, bgcolor=theme.SURFACE)

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
            ft.TextButton("Нет", on_click=do_cancel,
                          style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
            ft.ElevatedButton("Да", bgcolor=theme.DANGER,
                              color=ft.Colors.WHITE, on_click=do_delete),
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

    def _animate_delete(self, project: Project,
                        wrapper: Optional[ft.Container]) -> None:
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
            stage_remove()