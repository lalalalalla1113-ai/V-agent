"""Экран «Идеи для постов» — генератор идей через Cloudflare.

Пользователь вводит тему или выбирает из подсказок — ИИ придумывает
10 разных идей для постов. Каждую идею можно:
  • скопировать,
  • отправить в чат (как новую идею для генерации),
  • сразу сгенерировать по ней пост,
  • отправить в Telegram,
  • удалить из списка.

История идей хранится в ContentFarm/ideas_history.json.
"""

import json
import os
import threading
from datetime import datetime
from typing import Optional

import flet as ft

from services import paths, text_provider, text_ai
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect
from ui.message_bubble import render_telegram_html


# ===========================================================================
# Подсказки тем
# ===========================================================================

QUICK_TOPICS = [
    "Утренние привычки",
    "Продуктивность",
    "Психология",
    "Здоровое питание",
    "Путешествия",
    "Финансы",
    "Отношения",
    "Саморазвитие",
    "Спорт",
    "Работа из дома",
]

IDEA_STYLES = [
    ("universal", ft.Icons.AUTO_AWESOME_ROUNDED, "Универсальные"),
    ("story", ft.Icons.AUTO_STORIES_ROUNDED, "Истории"),
    ("list", ft.Icons.FORMAT_LIST_BULLETED_ROUNDED, "Списки"),
    ("question", ft.Icons.HELP_OUTLINE_ROUNDED, "Вопросы"),
    ("provocation", ft.Icons.BOLT_ROUNDED, "Провокации"),
]


# ===========================================================================
# ПУТИ
# ===========================================================================

def _history_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "ideas_history.json")


