"""Пузырь сообщения с адаптивной шириной + визуальный рендер Telegram-HTML.

В чате посты ИИ показываются КРАСИВО:
  • <b>жирный</b> → жирный текст
  • <i>курсив</i> → курсив
  • <u>подчёркнутый</u> → подчёркнутый
  • <s>зачёркнутый</s> → зачёркнутый
  • <code>моноширинный</code> → monospace
  • <tg-spoiler>скрытый</tg-spoiler> → серый текст
  • <blockquote>цитата</blockquote> → прозрачный синий блок
  • <tg-emoji emoji-id="...">эмодзи</tg-emoji> → просто эмодзи

В Telegram уходит ОРИГИНАЛЬНАЯ строка с тегами — она хранится в
message.text / message.variants, рендер только визуальный.

Публичная функция render_telegram_html() используется также
в screens/templates_screen.py и screens/ideas_screen.py.
"""

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
import re

import flet as ft

from services.models import Message
from ui import theme


MAX_BUBBLE_WIDTH = 380
MIN_BUBBLE_WIDTH = 240

_dynamic_width = MAX_BUBBLE_WIDTH


def set_dynamic_width(page) -> None:
    global _dynamic_width
    try:
        w = int(page.width or 800)
        if w < 700:
            _dynamic_width = max(MIN_BUBBLE_WIDTH, w - 60)
        else:
            _dynamic_width = MAX_BUBBLE_WIDTH
    except Exception:
        _dynamic_width = MAX_BUBBLE_WIDTH


def get_dynamic_width() -> int:
    return _dynamic_width


def calc_width_for_page(page) -> int:
    try:
        w = int(page.width or 800)
        if w < 700:
            return max(MIN_BUBBLE_WIDTH, w - 60)
        return MAX_BUBBLE_WIDTH
    except Exception:
        return MAX_BUBBLE_WIDTH


BUBBLE_PADDING_H = 12
BUBBLE_PADDING_V = 10
IMAGE_HEIGHT = 220

GAP_PHOTO_TO_HEADER = -2
GAP_HEADER_TO_TEXT = 14
GAP_TOP_NO_PHOTO = 2
GAP_TEXT_TO_DIVIDER = 20
GAP_DIVIDER_TO_BUTTONS = 6


def _fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return f"{dt.hour}:{dt.minute:02d}"
    except Exception:
        return ""


def _is_error_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith("❌"):
        return True
    first_line = t.split("\n", 1)[0].lower()
    markers = ["не удалось", "ошибка генерации", "ошибка:"]
    return any(m in first_line for m in markers)


def _split_variant(variant: str) -> tuple[str, str]:
    if not variant:
        return ("", "")
    m = re.match(r"^(Вариант\s*\d+\s*:)\s*(.*)", variant, re.DOTALL)
    if m:
        return (m.group(1), m.group(2))
    return ("", variant)


# ===========================================================================
# ПАРСЕР TELEGRAM-HTML → FLET
# ===========================================================================

_TG_EMOJI_RE = re.compile(
    r'<tg-emoji[^>]*>(.*?)</tg-emoji>',
    re.DOTALL | re.IGNORECASE,
)


def _strip_tg_emoji(text: str) -> str:
    return _TG_EMOJI_RE.sub(r"\1", text or "")


def _unescape_html(text: str) -> str:
    return (
        text.replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
    )


def _split_by_blockquotes(text: str):
    """Возвращает [(kind, content)] где kind ∈ {"plain", "quote"}."""
    text = _strip_tg_emoji(text or "")
    bq_re = re.compile(
        r"<blockquote(?:\s[^>]*)?>(.*?)</blockquote>",
        re.DOTALL | re.IGNORECASE,
    )
    parts = []
    last_end = 0
    for m in bq_re.finditer(text):
        if m.start() > last_end:
            parts.append(("plain", text[last_end:m.start()]))
        parts.append(("quote", m.group(1)))
        last_end = m.end()
    if last_end < len(text):
        parts.append(("plain", text[last_end:]))
    if not parts:
        parts = [("plain", text)]
    return parts


