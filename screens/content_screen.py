"""Автосоздание контента: генерация пачки постов по теме.

Возможности:
  • Ввод темы.
  • Мультивыбор форматов (пост / список / история / вопрос / реклама).
  • Мультивыбор стилей (сложный / простой / анти-ИИ / юмор).
  • Генерация 5-10 карточек сразу.
  • Сортировка: по дате / по формату / по стилю.
  • Фильтр по формату.
  • Копирование / удаление каждой карточки.
  • Сохранение в ContentFarm/auto_content.json.
"""

import json
import os
import threading
from datetime import datetime
from typing import Optional

import flet as ft

from services import paths, text_ai
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


# ---------- Пути ----------

def _content_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "auto_content.json")


def _load_items() -> list:
    p = _content_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_items(items: list) -> None:
    try:
        with open(_content_path(), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print(f"[CONTENT] save error: {ex}")


# ---------- Форматы ----------

FORMATS = [
    ("post",   ft.Icons.ARTICLE_ROUNDED,         "Пост",     "обычный пост"),
    ("list",   ft.Icons.FORMAT_LIST_BULLETED_ROUNDED, "Список", "5-7 пунктов"),
    ("story",  ft.Icons.AUTO_STORIES_ROUNDED,    "История",  "от первого лица"),
    ("quest",  ft.Icons.HELP_OUTLINE_ROUNDED,    "Вопрос",   "вопрос-ответ"),
    ("ad",     ft.Icons.CAMPAIGN_ROUNDED,        "Реклама",  "продающий"),
]

STYLES = [
    ("simple",   "💬", "Простой"),
    ("complex",  "🎓", "Сложный"),
    ("anti_ai",  "🥷", "Анти-ИИ"),
    ("humor",    "😄", "Юмор"),
]

SORTS = [
    ("date_desc",  "Сначала новые"),
    ("date_asc",   "Сначала старые"),
    ("format",     "По формату"),
    ("style",      "По стилю"),
]


def _fmt_date(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return f"{dt.day:02d}.{dt.month:02d} {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return ""


class ContentScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._bg_effect = None
        self._stopped = False

        self.items: list = _load_items()
        self.selected_formats: set = {"post"}
        self.selected_styles: set = {"simple"}
        self.current_sort: str = "date_desc"
        self.filter_format: Optional[str] = None
        self.is_generating = False
        self.count_to_generate = 5

        self.topic_field = ft.TextField(
            hint_text="Например: утренние пробежки для начинающих",
            multiline=True, min_lines=1, max_lines=3,
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=12,
            border_color=theme.DRAWER_ITEM_BORDER,
            focused_border_color=theme.PRIMARY,
            expand=True,
        )

        self.generate_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=18,
                            color=ft.Colors.WHITE),
                    ft.Text("Сгенерировать", size=14,
                            weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ],
                spacing=8, tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            border_radius=12,
            bgcolor=theme.PRIMARY,
            on_click=self._handle_generate,
            ink=True,
        )

        self.status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

        self.formats_row = ft.Row(spacing=8, run_spacing=8, wrap=True)
        self.styles_row = ft.Row(spacing=8, run_spacing=8, wrap=True)
        self.sort_dropdown = ft.Dropdown(
            value="date_desc",
            options=[ft.dropdown.Option(k, text=v) for k, v in SORTS],
            width=180,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=10,
            text_size=13,
            on_change=self._on_sort_change,
        )
        self.filter_row = ft.Row(spacing=8, run_spacing=8, wrap=True)

        self.cards_container = ft.Column(spacing=10)

        self._render_formats()
        self._render_styles()
        self._render_filter()
        self._render_cards()

    # ---------- Остановка ----------

    def stop_effect(self) -> None:
        self._stopped = True
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None

    # ---------- Построение ----------

    def build(self) -> ft.Container:
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

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=20,
                                        color=ft.Colors.WHITE),
                        width=40, height=40, border_radius=12,
                        bgcolor=theme.PRIMARY,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Автосоздание контента", size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text("Пачка постов по одной теме",
                                        size=11, color=theme.TEXT_SECONDARY),
                            ],
                            spacing=0, tight=True,
                        ),
                        margin=ft.margin.only(left=12),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
        )

        input_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Тема", size=12, weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    ft.Container(height=6),
                    ft.Row(
                        controls=[self.topic_field, self.generate_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Container(height=8),
                    self.status_text,
                ],
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
        )

        formats_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Форматы", size=12, weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    ft.Container(height=6),
                    self.formats_row,
                ],
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
        )

        styles_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Стили", size=12, weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    ft.Container(height=6),
                    self.styles_row,
                ],
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
        )

        controls_block = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text("Сортировка:", size=12,
                            color=theme.TEXT_SECONDARY),
                    self.sort_dropdown,
                    ft.Container(expand=True),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
        )

        filter_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Фильтр по формату", size=12,
                            weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY),
                    ft.Container(height=6),
                    self.filter_row,
                ],
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
        )

        cards_block = ft.Container(
            content=self.cards_container,
            padding=ft.padding.symmetric(horizontal=24, vertical=12),
        )

        content_col = ft.Column(
            controls=[
                header,
                input_block,
                formats_block,
                styles_block,
                controls_block,
                filter_block,
                ft.Container(height=1, bgcolor=theme.DIVIDER),
                cards_block,
                ft.Container(height=24),
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        main_layer = ft.Container(
            content=content_col,
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.6, theme.BG_DARK),
        )

        return ft.Container(
            content=ft.Stack(
                controls=[bg_layer, main_layer],
                expand=True,
            ),
            expand=True,
        )

    # ---------- Отрисовка форматов / стилей / фильтров ----------

    def _render_formats(self) -> None:
        self.formats_row.controls.clear()
        for key, icon, label, sub in FORMATS:
            is_active = key in self.selected_formats
            self.formats_row.controls.append(
                self._make_chip(key, icon, label, sub, is_active,
                                self._toggle_format)
            )

    def _render_styles(self) -> None:
        self.styles_row.controls.clear()
        for key, emoji, label in STYLES:
            is_active = key in self.selected_styles
            self.styles_row.controls.append(
                self._make_style_chip(key, emoji, label, is_active)
            )

    def _render_filter(self) -> None:
        self.filter_row.controls.clear()

        all_active = self.filter_format is None
        self.filter_row.controls.append(
            self._make_filter_chip("Все", all_active,
                                   lambda e: self._set_filter(None))
        )
        for key, icon, label, _sub in FORMATS:
            is_active = self.filter_format == key
            self.filter_row.controls.append(
                self._make_filter_chip(label, is_active,
                                       lambda e, k=key: self._set_filter(k))
            )

    def _make_chip(self, key, icon, label, sub, is_active, on_click):
        if is_active:
            bg = ft.Colors.with_opacity(0.18, theme.PRIMARY)
            border = theme.PRIMARY
            icon_c = ft.Colors.WHITE
            title_c = ft.Colors.WHITE
            sub_c = ft.Colors.with_opacity(0.85, theme.PRIMARY_LIGHT)
        else:
            bg = theme.SURFACE
            border = theme.DRAWER_ITEM_BORDER
            icon_c = theme.TEXT_PRIMARY
            title_c = theme.TEXT_PRIMARY
            sub_c = theme.TEXT_MUTED

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, size=18, color=icon_c),
                        width=36, height=36, border_radius=10,
                        bgcolor=(ft.Colors.with_opacity(0.15, theme.PRIMARY)
                                 if is_active else theme.BG_DARK),
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(label, size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=title_c),
                                ft.Text(sub, size=10, color=sub_c),
                            ],
                            spacing=0, tight=True,
                        ),
                        margin=ft.margin.only(left=10),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=12,
            bgcolor=bg,
            border=ft.border.all(2, border),
            on_click=lambda e: on_click(key),
            ink=True,
        )

    def _make_style_chip(self, key, emoji, label, is_active):
        bg = (ft.Colors.with_opacity(0.18, theme.PRIMARY)
              if is_active else theme.SURFACE)
        border = theme.PRIMARY if is_active else theme.DRAWER_ITEM_BORDER
        text_c = ft.Colors.WHITE if is_active else theme.TEXT_PRIMARY

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(emoji, size=16),
                    ft.Text(label, size=12, color=text_c,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=6, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border_radius=20,
            bgcolor=bg,
            border=ft.border.all(2, border),
            on_click=lambda e: self._toggle_style(key),
            ink=True,
        )

    def _make_filter_chip(self, label, is_active, on_click):
        bg = theme.PRIMARY if is_active else theme.SURFACE
        text_c = ft.Colors.WHITE if is_active else theme.TEXT_PRIMARY

        return ft.Container(
            content=ft.Text(label, size=12, color=text_c,
                            weight=ft.FontWeight.BOLD),
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            border_radius=20,
            bgcolor=bg,
            on_click=on_click,
            ink=True,
        )

    # ---------- Обработчики выбора ----------

    def _toggle_format(self, key: str) -> None:
        if key in self.selected_formats:
            if len(self.selected_formats) > 1:
                self.selected_formats.remove(key)
        else:
            self.selected_formats.add(key)
        self._render_formats()
        try:
            self.page.update()
        except Exception:
            pass

    def _toggle_style(self, key: str) -> None:
        if key in self.selected_styles:
            if len(self.selected_styles) > 1:
                self.selected_styles.remove(key)
        else:
            self.selected_styles.add(key)
        self._render_styles()
        try:
            self.page.update()
        except Exception:
            pass

    def _set_filter(self, key: Optional[str]) -> None:
        self.filter_format = key
        self._render_filter()
        self._render_cards()
        try:
            self.page.update()
        except Exception:
            pass

    def _on_sort_change(self, e) -> None:
        self.current_sort = e.control.value or "date_desc"
        self._render_cards()
        try:
            self.page.update()
        except Exception:
            pass

    # ---------- Генерация ----------

    def _handle_generate(self, e) -> None:
        if self.is_generating or self._stopped:
            return

        topic = (self.topic_field.value or "").strip()
        if not topic:
            self.page.open(ft.SnackBar(
                content=ft.Text("Введи тему"),
                duration=1500,
            ))
            return

        self.is_generating = True
        self.status_text.value = "⏳ Генерирую..."
        self.status_text.color = theme.TEXT_SECONDARY
        try:
            self.page.update()
        except Exception:
            pass

        formats = list(self.selected_formats)
        styles = list(self.selected_styles)
        count = self.count_to_generate

        def _worker():
            from services.user_profile import get_current as _gc
            profile = _gc()
            created = []

            for i in range(count):
                if self._stopped:
                    break
                fmt = formats[i % len(formats)]
                style = styles[i % len(styles)]

                variants = text_ai.generate_content(
                    idea=topic,
                    style=style,
                    history=None,
                    profile=profile,
                )
                text = variants[0] if variants else ""
                if not text:
                    text = "❌ Не удалось сгенерировать"

                created.append({
                    "id": f"{int(datetime.now().timestamp() * 1000)}-{i}",
                    "topic": topic,
                    "format": fmt,
                    "style": style,
                    "text": text,
                    "created_at": datetime.now().isoformat(),
                })

            def _done():
                self.items.extend(created)
                _save_items(self.items)
                self.is_generating = False
                self.status_text.value = f"✅ Готово: {len(created)} постов"
                self.status_text.color = theme.SUCCESS
                self._render_cards()
                try:
                    self.page.update()
                except Exception:
                    pass

            threading.Timer(0, _done).start()

        threading.Thread(target=_worker, daemon=True).start()

    # ---------- Список карточек ----------

    def _sorted_items(self) -> list:
        items = list(self.items)

        if self.filter_format:
            items = [i for i in items if i.get("format") == self.filter_format]

        if self.current_sort == "date_asc":
            items.sort(key=lambda x: x.get("created_at", ""))
        elif self.current_sort == "format":
            items.sort(key=lambda x: x.get("format", ""))
        elif self.current_sort == "style":
            items.sort(key=lambda x: x.get("style", ""))
        else:  # date_desc
            items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items

    def _render_cards(self) -> None:
        self.cards_container.controls.clear()
        items = self._sorted_items()

        if not items:
            self.cards_container.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED, size=56,
                                    color=ft.Colors.with_opacity(0.25,
                                                                 theme.TEXT_SECONDARY)),
                            ft.Container(height=12),
                            ft.Text("Введи тему и нажми «Сгенерировать»",
                                    size=15, color=theme.TEXT_SECONDARY,
                                    text_align=ft.TextAlign.CENTER),
                            ft.Container(height=6),
                            ft.Text("ИИ создаст несколько постов сразу",
                                    size=12,
                                    color=ft.Colors.with_opacity(0.5,
                                                                 theme.TEXT_SECONDARY),
                                    italic=True,
                                    text_align=ft.TextAlign.CENTER),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                    ),
                    alignment=ft.alignment.center,
                    padding=ft.padding.symmetric(vertical=60),
                )
            )
        else:
            for item in items:
                self.cards_container.controls.append(self._make_card(item))

    def _make_card(self, item: dict) -> ft.Container:
        fmt_key = item.get("format", "post")
        style_key = item.get("style", "simple")
        fmt_info = next((f for f in FORMATS if f[0] == fmt_key), FORMATS[0])
        style_info = next((s for s in STYLES if s[0] == style_key), STYLES[0])

        fmt_icon = fmt_info[1]
        fmt_label = fmt_info[2]
        style_label = f"{style_info[1]} {style_info[2]}"

        date_label = _fmt_date(item.get("created_at", ""))
        text = item.get("text", "")

        def copy_text(ev):
            try:
                self.page.set_clipboard(text)
                self.page.open(ft.SnackBar(
                    content=ft.Text("Скопировано"),
                    duration=1200,
                ))
            except Exception:
                pass

        def delete_item(ev):
            self.items = [i for i in self.items if i.get("id") != item.get("id")]
            _save_items(self.items)
            self._render_cards()
            try:
                self.page.update()
            except Exception:
                pass

        def send_to_tg(ev):
            profile = get_current()
            if not profile or not profile.tg_bots:
                self.page.open(ft.SnackBar(
                    content=ft.Text("Сначала добавь Telegram-бота"),
                    duration=2000,
                ))
                return
            bot = profile.get_active_bot()
            if not bot:
                return
            from services import telegram as tg
            ok, err = tg.send_message(bot.get("token", ""),
                                      bot.get("channel", ""), text)
            if ok:
                self.page.open(ft.SnackBar(
                    content=ft.Text("✅ Отправлено в Telegram"),
                    duration=2000,
                ))
            else:
                self.page.open(ft.SnackBar(
                    content=ft.Text(f"❌ {err}"),
                    duration=2500,
                ))

        header = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(fmt_icon, size=14,
                                    color=theme.PRIMARY),
                    width=28, height=28, border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.15, theme.PRIMARY),
                    alignment=ft.alignment.center,
                ),
                ft.Container(
                    content=ft.Text(fmt_label, size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY),
                    margin=ft.margin.only(left=8),
                ),
                ft.Container(
                    content=ft.Text(style_label, size=11,
                                    color=theme.TEXT_SECONDARY),
                    margin=ft.margin.only(left=8),
                ),
                ft.Container(expand=True),
                ft.Text(date_label, size=10, color=theme.TEXT_MUTED),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        )

        body = ft.Container(
            content=ft.Text(text, size=13, color=theme.TEXT_PRIMARY,
                            selectable=True, no_wrap=False),
            padding=ft.padding.only(top=10, bottom=10),
        )

        actions = ft.Row(
            controls=[
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.COPY_ROUNDED, size=14,
                                    color=theme.PRIMARY),
                            ft.Text("Копировать", size=11, color=theme.PRIMARY),
                        ],
                        spacing=4, tight=True,
                    ),
                    on_click=copy_text,
                ),
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SEND_ROUNDED, size=14,
                                    color=theme.PRIMARY),
                            ft.Text("Telegram", size=11, color=theme.PRIMARY),
                        ],
                        spacing=4, tight=True,
                    ),
                    on_click=send_to_tg,
                ),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_color=theme.DANGER,
                    icon_size=16,
                    tooltip="Удалить",
                    on_click=delete_item,
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            content=ft.Column(
                controls=[header, body, actions],
                spacing=0,
            ),
            padding=ft.padding.all(14),
            bgcolor=theme.SURFACE,
            border_radius=14,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
        )