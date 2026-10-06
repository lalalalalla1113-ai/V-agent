"""Экран «Шаблоны» — готовые структуры постов.

Пользователь выбирает шаблон, заполняет поля (тема, аудитория, тон),
нажимает «Сгенерировать» — ИИ собирает готовый пост по этому шаблону.

Результат рендерится С ВИЗУАЛЬНЫМ ФОРМАТИРОВАНИЕМ (жирный, курсив,
цитата-синий-блок) через ui.message_bubble.render_telegram_html().
"""

import json
import os
import threading
from datetime import datetime
from typing import Optional

import flet as ft

from services import paths, text_provider
from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect
from ui.message_bubble import render_telegram_html


# ===========================================================================
# ШАБЛОНЫ
# ===========================================================================

TEMPLATES = [
    {
        "id": "instruction",
        "icon": ft.Icons.MENU_BOOK_ROUNDED,
        "title": "Инструкция",
        "subtitle": "Пошаговое руководство",
        "color": "#2196F3",
        "structure": (
            "1. Заголовок с эмодзи: «Как <сделать что-то>»\n"
            "2. Короткое вступление: зачем это нужно (1-2 предложения)\n"
            "3. Список шагов (3-7 пунктов), каждый с эмодзи-маркером\n"
            "4. Один важный совет выделить цитатой <blockquote>\n"
            "5. Вопрос читателю в конце"
        ),
        "fields": [
            ("topic", "Что делаем?", "Например: приготовить идеальный омлет"),
            ("audience", "Для кого?", "Например: для новичков на кухне"),
        ],
    },
    {
        "id": "review",
        "icon": ft.Icons.RATE_REVIEW_ROUNDED,
        "title": "Обзор",
        "subtitle": "Мнение о продукте/сервисе",
        "color": "#9C27B0",
        "structure": (
            "1. Заголовок: цепляющее название обзора\n"
            "2. Вступление: с чем сравниваем, для кого\n"
            "3. Плюсы (3-5 пунктов с ✅)\n"
            "4. Минусы (2-3 пункта с ❌)\n"
            "5. Итог цитатой <blockquote>: рекомендация или нет\n"
            "6. Вопрос: «А вы пробовали?»"
        ),
        "fields": [
            ("topic", "Что обозреваем?", "Например: беспроводные наушники"),
            ("audience", "Для кого обзор?", "Например: для бегунов"),
        ],
    },
    {
        "id": "facts",
        "icon": ft.Icons.LIGHTBULB_ROUNDED,
        "title": "10 фактов",
        "subtitle": "Подборка интересного",
        "color": "#FF9800",
        "structure": (
            "1. Заголовок: «10 фактов о <тема>, которые вас удивят»\n"
            "2. Короткое вступление (1 предложение)\n"
            "3. Ровно 10 фактов, каждый с новой строки и эмодзи\n"
            "4. Один самый удивительный факт выделить цитатой\n"
            "5. Вопрос: какой факт удивил больше всего?"
        ),
        "fields": [
            ("topic", "Тема подборки", "Например: космос"),
            ("audience", "Для кого?", "Например: для любознательных"),
        ],
    },
    {
        "id": "case",
        "icon": ft.Icons.TRENDING_UP_ROUNDED,
        "title": "Кейс",
        "subtitle": "История успеха",
        "color": "#4CAF50",
        "structure": (
            "1. Заголовок: результат в цифрах или фактах\n"
            "2. Было: с чего начинали (2-3 строки)\n"
            "3. Что сделали: 3-4 ключевых шага\n"
            "4. Стало: результат с конкретикой\n"
            "5. Вывод/урок цитатой <blockquote>\n"
            "6. Вопрос: «А у вас был похожий опыт?»"
        ),
        "fields": [
            ("topic", "О чём кейс?", "Например: как я выучил английский за год"),
            ("audience", "Для кого?", "Например: для тех, кто учит язык"),
        ],
    },
    {
        "id": "mistakes",
        "icon": ft.Icons.ERROR_OUTLINE_ROUNDED,
        "title": "Ошибки",
        "subtitle": "Чего не стоит делать",
        "color": "#E53935",
        "structure": (
            "1. Заголовок: «5 ошибок в <тема>, которые стоят дорого»\n"
            "2. Вступление: почему это важно\n"
            "3. Список ошибок (3-5), каждая с объяснением\n"
            "4. Как правильно — цитатой <blockquote>\n"
            "5. Вопрос: «Какую ошибку совершали вы?»"
        ),
        "fields": [
            ("topic", "Тема", "Например: вложения в крипту"),
            ("audience", "Для кого?", "Например: для начинающих инвесторов"),
        ],
    },
    {
        "id": "question",
        "icon": ft.Icons.HELP_OUTLINE_ROUNDED,
        "title": "Вопрос-ответ",
        "subtitle": "Разбор частого вопроса",
        "color": "#00BCD4",
        "structure": (
            "1. Заголовок: сам вопрос крупно\n"
            "2. Короткий ответ (1-2 предложения)\n"
            "3. Развёрнуто: 2-3 абзаца объяснения\n"
            "4. Пример из жизни\n"
            "5. Итог цитатой <blockquote>\n"
            "6. Ещё один вопрос читателю"
        ),
        "fields": [
            ("topic", "Какой вопрос?", "Например: стоит ли начинать блог в 2025?"),
            ("audience", "Кто спрашивает?", "Например: новички в блогинге"),
        ],
    },
    {
        "id": "top",
        "icon": ft.Icons.STAR_ROUNDED,
        "title": "ТОП-N",
        "subtitle": "Рейтинг или подборка",
        "color": "#FFC107",
        "structure": (
            "1. Заголовок: «ТОП-5 <тема> по версии ...»\n"
            "2. Вступление: критерии отбора\n"
            "3. Нумерованный список с описанием каждого пункта\n"
            "4. Победитель — выделить цитатой <blockquote>\n"
            "5. Вопрос: «А что бы вы добавили?»"
        ),
        "fields": [
            ("topic", "Что в топе?", "Например: фильмы 2024 года"),
            ("audience", "Для кого?", "Например: для любителей кино"),
        ],
    },
    {
        "id": "comparison",
        "icon": ft.Icons.COMPARE_ARROWS_ROUNDED,
        "title": "Сравнение",
        "subtitle": "A vs B",
        "color": "#673AB7",
        "structure": (
            "1. Заголовок: «<A> vs <B>: что выбрать?»\n"
            "2. Кратко о каждом варианте\n"
            "3. Таблица или список с плюсами/минусами каждого\n"
            "4. Вывод: для кого что лучше — цитатой <blockquote>\n"
            "5. Вопрос: «А что выбрали вы?»"
        ),
        "fields": [
            ("topic", "Что сравниваем?", "Например: iPhone vs Android"),
            ("audience", "Для кого?", "Например: для тех, кто выбирает телефон"),
        ],
    },
]