def _parse_inline_to_spans(text: str) -> list:
    """Разбирает инлайн-теги в список spans.
    Каждый span: {"text", "b", "i", "u", "s", "code", "spoiler"}.
    """
    tag_re = re.compile(
        r"<(/?)(b|strong|i|em|u|s|strike|code|pre|tg-spoiler)>",
        re.IGNORECASE,
    )
    spans = []
    flags = {"b": 0, "i": 0, "u": 0, "s": 0, "code": 0, "spoiler": 0}
    pos = 0
    for m in tag_re.finditer(text):
        if m.start() > pos:
            chunk = _unescape_html(text[pos:m.start()])
            if chunk:
                spans.append({
                    "text": chunk,
                    "b": flags["b"] > 0,
                    "i": flags["i"] > 0,
                    "u": flags["u"] > 0,
                    "s": flags["s"] > 0,
                    "code": flags["code"] > 0,
                    "spoiler": flags["spoiler"] > 0,
                })
        closing = m.group(1) == "/"
        tag = m.group(2).lower()
        if tag == "strong":
            tag = "b"
        elif tag == "em":
            tag = "i"
        elif tag == "strike":
            tag = "s"
        elif tag == "pre":
            tag = "code"
        if tag in flags:
            flags[tag] += -1 if closing else 1
            if flags[tag] < 0:
                flags[tag] = 0
        pos = m.end()
    if pos < len(text):
        chunk = _unescape_html(text[pos:])
        if chunk:
            spans.append({
                "text": chunk,
                "b": flags["b"] > 0,
                "i": flags["i"] > 0,
                "u": flags["u"] > 0,
                "s": flags["s"] > 0,
                "code": flags["code"] > 0,
                "spoiler": flags["spoiler"] > 0,
            })

    merged = []
    for sp in spans:
        if not sp["text"]:
            continue
        if merged and all(
            merged[-1][k] == sp[k]
            for k in ("b", "i", "u", "s", "code", "spoiler")
        ):
            merged[-1]["text"] += sp["text"]
        else:
            merged.append(sp)
    return merged


def _spans_to_text(spans: list, base_size: int = 14) -> ft.Text:
    """Собирает ft.Text с ft.TextSpan из списка spans."""
    if not spans:
        return ft.Text(" ", size=base_size)

    text_spans = []
    for sp in spans:
        txt = sp["text"]
        if not txt:
            continue

        weight = ft.FontWeight.BOLD if sp["b"] else ft.FontWeight.NORMAL
        italic = bool(sp["i"])

        decoration = None
        if sp["u"] and sp["s"]:
            decoration = ft.TextDecoration.UNDERLINE
        elif sp["u"]:
            decoration = ft.TextDecoration.UNDERLINE
        elif sp["s"]:
            decoration = ft.TextDecoration.LINE_THROUGH

        color = theme.TEXT_PRIMARY
        if sp["spoiler"]:
            color = theme.TEXT_MUTED

        style = ft.TextStyle(
            size=base_size if not sp["code"] else base_size - 1,
            weight=weight,
            italic=italic,
            decoration=decoration,
            color=color,
            font_family="monospace" if sp["code"] else None,
        )

        text_spans.append(ft.TextSpan(text=txt, style=style))

    if not text_spans:
        text_spans = [ft.TextSpan(text=" ",
                                   style=ft.TextStyle(size=base_size))]

    return ft.Text(
        spans=text_spans,
        selectable=True,
        no_wrap=False,
    )


def render_telegram_html(raw: str, base_size: int = 14) -> ft.Control:
    """ПУБЛИЧНАЯ функция: рендерит Telegram-HTML в Flet-контрол.

    • Инлайн теги → ft.TextSpan (жирный, курсив, подчёркнутый и т.д.)
    • <blockquote> → прозрачный синий блок
    • \\n\\n → пустой отступ
    • \\n → перенос строки

    Используется в: message_bubble, templates_screen, ideas_screen.
    """
    parts = _split_by_blockquotes(raw)

    controls = []
    for kind, content in parts:
        if kind == "quote":
            inner_spans = _parse_inline_to_spans(content)
            inner_text = _spans_to_text(inner_spans, base_size)
            controls.append(
                ft.Container(
                    content=inner_text,
                    padding=ft.padding.symmetric(
                        horizontal=12, vertical=8,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.15, "#2196F3"),
                    border_radius=8,
                    margin=ft.margin.symmetric(vertical=4),
                )
            )
        else:
            cleaned = content.strip("\n")
            if not cleaned.strip():
                continue

            lines = cleaned.split("\n")
            for line in lines:
                if not line.strip():
                    controls.append(ft.Container(height=6))
                    continue
                line_spans = _parse_inline_to_spans(line)
                controls.append(_spans_to_text(line_spans, base_size))

    if not controls:
        controls = [ft.Text(" ", size=base_size)]

    return ft.Column(controls=controls, spacing=2, tight=True)


