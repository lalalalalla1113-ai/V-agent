"""Левая боковая панель с кнопками меню и логотипом V-AGENT.

Стеклянный дизайн (glassmorphism).
Подсветка активной вкладки работает для ВСЕХ кнопок.

ИСПРАВЛЕНО: убран баг, из-за которого при активной Premium-подписке
все пункты оставались серыми (accent ломал set_active).
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import flet as ft

from ui import theme


LOGO_V_FILENAME = "logo_v_only.webp"
LOGO_TEXT_FILENAME = "logo_text.webp"

LOGO_BOX_HEIGHT = 72
LOGO_V_SIZE = 44
LOGO_TEXT_WIDTH = 180

FADE_MS = 260
ITEM_ANIM_MS = 220


def _is_mobile() -> bool:
    return bool(os.environ.get("FLET_APP_STORAGE_DATA"))


class SidebarItem:
    def __init__(
        self,
        icon: str,
        label: str,
        on_click: Callable[[ft.ControlEvent], None],
        color: Optional[str] = None,
        accent: bool = False,
        item_id: Optional[str] = None,
    ) -> None:
        self.icon = icon
        self.label = label
        self.on_click = on_click
        self.color = color
        self.accent = accent
        self.item_id = item_id


class Sidebar:
    def __init__(
        self,
        page: ft.Page,
        items: list[SidebarItem],
        bottom_items: Optional[list[SidebarItem]] = None,
    ) -> None:
        self.page = page
        self.items = items
        self.bottom_items = bottom_items or []
        self.expanded = False
        self.active_id: Optional[str] = None
        self.mobile = _is_mobile()

        self._button_refs: dict = {}

        self.items_column = ft.Column(controls=[], spacing=4)
        self.bottom_column = ft.Column(controls=[], spacing=4)

        # Логотипы
        self.logo_v = ft.Image(
            src=LOGO_V_FILENAME,
            width=LOGO_V_SIZE, height=LOGO_V_SIZE,
            fit=ft.ImageFit.CONTAIN,
        )
        self.logo_v_wrap = ft.Container(
            content=self.logo_v,
            alignment=ft.alignment.center,
            opacity=1.0,
            animate_opacity=ft.Animation(FADE_MS, ft.AnimationCurve.EASE_IN_OUT),
        )

        self.logo_text = ft.Image(
            src=LOGO_TEXT_FILENAME,
            width=LOGO_TEXT_WIDTH, height=LOGO_BOX_HEIGHT,
            fit=ft.ImageFit.CONTAIN,
        )
        self.logo_text_wrap = ft.Container(
            content=self.logo_text,
            alignment=ft.alignment.center,
            opacity=0.0,
            animate_opacity=ft.Animation(FADE_MS, ft.AnimationCurve.EASE_IN_OUT),
        )

        self.logo_container = ft.Container(
            height=LOGO_BOX_HEIGHT + 20,
            alignment=ft.alignment.center,
            content=ft.Stack(
                controls=[self.logo_v_wrap, self.logo_text_wrap],
                alignment=ft.alignment.center,
            ),
        )

        # Стеклянная панель
        self.panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(height=12),
                    self.logo_container,
                    ft.Container(height=8),
                    self.items_column,
                    ft.Container(expand=True),
                    self.bottom_column,
                    ft.Container(height=12),
                ],
                spacing=0,
                expand=True,
            ),
            width=theme.SIDEBAR_COLLAPSED,
            bgcolor=ft.Colors.with_opacity(0.35, theme.SIDEBAR_BG),
            border=ft.border.only(
                right=ft.BorderSide(
                    1,
                    ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                ),
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=8),
            animate=ft.Animation(
                theme.SIDEBAR_ANIM_MS, ft.AnimationCurve.EASE_OUT,
            ),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=20,
                color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
                offset=ft.Offset(2, 0),
            ),
            on_hover=(None if self.mobile else self._on_hover),
            on_click=(self._on_panel_click if self.mobile else None),
        )

        self._build_items()

    # ------------------------------------------------------------------
    # Логотип
    # ------------------------------------------------------------------

    def _swap_logo(self, to_expanded: bool) -> None:
        if to_expanded:
            self.logo_v_wrap.opacity = 0.0
            self.logo_text_wrap.opacity = 1.0
        else:
            self.logo_v_wrap.opacity = 1.0
            self.logo_text_wrap.opacity = 0.0
        try:
            self.logo_v_wrap.update()
            self.logo_text_wrap.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Кнопки
    # ------------------------------------------------------------------

    def _build_items(self) -> None:
        self.items_column.controls.clear()
        self.bottom_column.controls.clear()
        self._button_refs.clear()

        for item in self.items:
            self.items_column.controls.append(self._make_button(item))

        for item in self.bottom_items:
            self.bottom_column.controls.append(self._make_button(item))

    def _get_button_colors(self, item: SidebarItem, is_active: bool):
        """Возвращает (bg, icon_color, label_color) для состояния."""
        if is_active:
            # Активный — фиолетовый/выбранный цвет темы
            return (
                theme.PRIMARY,
                ft.Colors.WHITE,
                ft.Colors.WHITE,
            )
        if item.accent:
            # Акцентный, но НЕ активный — просто иконка фиолетовая
            return (
                ft.Colors.TRANSPARENT,
                theme.PRIMARY,
                theme.TEXT_PRIMARY,
            )
        # Обычная кнопка
        icon_color = item.color if item.color else theme.TEXT_PRIMARY
        return (
            ft.Colors.TRANSPARENT,
            icon_color,
            theme.TEXT_PRIMARY,
        )

    def _make_button(self, item: SidebarItem) -> ft.Container:
        is_active = (item.item_id is not None and item.item_id == self.active_id)
        bg, icon_color, label_color = self._get_button_colors(item, is_active)

        icon_widget = ft.Icon(
            name=item.icon, size=22, color=icon_color,
            animate_opacity=ft.Animation(ITEM_ANIM_MS, ft.AnimationCurve.EASE_OUT),
        )

        label_widget = ft.Text(
            item.label, size=13, color=label_color, no_wrap=False,
            animate_opacity=ft.Animation(ITEM_ANIM_MS, ft.AnimationCurve.EASE_OUT),
        )

        label_container = ft.Container(
            content=label_widget,
            visible=self.expanded,
            margin=ft.margin.only(left=10),
            animate_opacity=ft.Animation(ITEM_ANIM_MS, ft.AnimationCurve.EASE_OUT),
        )

        row = ft.Row(
            controls=[icon_widget, label_container],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        def _handle_click(e, item_ref=item):
            if self.mobile and not self.expanded:
                self.expand()
                return
            try:
                item_ref.on_click(e)
            except Exception as ex:
                print(f"[SIDEBAR] click error: {ex}")

        container = ft.Container(
            content=row,
            padding=ft.padding.symmetric(horizontal=10, vertical=12),
            border_radius=theme.SIDEBAR_ITEM_RADIUS,
            bgcolor=bg,
            ink=True,
            on_click=_handle_click,
            tooltip=item.label,
            expand=True,
            animate=ft.Animation(ITEM_ANIM_MS, ft.AnimationCurve.EASE_OUT),
        )

        if item.item_id:
            self._button_refs[item.item_id] = {
                "container": container,
                "icon": icon_widget,
                "label": label_widget,
                "item": item,
            }

        return container

    # ------------------------------------------------------------------
    # Активный пункт
    # ------------------------------------------------------------------

    def set_active(self, item_id: Optional[str]) -> None:
        """Меняет подсветку активного пункта.

        ИСПРАВЛЕНО: работает и для accent-кнопок (Premium).
        Если item_id=None — сбрасывает все.
        """
        if self.active_id == item_id:
            return

        old_id = self.active_id
        self.active_id = item_id

        # Снимаем подсветку со старого
        if old_id and old_id in self._button_refs:
            self._reset_button(old_id)

        # Ставим подсветку на новый
        if item_id and item_id in self._button_refs:
            self._activate_button(item_id)

        try:
            self.page.update()
        except Exception:
            pass

    def _reset_button(self, item_id: str) -> None:
        ref = self._button_refs.get(item_id)
        if not ref:
            return
        item = ref["item"]
        bg, icon_color, label_color = self._get_button_colors(item, False)
        ref["container"].bgcolor = bg
        ref["icon"].color = icon_color
        ref["label"].color = label_color

    def _activate_button(self, item_id: str) -> None:
        ref = self._button_refs.get(item_id)
        if not ref:
            return
        item = ref["item"]
        bg, icon_color, label_color = self._get_button_colors(item, True)
        ref["container"].bgcolor = bg
        ref["icon"].color = icon_color
        ref["label"].color = label_color

    # ------------------------------------------------------------------
    # Раскрытие
    # ------------------------------------------------------------------

    def _on_hover(self, e: ft.ControlEvent) -> None:
        if e.data == "true":
            self.expand()
        else:
            self.collapse()

    def _on_panel_click(self, e: ft.ControlEvent) -> None:
        if self.expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self) -> None:
        if self.expanded:
            return
        self.expanded = True
        self.panel.width = theme.SIDEBAR_EXPANDED
        self._set_labels_visible(True)
        self._swap_logo(to_expanded=True)
        try:
            self.page.update()
        except Exception:
            pass

    def collapse(self) -> None:
        if not self.expanded:
            return
        self.expanded = False
        self.panel.width = theme.SIDEBAR_COLLAPSED
        self._set_labels_visible(False)
        self._swap_logo(to_expanded=False)
        try:
            self.page.update()
        except Exception:
            pass

    def _set_labels_visible(self, visible: bool) -> None:
        for ref in self._button_refs.values():
            try:
                label_container = ref["container"].content.controls[1]
                label_container.visible = visible
            except Exception:
                pass

    def build(self) -> ft.Container:
        return self.panel