# ===========================================================================
# ПУТИ
# ===========================================================================

def _history_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "template_history.json")


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
        print(f"[TEMPLATES] save error: {ex}")


def _fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return f"{dt.day:02d}.{dt.month:02d} {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return ""


# ===========================================================================
# ЭКРАН
# ===========================================================================

class TemplatesScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.mobile = self._is_mobile()
        self._bg_effect = None
        self._stopped = False

        self.selected_template_id: Optional[str] = None
        self.is_generating = False
        self.history: list = _load_history()

        self.templates_grid = ft.Row(
            controls=[], spacing=12, run_spacing=12, wrap=True,
        )

        self.fields_container = ft.Column(
            controls=[], spacing=10, tight=True,
        )

        self.result_container = ft.Container(
            content=self._build_empty_state(),
            padding=ft.padding.symmetric(vertical=20),
        )

        self.status_text = ft.Text(
            "", size=12, color=theme.TEXT_SECONDARY,
        )

        self.generate_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=18,
                            color=ft.Colors.WHITE),
                    ft.Text("Сгенерировать", size=14,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=8, tight=True,
            ),
            bgcolor=theme.PRIMARY,
            on_click=self._handle_generate,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.padding.symmetric(horizontal=22, vertical=14),
            ),
            disabled=True,
        )

        self._field_widgets: dict = {}
        self._render_templates()

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
                            ft.Icons.GRID_VIEW_ROUNDED, size=20,
                            color=ft.Colors.WHITE,
                        ),
                        width=40, height=40, border_radius=12,
                        bgcolor=theme.PRIMARY,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Шаблоны постов", size=20,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_PRIMARY),
                                ft.Text(
                                    "Готовые структуры — ИИ напишет по ним",
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

        templates_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Выбери шаблон",
                        size=13, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(height=10),
                    self.templates_grid,
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
        )

        fields_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Заполни поля",
                        size=13, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_SECONDARY,
                    ),
                    ft.Container(height=10),
                    self.fields_container,
                    ft.Container(height=14),
                    ft.Row(
                        controls=[
                            self.status_text,
                            ft.Container(expand=True),
                            self.generate_btn,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
        )

        result_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Divider(
                        color=ft.Colors.with_opacity(0.1, theme.TEXT_SECONDARY),
                    ),
                    ft.Container(
                        content=ft.Text(
                            "Результат",
                            size=13, weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_SECONDARY,
                        ),
                    ),
                    ft.Container(height=8),
                    ft.Container(
                        content=self.result_container,
                        padding=ft.padding.symmetric(horizontal=24),
                    ),
                ],
                spacing=6, tight=True,
            ),
            padding=ft.padding.only(top=8),
        )

        content_col = ft.Column(
            controls=[
                header,
                templates_block,
                fields_block,
                result_block,
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

    # ---------- Шаблоны ----------

    def _render_templates(self) -> None:
        self.templates_grid.controls.clear()
        for tpl in TEMPLATES:
            is_active = tpl["id"] == self.selected_template_id
            self.templates_grid.controls.append(
                self._make_template_card(tpl, is_active)
            )

    def _make_template_card(self, tpl: dict, is_active: bool) -> ft.Container:
        color = tpl["color"]

        bg = (
            ft.Colors.with_opacity(0.15, color) if is_active
            else ft.Colors.with_opacity(0.6, theme.SURFACE)
        )
        border = color if is_active else theme.DRAWER_ITEM_BORDER

        def on_click(e):
            self._select_template(tpl["id"])

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            tpl["icon"], size=22,
                            color=ft.Colors.WHITE if is_active else color,
                        ),
                        width=44, height=44, border_radius=12,
                        bgcolor=(
                            color if is_active
                            else ft.Colors.with_opacity(0.15, color)
                        ),
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        tpl["title"], size=14,
                        weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        tpl["subtitle"], size=10,
                        color=theme.TEXT_SECONDARY,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=2, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            width=150, height=130,
            padding=ft.padding.all(12),
            bgcolor=bg,
            border=ft.border.all(2, border),
            border_radius=14,
            on_click=on_click,
            ink=True,
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            scale=1.0,
            on_hover=self._hover_scale,
        )

    def _hover_scale(self, e: ft.ControlEvent) -> None:
        try:
            ctrl = e.control
            if e.data == "true":
                ctrl.scale = 1.03
            else:
                ctrl.scale = 1.0
            ctrl.update()
        except Exception:
            pass

    def _select_template(self, tpl_id: str) -> None:
        self.selected_template_id = tpl_id
        self._render_templates()
        self._render_fields()
        self.generate_btn.disabled = False
        try:
            self.page.update()
        except Exception:
            pass

    # ---------- Поля шаблона ----------

    def _render_fields(self) -> None:
        self.fields_container.controls.clear()
        self._field_widgets.clear()

        tpl = self._get_selected_template()
        if not tpl:
            return

        structure_block = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LIST_ALT_ROUNDED, size=14,
                                    color=theme.PRIMARY),
                            ft.Text(
                                f"Структура шаблона «{tpl['title']}»",
                                size=12, weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_PRIMARY,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        tpl["structure"],
                        size=11, color=theme.TEXT_SECONDARY,
                        selectable=True,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.all(12),
            bgcolor=ft.Colors.with_opacity(0.08, theme.PRIMARY),
            border=ft.border.all(1, ft.Colors.with_opacity(0.25, theme.PRIMARY)),
            border_radius=12,
        )
        self.fields_container.controls.append(structure_block)
        self.fields_container.controls.append(ft.Container(height=10))

        for field_key, label, hint in tpl["fields"]:
            field = ft.TextField(
                label=label,
                hint_text=hint,
                multiline=True, min_lines=1, max_lines=3,
                filled=True,
                fill_color=theme.SURFACE,
                color=theme.TEXT_PRIMARY,
                border_radius=10,
                border_color=theme.DRAWER_ITEM_BORDER,
                focused_border_color=theme.PRIMARY,
                text_size=13,
                expand=True,
            )
            self._field_widgets[field_key] = field
            self.fields_container.controls.append(field)

    def _get_selected_template(self) -> Optional[dict]:
        if not self.selected_template_id:
            return None
        for tpl in TEMPLATES:
            if tpl["id"] == self.selected_template_id:
                return tpl
        return None

    # ---------- Пустое состояние ----------

    def _build_empty_state(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.AUTO_AWESOME_OUTLINED, size=44,
                        color=ft.Colors.with_opacity(
                            0.25, theme.TEXT_SECONDARY,
                        ),
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Выбери шаблон выше",
                        size=14, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=4),
                    ft.Text(
                        "Заполни поля — и ИИ напишет пост по этой структуре",
                        size=11, color=theme.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=30),
            alignment=ft.alignment.center,
            bgcolor=theme.SURFACE,
            border_radius=14,
        )

    # ---------- Генерация ----------

    def _handle_generate(self, e) -> None:
        if self.is_generating or self._stopped:
            return

        tpl = self._get_selected_template()
        if not tpl:
            return

        values = {}
        for key, _label, _hint in tpl["fields"]:
            field = self._field_widgets.get(key)
            values[key] = (field.value or "").strip() if field else ""

        topic = values.get("topic", "")
        if not topic:
            self.page.open(ft.SnackBar(
                content=ft.Text("Заполни хотя бы поле «Тема»"),
                duration=1800,
            ))
            return

        self.is_generating = True
        self.generate_btn.disabled = True
        self.status_text.value = "⏳ Генерирую пост..."
        self.status_text.color = theme.TEXT_SECONDARY
        try:
            self.page.update()
        except Exception:
            pass

        tpl_copy = dict(tpl)
        values_copy = dict(values)

        def _worker():
            prompt = self._build_prompt(tpl_copy, values_copy)
            result = text_provider.ask(
                prompt,
                system="Ты SMM-редактор. Выдаёшь только готовый пост без "
                       "комментариев и пояснений.",
                max_tokens=1200,
            )

            def _done():
                self.is_generating = False
                self.generate_btn.disabled = False

                if not result:
                    self.status_text.value = "❌ Не удалось сгенерировать"
                    self.status_text.color = theme.DANGER
                    try:
                        self.page.update()
                    except Exception:
                        pass
                    return

                self.status_text.value = "✅ Готово"
                self.status_text.color = theme.SUCCESS

                item = {
                    "id": f"{int(datetime.now().timestamp() * 1000)}",
                    "template_id": tpl_copy["id"],
                    "template_title": tpl_copy["title"],
                    "topic": values_copy.get("topic", ""),
                    "text": result,
                    "created_at": datetime.now().isoformat(),
                }
                self.history.insert(0, item)
                self.history = self.history[:50]
                _save_history(self.history)

                self.result_container.content = self._build_result(item)
                try:
                    self.page.update()
                except Exception:
                    pass

            threading.Timer(0, _done).start()

        threading.Thread(target=_worker, daemon=True).start()

    def _build_prompt(self, tpl: dict, values: dict) -> str:
        profile = get_current()

        parts = []
        parts.append(
            "Напиши пост для соцсетей СТРОГО по этой структуре:\n\n"
            f"{tpl['structure']}\n\n"
            "ОФОРМЛЕНИЕ (HTML-теги Telegram):\n"
            "• <b>жирный</b> для заголовка и ключевых слов\n"
            "• <i>курсив</i> для оттенков мысли\n"
            "• <blockquote>цитата</blockquote> для главного вывода\n"
            "• СПИСОК оформляй простыми строками с маркерами ▫️ ✅ 🔹, "
            "КАЖДЫЙ ПУНКТ С НОВОЙ СТРОКИ. НЕ оборачивай список "
            "в <blockquote>.\n"
            "• Заголовок первой строкой, в <b>…</b>, с одним эмодзи\n"
            "• Не больше 5-6 выделений за пост\n"
            "• НЕ используй Markdown (**, __, #, `)\n"
        )

        parts.append("ДАННЫЕ ДЛЯ ПОСТА:")
        if values.get("topic"):
            parts.append(f"• Тема: {values['topic']}")
        if values.get("audience"):
            parts.append(f"• Аудитория: {values['audience']}")

        if profile:
            user_info = []
            if profile.name:
                user_info.append(f"автор — {profile.name}")
            if profile.audience:
                user_info.append(f"обычная аудитория — {profile.audience}")
            if user_info:
                parts.append("• О авторе: " + ", ".join(user_info))

        parts.append(
            "\nВыдай ТОЛЬКО готовый текст поста, без пояснений "
            "и без слов «Вот пост:»."
        )

        return "\n".join(parts)

    # ---------- Результат ----------

    def _build_result(self, item: dict) -> ft.Container:
        text = item.get("text", "")
        tpl_title = item.get("template_title", "")
        topic = item.get("topic", "")
        time_str = _fmt_time(item.get("created_at", ""))

        def copy_text(e):
            try:
                # Копируем С ТЕГАМИ — чтобы вставка в Telegram дала формат
                self.page.set_clipboard(text)
                self.page.open(ft.SnackBar(
                    content=ft.Text("Скопировано (с форматированием)"),
                    duration=1500,
                ))
            except Exception:
                pass

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
            from services import telegram as tg
            ok, err = tg.send_message(
                bot.get("token", ""), bot.get("channel", ""), text,
            )
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

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.DESCRIPTION_ROUNDED, size=14,
                                    color=theme.PRIMARY,
                                ),
                                width=28, height=28, border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.15, theme.PRIMARY),
                                alignment=ft.alignment.center,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    tpl_title, size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.TEXT_PRIMARY,
                                ),
                                margin=ft.margin.only(left=8),
                            ),
                            ft.Container(
                                content=ft.Text(
                                    f"· {topic}", size=11,
                                    color=theme.TEXT_MUTED,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                margin=ft.margin.only(left=6),
                                expand=True,
                            ),
                            ft.Text(time_str, size=10,
                                    color=theme.TEXT_MUTED),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=10),
                    ft.Container(
                        content=rendered,
                        padding=ft.padding.all(12),
                        bgcolor=theme.BG_DARK,
                        border_radius=10,
                    ),
                    ft.Container(height=10),
                    ft.Row(
                        controls=[
                            ft.TextButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.COPY_ROUNDED,
                                                size=14, color=theme.PRIMARY),
                                        ft.Text("Копировать", size=11,
                                                color=theme.PRIMARY),
                                    ],
                                    spacing=4, tight=True,
                                ),
                                on_click=copy_text,
                            ),
                            ft.TextButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.SEND_ROUNDED,
                                                size=14, color=theme.PRIMARY),
                                        ft.Text("Telegram", size=11,
                                                color=theme.PRIMARY),
                                    ],
                                    spacing=4, tight=True,
                                ),
                                on_click=send_to_tg,
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=0, tight=True,
            ),
            padding=ft.padding.all(14),
            bgcolor=theme.SURFACE,
            border=ft.border.all(1, theme.DRAWER_ITEM_BORDER),
            border_radius=14,
        )