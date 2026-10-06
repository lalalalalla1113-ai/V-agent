"""Левая боковая панель с кнопками меню и логотипом V-AGENT.

Дизайн: максимально чёрный фон (#050505) в цвет логотипа,
фиолетовые акценты для активных пунктов.

Логотип:
  • Свёрнутая шторка → квадратный знак "V" (logo_v_only.webp)
  • Развёрнутая шторка → горизонтальная надпись "V-AGENT" (logo_text.webp)
  • Переход — плавный через прозрачность (opacity).

Анимации:
  • Ширина шторки — SIDEBAR_ANIM_MS.
  • Логотип — плавный кроссфейд через opacity.
  • Подсветка активного пункта — плавно (bgcolor, icon.color, text.color).
"""

from __future__ import annotations

from typing import Callable, Optional

import flet as ft

from ui import theme


# ---------------------------------------------------------------------------
# Логотипы
# ---------------------------------------------------------------------------

LOGO_V_FILENAME = "logo_v_only.webp"
LOGO_TEXT_FILENAME = "logo_text.webp"

LOGO_BOX_HEIGHT = 72
LOGO_V_SIZE = 44
LOGO_TEXT_WIDTH = 180

FADE_MS = 260
# Длительность анимации подсветки кнопок
ITEM_ANIM_MS = 220


class SidebarItem:
    """Одна кнопка боковой панели."""

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
    """Боковая панель: логотип + top-блок + bottom-блок."""

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

        # Список ссылок на виджеты кнопок для последующей анимации
        # Формат: {item_id: {"container": ..., "icon": ..., "label": ...}}
        self._button_refs: dict = {}

        self.items_column = ft.Column(controls=[], spacing=4)
        self.bottom_column = ft.Column(controls=[], spacing=4)

        # ---- Логотип: две картинки в Stack, кроссфейд через opacity ----
        self.logo_v = ft.Image(
            src=LOGO_V_FILENAME,
            width=LOGO_V_SIZE,
            height=LOGO_V_SIZE,
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
            width=LOGO_TEXT_WIDTH,
            height=LOGO_BOX_HEIGHT,
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

        # ---- Панель ----
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
            bgcolor=theme.SIDEBAR_BG,
            border=ft.border.only(
                right=ft.BorderSide(1, theme.SIDEBAR_BORDER),
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=8),
            animate=ft.Animation(
                theme.SIDEBAR_ANIM_MS, ft.AnimationCurve.EASE_OUT,
            ),
            on_hover=self._on_hover,
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
    # Кнопки меню
    # ------------------------------------------------------------------

    def _build_items(self) -> None:
        """Создаёт кнопки один раз. Дальше меняем свойства, а не пересоздаём."""
        self.items_column.controls.clear()
        self.bottom_column.controls.clear()
        self._button_refs.clear()

        for item in self.items:
            self.items_column.controls.append(self._make_button(item))

        for item in self.bottom_items:
            self.bottom_column.controls.append(self._make_button(item))

    def _make_button(self, item: SidebarItem) -> ft.Container:
        is_active = (
            item.item_id is not None
            and item.item_id == self.active_id
        )

        if item.accent or is_active:
            icon_color = ft.Colors.WHITE
            label_color = ft.Colors.WHITE
            bg = theme.PRIMARY
        else:
            icon_color = item.color if item.color else theme.TEXT_PRIMARY
            label_color = theme.TEXT_PRIMARY
            bg = ft.Colors.TRANSPARENT

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

        container = ft.Container(
            content=row,
            padding=ft.padding.symmetric(horizontal=10, vertical=12),
            border_radius=theme.SIDEBAR_ITEM_RADIUS,
            bgcolor=bg,
            ink=True,
            on_click=item.on_click,
            tooltip=item.label,
            expand=True,
            # Анимируем именно фон — при переключении active он плавно
            # переходит из прозрачного в фиолетовый (и обратно).
            animate=ft.Animation(ITEM_ANIM_MS, ft.AnimationCurve.EASE_OUT),
        )

        # Запоминаем ссылки для будущей анимации active
        if item.item_id:
            self._button_refs[item.item_id] = {
                "container": container,
                "icon": icon_widget,
                "label": label_widget,
                "item": item,
            }

        return container

    # ------------------------------------------------------------------
    # Активный пункт, hover
    # ------------------------------------------------------------------

    def set_active(self, item_id: Optional[str]) -> None:
        """Плавно переключает подсветку активного пункта.

        Не пересоздаёт кнопки — только меняет цвета существующих.
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
        # Если accent=True — этот пункт всегда фиолетовый, не сбрасываем
        if item.accent:
            return
        ref["container"].bgcolor = ft.Colors.TRANSPARENT
        ref["icon"].color = item.color if item.color else theme.TEXT_PRIMARY
        ref["label"].color = theme.TEXT_PRIMARY

    def _activate_button(self, item_id: str) -> None:
        ref = self._button_refs.get(item_id)
        if not ref:
            return
        ref["container"].bgcolor = theme.PRIMARY
        ref["icon"].color = ft.Colors.WHITE
        ref["label"].color = ft.Colors.WHITE

    def _on_hover(self, e: ft.ControlEvent) -> None:
        if e.data == "true":
            self.expand()
        else:
            self.collapse()

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
        """Меняет видимость подписей у всех кнопок."""
        for ref in self._button_refs.values():
            try:
                label_container = ref["container"].content.controls[1]
                label_container.visible = visible
            except Exception:
                pass

    def build(self) -> ft.Container:
        return self.panel