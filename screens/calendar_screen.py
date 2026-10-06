"""Календарь постов с напоминаниями.

- Сетка месяца с крупными клетками.
- Клик по клетке → модальное окно: текст + время.
- Напоминание сохраняется в ContentFarm/reminders.json.
- Клетка с напоминанием обводится фиолетовым.
- Фоновый планировщик раз в 20 сек проверяет напоминания
  и показывает SnackBar, когда наступило время.
"""

import calendar as cal_mod
import json
import os
from services import paths
import threading
import time
from datetime import datetime, date, timedelta
from typing import Optional

import flet as ft

from services.user_profile import get_current
from ui import theme
from ui.effects import create_effect


_THIS_FILE = os.path.abspath(__file__)
_SCREENS_DIR = os.path.dirname(_THIS_FILE)
_PROJECT_ROOT = os.path.dirname(_SCREENS_DIR)


def _reminders_path() -> str:
    d = str(paths.data_dir())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "reminders.json")


def load_reminders() -> list:
    p = _reminders_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_reminders(items: list) -> None:
    try:
        with open(_reminders_path(), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print(f"[REMINDERS] save error: {ex}")


class CalendarScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.view_year = date.today().year
        self.view_month = date.today().month
        self._bg_effect = None
        self._grid_container = ft.Container()
        self._current_dialog: Optional[ft.AlertDialog] = None

        self.reminders: list = load_reminders()

        self.month_label = ft.Text(
            "", size=18, weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY, text_align=ft.TextAlign.CENTER,
        )

    # ---------- Построение ----------

    def build(self) -> ft.Stack:
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
                    ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=22,
                            color=theme.PRIMARY),
                    ft.Text("Календарь постов", size=18,
                            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    ft.Text(
                        "Нажми на день — создай напоминание",
                        size=11, color=theme.TEXT_SECONDARY, italic=True,
                    ),
                ],
                spacing=10, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
        )

        nav = ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                        icon_color=theme.TEXT_PRIMARY,
                        on_click=lambda e: self._shift_month(-1),
                    ),
                    ft.Container(content=self.month_label, expand=True,
                                 alignment=ft.alignment.center),
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        icon_color=theme.TEXT_PRIMARY,
                        on_click=lambda e: self._shift_month(1),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
        )

        self._render_grid()

        content = ft.Column(
            controls=[header, nav, self._grid_container],
            spacing=0, expand=True,
        )

        main_layer = ft.Container(
            content=content,
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.6, theme.BG_DARK),
        )


        return ft.Stack(controls=[bg_layer, main_layer], expand=True)
    def stop_effect(self) -> None:
        """Полная остановка — при уходе с экрана."""
        if self._bg_effect is not None:
            try:
                self._bg_effect.stop()
            except Exception:
                pass
            self._bg_effect = None
        if self._current_dialog is not None:
            try:
                self.page.close(self._current_dialog)
            except Exception:
                pass
            self._current_dialog = None

    def _shift_month(self, delta: int) -> None:
        m = self.view_month + delta
        y = self.view_year
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        self.view_month = m
        self.view_year = y
        self._render_grid()
        try:
            self.page.update()
        except Exception:
            pass

    # ---------- Сетка ----------

    def _render_grid(self) -> None:
        months_ru = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
        ]
        self.month_label.value = f"{months_ru[self.view_month - 1]} {self.view_year}"

        first_weekday, days_in_month = cal_mod.monthrange(
            self.view_year, self.view_month
        )
        first_weekday = (first_weekday + 1) % 7   # 0 = понедельник

        days_labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        header_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(
                        d, size=13,
                        color="#FF8A80" if i == 6 else theme.TEXT_SECONDARY,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    expand=True, height=30,
                    alignment=ft.alignment.center,
                )
                for i, d in enumerate(days_labels)
            ],
            spacing=6,
        )

        today = date.today()
        rows = []
        row_cells = []

        for _ in range(first_weekday):
            row_cells.append(self._empty_cell())

        for day in range(1, days_in_month + 1):
            is_today = (
                day == today.day
                and self.view_month == today.month
                and self.view_year == today.year
            )
            # Воскресенье — индекс (first_weekday + day - 1) % 7
            weekday_idx = (first_weekday + day - 1) % 7
            is_sunday = weekday_idx == 6
            row_cells.append(self._day_cell(day, is_today, is_sunday))

            if len(row_cells) == 7:
                rows.append(ft.Row(controls=row_cells, spacing=6))
                row_cells = []

        if row_cells:
            while len(row_cells) < 7:
                row_cells.append(self._empty_cell())
            rows.append(ft.Row(controls=row_cells, spacing=6))

        grid = ft.Column(controls=[header_row] + rows, spacing=6)

        self._grid_container.content = ft.Container(
            content=grid,
            padding=ft.padding.symmetric(horizontal=24, vertical=12),
        )

    def _empty_cell(self) -> ft.Container:
        return ft.Container(expand=True, height=90)

    def _reminders_for_day(self, d: date) -> list:
        key = d.strftime("%Y-%m-%d")
        return [r for r in self.reminders if r.get("date") == key]

    def _day_cell(self, day: int, is_today: bool, is_sunday: bool) -> ft.Container:
        d = date(self.view_year, self.view_month, day)
        day_reminders = self._reminders_for_day(d)
        has_reminders = bool(day_reminders)

        # Цвет дня недели
        if is_sunday:
            text_color = "#FF8A80"
        else:
            text_color = theme.TEXT_PRIMARY

        if is_today:
            text_color = ft.Colors.WHITE

        # Фон и рамка
        if is_today:
            bg = theme.PRIMARY
            border_color = theme.PRIMARY
        elif has_reminders:
            bg = ft.Colors.with_opacity(0.55, theme.SURFACE)
            border_color = theme.PRIMARY
        else:
            bg = ft.Colors.with_opacity(0.45, theme.SURFACE)
            border_color = ft.Colors.with_opacity(0.08, theme.TEXT_SECONDARY)

        cell_controls = [
            ft.Row(
                controls=[
                    ft.Text(
                        str(day),
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=text_color,
                    ),
                    ft.Container(expand=True),
                    ft.Container(
                        width=6, height=6, border_radius=3,
                        bgcolor=theme.PRIMARY if has_reminders else ft.Colors.TRANSPARENT,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ]

        # Подписи напоминаний (максимум 2)
        for r in day_reminders[:2]:
            t = r.get("time", "")
            txt = r.get("text", "")
            cell_controls.append(
                ft.Container(
                    content=ft.Text(
                        f"{t}  {txt}",
                        size=9,
                        color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE) if is_today else theme.TEXT_SECONDARY,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    padding=ft.padding.only(top=2),
                )
            )
        if len(day_reminders) > 2:
            cell_controls.append(
                ft.Text(f"+{len(day_reminders) - 2}", size=9,
                        color=theme.TEXT_SECONDARY)
            )

        return ft.Container(
            content=ft.Column(
                controls=cell_controls,
                spacing=0, tight=True,
            ),
            expand=True, height=90,
            bgcolor=bg,
            border=ft.border.all(2 if has_reminders else 1, border_color),
            border_radius=10,
            padding=ft.padding.all(6),
            on_click=lambda e, dd=d: self._open_day_editor(dd),
            ink=True,
        )

    # ---------- Модальное окно настройки напоминания ----------

    def _open_day_editor(self, d: date) -> None:
        self._close_dialog()

        # Поле текста
        text_field = ft.TextField(
            hint_text="Например: пост про кота",
            multiline=True, min_lines=2, max_lines=4,
            filled=True, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=12, border_color=theme.SURFACE, text_size=14,
            autofocus=True,
        )

        # Часы и минуты
        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]
        hour_dd = ft.Dropdown(
            value="12", options=[ft.dropdown.Option(h) for h in hours],
            width=90, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=10, text_size=14,
        )
        minute_dd = ft.Dropdown(
            value="00", options=[ft.dropdown.Option(m) for m in minutes],
            width=90, fill_color=theme.SURFACE, color=theme.TEXT_PRIMARY,
            border_radius=10, text_size=14,
        )

        date_label = ft.Text(
            f"{d.day}.{d.month:02d}.{d.year}",
            size=15, weight=ft.FontWeight.BOLD, color=theme.PRIMARY,
        )

        # Список существующих напоминаний этого дня
        existing = self._reminders_for_day(d)
        existing_block = ft.Column(spacing=4)
        if existing:
            existing_block.controls.append(
                ft.Text("Уже есть напоминания:", size=11,
                        color=theme.TEXT_SECONDARY)
            )
            for r in existing:
                existing_block.controls.append(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=14,
                                    color=theme.PRIMARY),
                            ft.Text(f"{r.get('time', '')} — {r.get('text', '')}",
                                    size=12, color=theme.TEXT_PRIMARY,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_size=16,
                                icon_color="#FF5252",
                                tooltip="Удалить",
                                on_click=lambda e, rr=r: self._delete_reminder(rr),
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

        dialog = ft.AlertDialog(modal=True)

        def save(ev):
            txt = (text_field.value or "").strip()
            if not txt:
                self.page.open(ft.SnackBar(
                    content=ft.Text("Введи текст напоминания"),
                    duration=1500,
                ))
                return
            hh = hour_dd.value or "12"
            mm = minute_dd.value or "00"
            item = {
                "date": d.strftime("%Y-%m-%d"),
                "time": f"{hh}:{mm}",
                "text": txt,
                "notified": False,
            }
            self.reminders.append(item)
            save_reminders(self.reminders)
            self._close_dialog()
            self._render_grid()
            try:
                self.page.update()
            except Exception:
                pass
            self.page.open(ft.SnackBar(
                content=ft.Text(f"Напоминание на {hh}:{mm} добавлено"),
                duration=1500,
            ))

        def close(ev):
            self._close_dialog()

        dialog.title = ft.Text("Напоминание")
        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=18,
                                    color=theme.PRIMARY),
                            date_label,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=12),
                    ft.Text("Текст:", size=12,
                            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Container(height=6),
                    text_field,
                    ft.Container(height=14),
                    ft.Text("Время:", size=12,
                            weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                    ft.Container(height=6),
                    ft.Row(
                        controls=[hour_dd, ft.Text(":", size=18,
                                                    color=theme.TEXT_PRIMARY),
                                  minute_dd],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=14),
                    existing_block,
                ],
                spacing=0, tight=True, scroll=ft.ScrollMode.AUTO,
            ),
            width=460, height=460,
        )
        dialog.actions = [
            ft.TextButton("Отмена", on_click=close,
                          style=ft.ButtonStyle(color=theme.TEXT_SECONDARY)),
            ft.ElevatedButton("Сохранить", bgcolor=theme.PRIMARY,
                              color=ft.Colors.WHITE, on_click=save),
        ]
        dialog.actions_alignment = ft.MainAxisAlignment.END

        self._current_dialog = dialog
        self.page.open(dialog)
        try:
            self.page.update()
        except Exception:
            pass

    def _delete_reminder(self, reminder: dict) -> None:
        self.reminders = [r for r in self.reminders if r is not reminder]
        save_reminders(self.reminders)
        self._close_dialog()
        self._render_grid()
        try:
            self.page.update()
        except Exception:
            pass

    def _close_dialog(self) -> None:
        if self._current_dialog is not None:
            try:
                self.page.close(self._current_dialog)
            except Exception:
                pass
            self._current_dialog = None
            try:
                self.page.update()
            except Exception:
                pass