def _strip_all_tags(text: str) -> str:
    """Убирает все Telegram-HTML-теги, оставляя чистый текст."""
    if not text:
        return ""
    t = _strip_tg_emoji(text)
    t = re.sub(
        r"</?(?:b|strong|i|em|u|s|strike|code|pre|blockquote|tg-spoiler)"
        r"(?:\s[^>]*)?>",
        "",
        t,
        flags=re.IGNORECASE,
    )
    return _unescape_html(t)


# ---------- Просмотр фото ----------

def _open_fullscreen_image(e: ft.ControlEvent, path: Path) -> None:
    page = e.page

    try:
        screen_w = page.width or 800
        screen_h = page.height or 700
    except Exception:
        screen_w, screen_h = 800, 700

    target_w = 560
    target_h = 440

    max_w = int(screen_w * 0.8)
    max_h = int(screen_h * 0.8)
    if target_w > max_w:
        ratio = max_w / target_w
        target_w = max_w
        target_h = int(target_h * ratio)
    if target_h > max_h:
        ratio = max_h / target_h
        target_h = max_h
        target_w = int(target_w * ratio)

    overlay_ref = {}

    overlay = ft.Container(
        content=ft.Container(
            content=ft.Image(
                src=str(path.resolve()),
                width=target_w,
                height=target_h,
                fit=ft.ImageFit.CONTAIN,
            ),
            width=target_w,
            height=target_h,
            alignment=ft.alignment.center,
        ),
        bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.BLACK),
        alignment=ft.alignment.center,
        expand=True,
        on_click=lambda ev: _close_overlay(page, overlay_ref),
    )

    overlay_ref["widget"] = overlay

    try:
        page.overlay.append(overlay)
        page.update()
    except Exception as ex:
        print(f"Overlay error: {ex}")


def _close_overlay(page: ft.Page, overlay_ref: dict) -> None:
    widget = overlay_ref.get("widget")
    if widget is not None:
        try:
            if widget in page.overlay:
                page.overlay.remove(widget)
            page.update()
        except Exception:
            pass


# ---------- Меню фото ----------