def _load_history() -> list:
    p = _history_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(items: list) -> None:
    try:
        with open(_history_path(), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print(f"[IDEAS] save error: {ex}")


def _fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return f"{dt.day:02d}.{dt.month:02d} {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return ""


# ===========================================================================
# ЭКРАН
# ===========================================================================

class IdeasScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.mobile = self._is_mobile()
        self._bg_effect = None
        self._stopped = False

        self.selected_style = "universal"
        self.is_generating = False
        self.history: list = _load_history()

        # Текущая пачка идей
        self.current_ideas: list = []

        # ---------- Поля ввода ----------
        self.topic_field = ft.TextField(
            hint_text="Например: как перестать откладывать дела",
            multiline=True, min_lines=1, max_lines=3,
            filled=True,
            fill_color=theme.SURFACE,
            color=theme.TEXT_PRIMARY,
            border_radius=12,
            border_color=theme.DRAWER_ITEM_BORDER,
            focused_border_color=theme.PRIMARY,
            text_size=14,
            expand=True,
        )

        self.generate_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, size=18,
                            color=ft.Colors.WHITE),
                    ft.Text("Придумать идеи", size=14,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=8, tight=True,
            ),
            bgcolor=theme.PRIMARY,
            on_click=self._handle_generate,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.padding.symmetric(horizontal=20, vertical=14),
            ),
        )

        self.status_text = ft.Text(
            "", size=12, color=theme.TEXT_SECONDARY,
        )

        self.ideas_container = ft.Column(
            controls=[], spacing=10, tight=True,
        )

        # Хранилище ссылок на чипы стилей: {key: {"container", "icon", "text"}}
        self._style_refs: dict = {}

        # Собираем Row стилей ОДИН раз
        self.styles_row = ft.Row(
            controls=self._build_style_chips(),
            spacing=8, run_spacing=8, wrap=True,
        )

        self._render_ideas()

    # ---------- Утилиты ----------

    def _is_mobile(self) -> bool:
        try:
            if self.page.platform in ("android", "ios"):
                return True
        except Exception:
            pass
        try:
            w = int(self.page.width or 0)
            return 0 < w < 700
        except Exception:
            return False

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

        top_pad = 32 if self.mobile else 0

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.LIGHTBULB_ROUNDED, size=20,
                            color=ft.Colors.WHITE,
                        ),
                        width=40, height=40, border_radius=12,
                        bgcolor=theme.PRIMARY,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Идеи для постов", size=20,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text(
                                    "10 разных идей по одной теме",
                                    size=11, color=theme.TEXT_SECONDARY,
                                ),
                            ],
                            spacing=0, tight=True,
                        ),
                        margin=ft.margin.only(left=12),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(
                left=24, right=24, top=top_pad + 14, bottom=10,
            ),
        )

        # ---------- Стили ----------
        styles_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Стиль идей",
                        size=12, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(height=8),
                    self.styles_row,
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
        )

        # ---------- Ввод темы ----------
        topic_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Тема",
                        size=12, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(height=6),
                    ft.Row(
                        controls=[self.topic_field, self.generate_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
        )

        # ---------- Подсказки тем ----------
        quick_chips = []
        for t in QUICK_TOPICS:
            quick_chips.append(self._make_quick_chip(t))

        quick_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Быстрые темы",
                        size=11, color=theme.TEXT_MUTED,
                    ),
                    ft.Container(height=6),
                    ft.Row(
                        controls=quick_chips,
                        spacing=6, run_spacing=6, wrap=True,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=6),
        )

        # ---------- Статус ----------
        status_block = ft.Container(
            content=self.status_text,
            padding=ft.padding.symmetric(horizontal=24, vertical=4),
        )

        # ---------- Идеи ----------
        ideas_block = ft.Container(
            content=self.ideas_container,
            padding=ft.padding.symmetric(horizontal=24, vertical=12),
        )

        content_col = ft.Column(
            controls=[
                header,
                styles_block,
                topic_block,
                quick_block,
                status_block,
                ft.Divider(
                    color=ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY),
                ),
                ideas_block,
                ft.Container(height=40),
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

    # ---------- Стили (чипы) ----------

    def _build_style_chips(self) -> list:
        """Создаёт чипы ОДИН раз. Дальше меняем свойства на месте."""
        self._style_refs.clear()
        chips = []
        for key, icon, label in IDEA_STYLES:
            is_active = key == self.selected_style

            icon_widget = ft.Icon(
                icon, size=14,
                color=ft.Colors.WHITE if is_active else theme.TEXT_PRIMARY,
            )
            text_widget = ft.Text(
                label, size=12,
                color=ft.Colors.WHITE if is_active else theme.TEXT_PRIMARY,
                weight=ft.FontWeight.BOLD,
            )

            container = ft.Container(
                content=ft.Row(
                    controls=[icon_widget, text_widget],
                    spacing=6, tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=14, vertical=8),
                border_radius=20,
                bgcolor=theme.PRIMARY if is_active else theme.SURFACE,
                border=ft.border.all(
                    2,
                    theme.PRIMARY if is_active
                    else theme.DRAWER_ITEM_BORDER,
                ),
                on_click=lambda e, k=key: self._select_style(k),
                ink=True,
                animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            )

            self._style_refs[key] = {
                "container": container,
                "icon": icon_widget,
                "text": text_widget,
            }
            chips.append(container)
        return chips

    def _select_style(self, key: str) -> None:
        """Меняет подсветку чипов НА МЕСТЕ, не пересоздавая их."""
        if self.selected_style == key:
            return
        self.selected_style = key

        for k, ref in self._style_refs.items():
            active = k == key
            ref["container"].bgcolor = (
                theme.PRIMARY if active else theme.SURFACE
            )
            ref["container"].border = ft.border.all(
                2,
                theme.PRIMARY if active else theme.DRAWER_ITEM_BORDER,
            )
            ref["icon"].color = (
                ft.Colors.WHITE if active else theme.TEXT_PRIMARY
            )
            ref["text"].color = (
                ft.Colors.WHITE if active else theme.TEXT_PRIMARY
            )

        try:
            self.page.update()
        except Exception:
            pass

    # ---------- Быстрые темы ----------

    def _make_quick_chip(self, text: str) -> ft.Container:
        def pick(e):
            self.topic_field.value = text
            try:
                self.topic_field.update()
            except Exception:
                pass

        return ft.Container(
            content=ft.Text(
                text, size=11, color=theme.TEXT_SECONDARY,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            bgcolor=ft.Colors.with_opacity(0.5, theme.SURFACE),
            border_radius=16,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            on_click=pick,
            ink=True,
        )

    # ---------- Пустая заглушка ----------

    def _build_empty_ideas(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=44,
                        color=ft.Colors.with_opacity(
                            0.25, theme.TEXT_SECONDARY,
                        ),
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Введи тему — ИИ придумает 10 идей",
                        size=14, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=4),
                    ft.Text(
                        "Идеи можно копировать, отправлять в чат или сразу "
                        "генерировать по ним пост",
                        size=11, color=theme.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=40),
            alignment=ft.alignment.center,
        )

    def _render_ideas(self) -> None:
        self.ideas_container.controls.clear()
        if not self.current_ideas:
            self.ideas_container.controls.append(self._build_empty_ideas())
            return

        for i, idea in enumerate(self.current_ideas, 1):
            self.ideas_container.controls.append(
                self._make_idea_card(i, idea)
            )

    # ---------- Карточка идеи ----------

    def _make_idea_card(self, index: int, idea: str) -> ft.Container:
        def copy_idea(e):
            try:
                self.page.set_clipboard(idea)
                self.page.open(ft.SnackBar(
                    content=ft.Text("Идея скопирована"),
                    duration=1500,
                ))
            except Exception:
                pass

        def send_to_chat(e):
            try:
                chat = getattr(self.page, "_vagent_chat_screen", None)
                if chat is not None:
                    chat.input_field.value = idea
                    try:
                        chat.input_field.update()
                    except Exception:
                        pass
                    chat._handle_nav("home")
                else:
                    self.page.set_clipboard(idea)
                self.page.open(ft.SnackBar(
                    content=ft.Text("Идея отправлена в чат"),
                    duration=1500,
                ))
            except Exception as ex:
                print(f"[IDEAS] send_to_chat error: {ex}")

        def generate_post(e):
            if self.is_generating:
                return
            self.is_generating = True
            self.status_text.value = "⏳ Генерирую пост по идее..."
            self.status_text.color = theme.TEXT_SECONDARY
            try:
                self.page.update()
            except Exception:
                pass

            idea_copy = idea

            def _worker():
                from services.user_profile import get_current as _gc
                variants = text_ai.generate_content(
                    idea=idea_copy,
                    style="simple",
                    history=None,
                    profile=_gc(),
                )

                def _done():
                    self.is_generating = False
                    self.status_text.value = "✅ Пост сгенерирован"
                    self.status_text.color = theme.SUCCESS
                    try:
                        self.page.update()
                    except Exception:
                        pass

                    self._save_idea_to_history(idea_copy, variants)
                    self._show_result_dialog(idea_copy, variants)

                threading.Timer(0, _done).start()

            threading.Thread(target=_worker, daemon=True).start()

        def send_to_tg(e):
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

            if self.is_generating:
                return
            self.is_generating = True
            self.status_text.value = "⏳ Генерирую и отправляю..."
            self.status_text.color = theme.TEXT_SECONDARY
            try:
                self.page.update()
            except Exception:
                pass

            idea_copy = idea

            def _worker():
                from services.user_profile import get_current as _gc
                variants = text_ai.generate_content(
                    idea=idea_copy,
                    style="simple",
                    history=None,
                    profile=_gc(),
                )
                text = variants[0] if variants else ""
                if not text:
                    def _fail():
                        self.is_generating = False
                        self.status_text.value = "❌ Не удалось сгенерировать"
                        self.status_text.color = theme.DANGER
                        try:
                            self.page.update()
                        except Exception:
                            pass
                    threading.Timer(0, _fail).start()
                    return

                from services import telegram as tg
                ok, err = tg.send_message(
                    bot.get("token", ""), bot.get("channel", ""), text,
                )

                def _done():
                    self.is_generating = False
                    if ok:
                        self.status_text.value = "✅ Отправлено в Telegram"
                        self.status_text.color = theme.SUCCESS
                        self._save_idea_to_history(idea_copy, variants)
                    else:
                        self.status_text.value = f"❌ {err}"
                        self.status_text.color = theme.DANGER
                    try:
                        self.page.update()
                    except Exception:
                        pass

                threading.Timer(0, _done).start()

            threading.Thread(target=_worker, daemon=True).start()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(
                                    str(index), size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                width=26, height=26, border_radius=13,
                                bgcolor=theme.PRIMARY,
                                alignment=ft.alignment.center,
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.COPY_ROUNDED,
                                icon_size=15,
                                icon_color=theme.TEXT_MUTED,
                                tooltip="Копировать",
                                on_click=copy_idea,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.SEND_ROUNDED,
                                icon_size=15,
                                icon_color=theme.TEXT_MUTED,
                                tooltip="В Telegram",
                                on_click=send_to_tg,
                            ),
                        ],
                        spacing=2,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        idea, size=13,
                        color=theme.TEXT_PRIMARY,
                        selectable=True, no_wrap=False,
                    ),
                    ft.Container(height=10),
                    ft.Row(
                        controls=[
                            ft.TextButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.FORWARD_TO_INBOX_ROUNDED,
                                            size=13,
                                            color=theme.PRIMARY,
                                        ),
                                        ft.Text(
                                            "В чат", size=11,
                                            color=theme.PRIMARY,
                                        ),
                                    ],
                                    spacing=4, tight=True,
                                ),
                                on_click=send_to_chat,
                            ),
                            ft.TextButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.AUTO_AWESOME_ROUNDED,
                                            size=13,
                                            color=theme.PRIMARY,
                                        ),
                                        ft.Text(
                                            "Создать пост", size=11,
                                            color=theme.PRIMARY,
                                        ),
                                    ],
                                    spacing=4, tight=True,
                                ),
                                on_click=generate_post,
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.all(12),
            bgcolor=theme.SURFACE,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            border_radius=14,
        )

    # ---------- Генерация идей ----------

    def _handle_generate(self, e) -> None:
        if self.is_generating or self._stopped:
            return

        topic = (self.topic_field.value or "").strip()
        if not topic:
            self.page.open(ft.SnackBar(
                content=ft.Text("Введи тему или выбери подсказку"),
                duration=1500,
            ))
            return

        self.is_generating = True
        self.generate_btn.disabled = True
        self.status_text.value = "⏳ Придумываю идеи..."
        self.status_text.color = theme.TEXT_SECONDARY
        try:
            self.page.update()
        except Exception:
            pass

        style_key = self.selected_style

        def _worker():
            prompt = self._build_prompt(topic, style_key)
            result = text_provider.ask(
                prompt,
                system="Ты креативный SMM-редактор. Придумываешь идеи "
                       "для постов. Выдаёшь только список, без пояснений.",
                max_tokens=900,
            )

            def _done():
                self.is_generating = False
                self.generate_btn.disabled = False

                if not result:
                    self.status_text.value = "❌ Не удалось получить идеи"
                    self.status_text.color = theme.DANGER
                    try:
                        self.page.update()
                    except Exception:
                        pass
                    return

                ideas = self._parse_ideas(result)
                if not ideas:
                    self.status_text.value = "❌ ИИ вернул пустой ответ"
                    self.status_text.color = theme.DANGER
                    try:
                        self.page.update()
                    except Exception:
                        pass
                    return

                self.current_ideas = ideas
                self.status_text.value = f"✅ Готово: {len(ideas)} идей"
                self.status_text.color = theme.SUCCESS
                self._render_ideas()
                try:
                    self.page.update()
                except Exception:
                    pass

            threading.Timer(0, _done).start()

        threading.Thread(target=_worker, daemon=True).start()

    def _build_prompt(self, topic: str, style_key: str) -> str:
        style_hints = {
            "universal": (
                "Универсальные идеи — разные форматы: инструкция, "
                "подборка, лайфхак, разбор, личный опыт."
            ),
            "story": (
                "Идеи в формате историй от первого лица. "
                "Каждая — начало «Однажды…» или «Помню, как…»."
            ),
            "list": (
                "Идеи в формате списков. Каждая — «5 способов…», "
                "«7 ошибок…», «10 фактов…»."
            ),
            "question": (
                "Идеи в формате вопрос-ответ. Каждая — начинается "
                "с вопроса читателю."
            ),
            "provocation": (
                "Провокационные идеи. Каждая — резкое утверждение, "
                "ломающее шаблоны, спорный тезис."
            ),
        }
        hint = style_hints.get(style_key, style_hints["universal"])

        return (
            f"Тема: «{topic}»\n\n"
            f"Придумай РОВНО 10 разных идей для постов по этой теме.\n\n"
            f"Стиль: {hint}\n\n"
            "ФОРМАТ ОТВЕТА:\n"
            "Каждая идея на новой строке, начинается с цифры и точки.\n"
            "Идея = 1-2 предложения, конкретная, без воды.\n"
            "НЕ пиши вступление, НЕ пиши заключение.\n"
            "Только список 1-10.\n\n"
            "Пример:\n"
            "1. Как <конкретное действие> за <конкретный срок>\n"
            "2. 5 ошибок, которые <конкретная проблема>\n"
            "...\n\n"
            "Начни СРАЗУ с «1.»."
        )

    def _parse_ideas(self, raw: str) -> list:
        import re as _re
        text = (raw or "").strip()

        pattern = _re.compile(
            r"^\s*(\d+)\s*[\.\)]\s*(.+?)(?=^\s*\d+\s*[\.\)]|\Z)",
            _re.MULTILINE | _re.DOTALL,
        )
        ideas = []
        for m in pattern.finditer(text):
            body = m.group(2).strip()
            body = _re.sub(r"\s+", " ", body)
            if body:
                ideas.append(body)

        if not ideas:
            for line in text.split("\n"):
                line = line.strip()
                if len(line) > 5:
                    ideas.append(line)

        return ideas[:10]

    # ---------- Сохранение в историю ----------

    def _save_idea_to_history(self, idea: str, variants: list) -> None:
        try:
            item = {
                "id": f"{int(datetime.now().timestamp() * 1000)}",
                "idea": idea,
                "post": variants[0] if variants else "",
                "created_at": datetime.now().isoformat(),
            }
            self.history.insert(0, item)
            self.history = self.history[:100]
            _save_history(self.history)
        except Exception as ex:
            print(f"[IDEAS] save to history error: {ex}")

    # ---------- Показ результата ----------

    def _show_result_dialog(self, idea: str, variants: list) -> None:
        text = variants[0] if variants else ""

        def close_dialog(ev):
            try:
                self.page.close(dialog)
            except Exception:
                pass

        def copy_post(ev):
            try:
                # Копируем С ТЕГАМИ — чтобы вставка в Telegram дала формат
                self.page.set_clipboard(text)
                self.page.open(ft.SnackBar(
                    content=ft.Text("Пост скопирован (с форматированием)"),
                    duration=1500,
                ))
            except Exception:
                pass

        def send_tg(ev):
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
            ok, err = tg.send_message(
                bot.get("token", ""), bot.get("channel", ""), text,
            )
            try:
                self.page.close(dialog)
            except Exception:
                pass
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

        # ВАЖНО: визуальный рендер с жирным/курсивом/цитатой
        rendered = render_telegram_html(text, base_size=13)

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            title=ft.Text("Готовый пост", color=theme.TEXT_PRIMARY),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"💡 {idea}",
                            size=11, color=theme.TEXT_MUTED,
                            italic=True, selectable=True,
                        ),
                        ft.Container(height=10),
                        ft.Container(
                            content=rendered,
                            padding=ft.padding.all(12),
                            bgcolor=theme.BG_DARK,
                            border_radius=10,
                        ),
                    ],
                    spacing=0, tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=480, height=460,
            ),
            actions=[
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.COPY_ROUNDED, size=14,
                                    color=theme.PRIMARY),
                            ft.Text("Копировать", size=12,
                                    color=theme.PRIMARY),
                        ],
                        spacing=4, tight=True,
                    ),
                    on_click=copy_post,
                ),
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SEND_ROUNDED, size=14,
                                    color=theme.PRIMARY),
                            ft.Text("Telegram", size=12,
                                    color=theme.PRIMARY),
                        ],
                        spacing=4, tight=True,
                    ),
                    on_click=send_tg,
                ),
                ft.TextButton(
                    "Закрыть",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        try:
            self.page.open(dialog)
            self.page.update()
        except Exception as ex:
            print(f"[IDEAS] show dialog error: {ex}")