# ---------- Планировщик напоминаний ----------

class ReminderScheduler:
    """Раз в 20 секунд проверяет напоминания и показывает SnackBar."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.alive = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.alive:
            return
        self.alive = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.alive = False

    def _loop(self) -> None:
        while self.alive:
            time.sleep(20)
            if not self.alive:
                break
            try:
                self._check()
            except Exception as ex:
                print(f"[SCHEDULER] error: {ex}")

    def _check(self) -> None:
        items = load_reminders()
        if not items:
            return
        now = datetime.now()
        changed = False
        for r in items:
            if r.get("notified"):
                continue
            try:
                dt = datetime.strptime(
                    f"{r.get('date', '')} {r.get('time', '')}",
                    "%Y-%m-%d %H:%M",
                )
            except Exception:
                continue
            # Показываем, если время наступило, но не прошло больше 1 часа
            if dt <= now <= dt + timedelta(hours=1):
                text = r.get("text", "")
                t = r.get("time", "")
                self._safe_snackbar(f"⏰ {t} — {text}")
                r["notified"] = True
                changed = True
        if changed:
            save_reminders(items)

    def _safe_snackbar(self, text: str) -> None:
        try:
            self.page.open(ft.SnackBar(
                content=ft.Text(text, size=14),
                duration=6000,
                bgcolor=theme.PRIMARY,
            ))
            try:
                self.page.update()
            except Exception:
                pass
        except Exception as ex:
            print(f"[SCHEDULER] snackbar error: {ex}")