def _open_image_menu(e: ft.ControlEvent, path: Path) -> None:
    page = e.page

    def close_dialog(ev):
        page.close(dialog)

    def action_edit(ev):
        page.close(dialog)
        page.open(ft.SnackBar(
            content=ft.Text("Редактирование фото — в разработке"),
            duration=1500,
        ))

    def action_download(ev):
        page.close(dialog)
        page.open(ft.SnackBar(
            content=ft.Text(f"Скачать: {path.name}"),
            duration=1500,
        ))

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Действия с фото"),
        content=ft.Column(
            controls=[
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.EDIT_ROUNDED, size=20),
                            ft.Text("Отредактировать", size=14),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    on_click=action_edit,
                ),
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=20),
                            ft.Text("Скачать", size=14),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    on_click=action_download,
                ),
            ],
            spacing=4,
            tight=True,
        ),
        actions=[
            ft.TextButton(
                "Закрыть",
                on_click=close_dialog,
                style=ft.ButtonStyle(color=theme.TEXT_SECONDARY),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.open(dialog)


# ---------- Копирование текущего варианта ----------

def _copy_current(e: ft.ControlEvent, variants: list, idx_state: dict) -> None:
    try:
        variant = variants[idx_state["i"]]
        _head, body = _split_variant(variant)
        raw = body if body.strip() else variant
        # Копируем С ТЕГАМИ — чтобы вставка в Telegram дала форматирование
        e.page.set_clipboard(raw)
        e.page.open(ft.SnackBar(
            content=ft.Text("Скопировано (с форматированием)"),
            duration=1500,
        ))
    except Exception as ex:
        print(f"Ошибка копирования: {ex}")


# ---------- Отправка текущего варианта в Telegram ----------

def _send_current_to_tg(
    e: ft.ControlEvent,
    variants: list,
    idx_state: dict,
    message: Message,
    on_send_to_tg: Optional[Callable[[str, str], None]],
) -> None:
    """Кнопка «В Telegram» в шапке карточки ИИ."""
    try:
        variant = variants[idx_state["i"]]
        _head, body = _split_variant(variant)
        text = body if body.strip() else variant
    except Exception:
        text = ""

    if on_send_to_tg:
        try:
            on_send_to_tg(message.timestamp, text)
            return
        except Exception as ex:
            print(f"[TG] send_to_tg error: {ex}")

    try:
        e.page.set_clipboard(text)
        e.page.open(ft.SnackBar(
            content=ft.Text("Пост скопирован"),
            duration=2000,
        ))
    except Exception:
        pass


def create_thinking_bubble(text_state: dict) -> ft.Container:
    thinking_text = ft.Text(
        f"{text_state['prefix']}{text_state['dots']}",
        size=14,
        color=theme.TEXT_SECONDARY,
        italic=True,
        no_wrap=False,
    )

    inner = ft.Container(
        content=thinking_text,
        bgcolor=theme.AI_BUBBLE,
        border_radius=theme.RADIUS,
        padding=ft.padding.symmetric(horizontal=14, vertical=12),
    )

    outer = ft.Container(
        content=inner,
        alignment=ft.alignment.center_left,
        margin=ft.margin.only(right=20, top=4, bottom=4),
    )

    text_state["widget"] = thinking_text
    return outer


def create_message_bubble(
    message: Message,
    on_edit: Optional[Callable[[str], None]] = None,
    on_change_format: Optional[Callable[[str], None]] = None,
    on_next: Optional[Callable[[str, str], None]] = None,
    on_cancel: Optional[Callable[[str], None]] = None,
    on_send_to_tg: Optional[Callable[[str, str], None]] = None,
) -> ft.Container:
    is_user = message.role == "user"

    if is_user:
        return _build_user_bubble(message)

    text = (message.text or "").strip()

    if _is_error_text(text):
        return _build_error_bubble(message)

    attachments_block = _build_attachments_block(message)
    variants = message.variants if message.variants else [message.text]
    card = _build_ai_card(
        variants, attachments_block,
        message, on_edit, on_change_format, on_next, on_cancel,
        on_send_to_tg,
    )

    row = ft.Row(
        controls=[card],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    return ft.Container(
        content=row,
        margin=ft.margin.only(right=20, top=4, bottom=4),
    )


# ---------- Error-пузырь ----------

def _build_error_bubble(message: Message) -> ft.Container:
    text = (message.text or "").strip()
    time_str = _fmt_time(getattr(message, "timestamp", ""))

    body = ft.Row(
        controls=[
            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=18, color="#FF5252"),
            ft.Container(
                content=ft.Text(
                    text,
                    size=13,
                    color=theme.TEXT_PRIMARY,
                    selectable=True,
                    no_wrap=False,
                ),
                expand=True,
                margin=ft.margin.only(left=10),
            ),
        ],
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    time_row = ft.Row(
        controls=[
            ft.Text(
                time_str, size=10,
                color=theme.TEXT_SECONDARY, no_wrap=True,
            ),
        ],
        alignment=ft.MainAxisAlignment.END,
    ) if time_str else ft.Container(height=0)

    bubble = ft.Container(
        content=ft.Column(
            controls=[
                body,
                ft.Container(content=time_row, padding=ft.padding.only(top=8)),
            ],
            spacing=0,
            tight=True,
        ),
        bgcolor=ft.Colors.with_opacity(0.15, "#FF5252"),
        border=ft.border.all(1, ft.Colors.with_opacity(0.6, "#FF5252")),
        border_radius=theme.RADIUS,
        padding=ft.padding.symmetric(
            horizontal=BUBBLE_PADDING_H + 4,
            vertical=BUBBLE_PADDING_V + 2,
        ),
        width=_dynamic_width,
    )

    row = ft.Row(
        controls=[bubble],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    return ft.Container(
        content=row,
        margin=ft.margin.only(right=20, top=4, bottom=4),
    )


# ---------- Пузырь пользователя ----------

def _build_user_bubble(message: Message) -> ft.Container:
    attachments = getattr(message, "attachments", []) or []
    images = [a for a in attachments
              if Path(a).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}]

    user_bubble_width = _dynamic_width
    time_str = _fmt_time(getattr(message, "timestamp", ""))

    inner_controls: list[ft.Control] = []

    if images:
        for img_path in images:
            p = Path(img_path)
            inner_controls.append(_build_user_image(p, user_bubble_width))

    has_text = bool(message.text.strip())

    if has_text:
        text_widget = ft.Text(
            message.text,
            color=ft.Colors.WHITE,
            size=14,
            selectable=True,
            no_wrap=False,
        )
    else:
        text_widget = ft.Text("", size=1)

    time_widget = ft.Text(
        time_str,
        size=10,
        color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
        no_wrap=True,
    ) if time_str else ft.Text("", size=1)

    text_block = ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(content=text_widget, expand=True),
                ft.Container(
                    content=time_widget,
                    padding=ft.padding.only(left=8, top=6),
                    alignment=ft.alignment.bottom_right,
                ),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.END,
        ),
        padding=ft.padding.only(left=12, right=12, top=6, bottom=6),
        width=user_bubble_width,
    )
    inner_controls.append(text_block)

    if not inner_controls:
        inner_controls = [ft.Text("", size=1)]

    bubble = ft.Container(
        content=ft.Column(
            controls=inner_controls,
            spacing=0,
            tight=True,
        ),
        bgcolor=theme.USER_BUBBLE,
        border_radius=theme.RADIUS,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        padding=0,
        width=user_bubble_width,
    )

    row = ft.Row(
        controls=[bubble],
        alignment=ft.MainAxisAlignment.END,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    return ft.Container(
        content=row,
        margin=ft.margin.only(left=20, top=4, bottom=4),
    )


def _build_user_image(path: Path, bubble_width: int) -> ft.Container:
    image = ft.Image(
        src=str(path.resolve()),
        width=bubble_width,
        height=IMAGE_HEIGHT,
        fit=ft.ImageFit.CONTAIN,
    )

    return ft.Container(
        content=image,
        width=bubble_width,
        height=IMAGE_HEIGHT,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        on_click=lambda e, p=path: _open_fullscreen_image(e, p),
    )


# ---------- Вложения ИИ ----------

def _build_attachments_block(message: Message) -> Optional[ft.Control]:
    attachments = getattr(message, "attachments", []) or []
    if not attachments:
        return None

    images_col: list[ft.Control] = []
    files_col: list[ft.Control] = []

    for path in attachments:
        p = Path(path)
        is_image = p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}

        if is_image:
            images_col.append(_build_ai_image(p))
        else:
            files_col.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, size=16,
                                    color=theme.TEXT_SECONDARY),
                            ft.Text(
                                p.name,
                                size=12,
                                color=theme.TEXT_SECONDARY,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=6,
                        tight=True,
                    ),
                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                    border_radius=8,
                    bgcolor=theme.SURFACE,
                )
            )

    blocks: list[ft.Control] = []
    if images_col:
        blocks.append(ft.Column(controls=images_col, spacing=0, tight=True))
    if files_col:
        blocks.append(ft.Column(controls=files_col, spacing=4, tight=True))
    if not blocks:
        return None
    return ft.Column(controls=blocks, spacing=0, tight=True)


def _build_ai_image(path: Path) -> ft.Control:
    inner_width = _dynamic_width - 2 * BUBBLE_PADDING_H
    if inner_width < 100:
        inner_width = max(100, _dynamic_width)

    image = ft.Image(
        src=str(path.resolve()),
        width=inner_width,
        height=IMAGE_HEIGHT,
        fit=ft.ImageFit.CONTAIN,
    )

    clickable = ft.Container(
        content=image,
        width=inner_width,
        height=IMAGE_HEIGHT,
        on_click=lambda e, p=path: _open_fullscreen_image(e, p),
    )

    return ft.Container(
        content=clickable,
        margin=ft.margin.only(
            top=-BUBBLE_PADDING_V - 2,
            bottom=GAP_PHOTO_TO_HEADER - BUBBLE_PADDING_V,
        ),
    )


# ---------- Карточка ИИ ----------

def _build_ai_card(
    variants: list,
    attachments_block: Optional[ft.Control],
    message: Message,
    on_edit: Optional[Callable[[str], None]],
    on_change_format: Optional[Callable[[str], None]],
    on_next: Optional[Callable[[str, str], None]],
    on_cancel: Optional[Callable[[str], None]],
    on_send_to_tg: Optional[Callable[[str, str], None]] = None,
) -> ft.Container:
    total = len(variants)
    idx_state = {"i": 0}
    has_photo = attachments_block is not None
    inner_width = _dynamic_width - 2 * BUBBLE_PADDING_H

    first_image_path: Optional[Path] = None
    if has_photo:
        for a in (getattr(message, "attachments", []) or []):
            p = Path(a)
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                first_image_path = p
                break

    head0, body0 = _split_variant(variants[0])

    variant_header = ft.Text(
        head0,
        size=13,
        color=theme.TEXT_SECONDARY,
        selectable=True,
        no_wrap=False,
        weight=ft.FontWeight.BOLD,
        visible=bool(head0),
    )

    # Визуальный рендер — теги превращаются в жирный/курсив/цитату
    variant_text_holder = {"widget": render_telegram_html(body0, base_size=14)}

    header_top_pad = GAP_TOP_NO_PHOTO if not has_photo else 0

    header_wrapper = ft.Container(
        content=variant_header,
        width=inner_width,
        padding=ft.padding.only(left=4, right=4, top=header_top_pad, bottom=0),
    )
    text_wrapper = ft.Container(
        content=variant_text_holder["widget"],
        width=inner_width,
        padding=ft.padding.only(left=4, right=4, top=GAP_HEADER_TO_TEXT, bottom=2),
    )

    counter_label = ft.Text(
        f"1 / {total}",
        size=12,
        color=theme.TEXT_SECONDARY,
    )

    def show_index(new_idx: int) -> None:
        idx_state["i"] = max(0, min(total - 1, new_idx))
        head, body = _split_variant(variants[idx_state["i"]])
        variant_header.value = head
        variant_header.visible = bool(head)
        variant_text_holder["widget"] = render_telegram_html(body, base_size=14)
        text_wrapper.content = variant_text_holder["widget"]
        counter_label.value = f"{idx_state['i'] + 1} / {total}"
        try:
            variant_header.update()
            text_wrapper.update()
            counter_label.update()
        except Exception:
            pass
        try:
            variant_header.page.update()
        except Exception:
            pass

    left_arrow = ft.IconButton(
        icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
        icon_color=theme.TEXT_SECONDARY,
        icon_size=18,
        tooltip="Предыдущий вариант",
        on_click=lambda e: show_index(idx_state["i"] - 1),
    )
    right_arrow = ft.IconButton(
        icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
        icon_color=theme.TEXT_SECONDARY,
        icon_size=18,
        tooltip="Следующий вариант",
        on_click=lambda e: show_index(idx_state["i"] + 1),
    )

    menu_btn = ft.Container(
        content=ft.Icon(ft.Icons.MORE_VERT_ROUNDED, size=18,
                        color=theme.TEXT_SECONDARY),
        padding=ft.padding.all(6),
        border_radius=8,
        bgcolor=theme.SURFACE,
        on_click=lambda e: _open_image_menu(e, first_image_path) if first_image_path else None,
        ink=True,
        tooltip="Действия с фото",
        visible=has_photo,
    )

    copy_btn = ft.Container(
        content=ft.Icon(ft.Icons.COPY_ROUNDED, size=18,
                        color=theme.TEXT_SECONDARY),
        padding=ft.padding.all(6),
        border_radius=8,
        bgcolor=theme.SURFACE,
        on_click=lambda e: _copy_current(e, variants, idx_state),
        ink=True,
        tooltip="Скопировать (с форматированием)",
    )

    tg_btn = ft.Container(
        content=ft.Icon(ft.Icons.SEND_ROUNDED, size=18,
                        color=theme.TEXT_SECONDARY),
        padding=ft.padding.all(6),
        border_radius=8,
        bgcolor=theme.SURFACE,
        on_click=lambda e: _send_current_to_tg(
            e, variants, idx_state, message, on_send_to_tg,
        ),
        ink=True,
        tooltip="Отправить в Telegram",
    )

    header = ft.Stack(
        controls=[
            ft.Container(
                content=ft.Row(
                    controls=[left_arrow, counter_label, right_arrow],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=2,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
                alignment=ft.alignment.center,
            ),
            ft.Container(content=menu_btn, alignment=ft.alignment.center_left),
            ft.Container(
                content=ft.Row(
                    controls=[tg_btn, copy_btn],
                    spacing=6, tight=True,
                ),
                alignment=ft.alignment.center_right,
            ),
        ],
        height=32,
        width=inner_width,
    )

    drag_start_x = {"x": None}

    def on_pan_start(e: ft.DragStartEvent):
        drag_start_x["x"] = e.local_x

    def on_pan_end(e: ft.DragEndEvent):
        start = drag_start_x["x"]
        if start is None:
            return
        dx = e.local_x - start
        if dx > 50:
            show_index(idx_state["i"] - 1)
        elif dx < -50:
            show_index(idx_state["i"] + 1)
        drag_start_x["x"] = None

    text_block = ft.Column(
        controls=[header_wrapper, text_wrapper],
        spacing=0,
        tight=True,
    )

    swipe_area = ft.GestureDetector(
        content=text_block,
        on_pan_start=on_pan_start,
        on_pan_end=on_pan_end,
        drag_interval=20,
        width=inner_width,
    )

    msg_id = message.timestamp
    selected = {"value": None}

    edit_circle = ft.Container(
        width=20, height=20, border_radius=10,
        bgcolor=ft.Colors.TRANSPARENT,
        border=ft.border.all(2, theme.TEXT_SECONDARY),
    )
    format_circle = ft.Container(
        width=20, height=20, border_radius=10,
        bgcolor=ft.Colors.TRANSPARENT,
        border=ft.border.all(2, theme.TEXT_SECONDARY),
    )

    edit_btn = ft.Container(
        content=ft.Row(
            controls=[
                edit_circle,
                ft.Icon(ft.Icons.EDIT_ROUNDED, size=17, color=theme.TEXT_SECONDARY),
                ft.Text("Отредактировать", size=15, color=theme.TEXT_SECONDARY),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=14, vertical=12),
        border_radius=10,
        bgcolor=theme.SURFACE,
        border=ft.border.all(2, ft.Colors.TRANSPARENT),
        on_click=lambda e: select("edit"),
        ink=True,
        expand=True,
    )

    format_btn = ft.Container(
        content=ft.Row(
            controls=[
                format_circle,
                ft.Icon(ft.Icons.AUTORENEW_ROUNDED, size=17, color=theme.TEXT_SECONDARY),
                ft.Text("Изменить формат", size=15, color=theme.TEXT_SECONDARY),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=14, vertical=12),
        border_radius=10,
        bgcolor=theme.SURFACE,
        border=ft.border.all(2, ft.Colors.TRANSPARENT),
        on_click=lambda e: select("format"),
        ink=True,
        expand=True,
    )

    next_button = ft.Container(
        content=ft.Row(
            controls=[
                ft.Text("Далее", size=15, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY),
                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=17,
                        color=theme.TEXT_PRIMARY),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=14, vertical=12),
        border_radius=10,
        bgcolor=theme.PRIMARY,
        on_click=lambda e: handle_next(e),
        ink=True,
        visible=False,
        expand=True,
    )

    cancel_button = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.CLOSE_ROUNDED, size=17, color=theme.TEXT_PRIMARY),
                ft.Text("Отмена", size=15, weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_PRIMARY),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=14, vertical=12),
        border_radius=10,
        bgcolor=theme.SURFACE,
        on_click=lambda e: handle_cancel(e),
        ink=True,
        visible=False,
        expand=True,
    )

    def _reset_button(btn, circle):
        circle.bgcolor = ft.Colors.TRANSPARENT
        circle.border = ft.border.all(2, theme.TEXT_SECONDARY)
        btn.border = ft.border.all(2, ft.Colors.TRANSPARENT)
        btn.content.controls[1].color = theme.TEXT_SECONDARY
        btn.content.controls[2].color = theme.TEXT_SECONDARY

    def _activate_button(btn, circle):
        circle.bgcolor = ft.Colors.BLUE
        circle.border = ft.border.all(2, ft.Colors.BLUE)
        btn.border = ft.border.all(2, ft.Colors.BLUE)
        btn.content.controls[1].color = theme.TEXT_PRIMARY
        btn.content.controls[2].color = theme.TEXT_PRIMARY

    def select(kind: str) -> None:
        if selected["value"] == kind:
            selected["value"] = None
            _reset_button(edit_btn, edit_circle)
            _reset_button(format_btn, format_circle)
            next_button.visible = False
        else:
            selected["value"] = kind
            _reset_button(edit_btn, edit_circle)
            _reset_button(format_btn, format_circle)
            if kind == "edit":
                _activate_button(edit_btn, edit_circle)
            else:
                _activate_button(format_btn, format_circle)
            next_button.visible = True
        try:
            edit_btn.update()
            format_btn.update()
            next_button.update()
        except Exception:
            pass

    def handle_next(e) -> None:
        kind = selected["value"]
        if not kind:
            return
        if kind == "edit" and on_edit:
            on_edit(msg_id)
        elif kind == "format" and on_change_format:
            on_change_format(msg_id)
        if on_next:
            on_next(msg_id, kind)
        edit_btn.visible = False
        format_btn.visible = False
        next_button.visible = False
        cancel_button.visible = True
        try:
            edit_btn.update()
            format_btn.update()
            next_button.update()
            cancel_button.update()
        except Exception:
            pass

    def handle_cancel(e) -> None:
        selected["value"] = None
        _reset_button(edit_btn, edit_circle)
        _reset_button(format_btn, format_circle)
        edit_btn.visible = True
        format_btn.visible = True
        next_button.visible = False
        cancel_button.visible = False
        try:
            edit_btn.update()
            format_btn.update()
            next_button.update()
            cancel_button.update()
        except Exception:
            pass
        if on_cancel:
            on_cancel(msg_id)

    actions_col = ft.Column(
        controls=[edit_btn, format_btn, next_button, cancel_button],
        spacing=6,
        tight=True,
        width=inner_width,
    )

    time_str = _fmt_time(getattr(message, "timestamp", ""))
    time_row = ft.Row(
        controls=[
            ft.Text(
                time_str,
                size=10,
                color=theme.TEXT_SECONDARY,
                no_wrap=True,
            ),
        ],
        alignment=ft.MainAxisAlignment.END,
    ) if time_str else ft.Container(height=0)

    content_controls: list[ft.Control] = []

    content_controls.append(header)
    if has_photo:
        content_controls.append(attachments_block)
    content_controls.append(swipe_area)
    content_controls.append(ft.Container(height=GAP_TEXT_TO_DIVIDER))
    content_controls.append(ft.Divider(height=1, color=theme.BG_DARK))
    content_controls.append(ft.Container(height=GAP_DIVIDER_TO_BUTTONS))
    content_controls.append(actions_col)
    content_controls.append(ft.Container(content=time_row,
                                          padding=ft.padding.only(top=6)))

    spacing = 0 if has_photo else 6

    return ft.Container(
        content=ft.Column(
            controls=content_controls,
            spacing=spacing,
            tight=True,
        ),
        bgcolor=theme.AI_BUBBLE,
        border_radius=theme.RADIUS,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        padding=ft.padding.symmetric(
            horizontal=BUBBLE_PADDING_H,
            vertical=BUBBLE_PADDING_V,
        ),
        width=_dynamic_width,
    )