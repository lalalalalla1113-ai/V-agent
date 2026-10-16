"""Генерация текста и хештегов через Cloudflare Workers AI.

Оформление — HTML-теги Telegram.
"""

import random
import re
from typing import List, Optional

from services import cf_text
from services import bad_words


# ===========================================================================
# Стили
# ===========================================================================

STYLE_PROMPTS = {
    "complex": (
        "СТИЛЬ: СЛОЖНЫЙ (литературный).\n"
        "• Длинные предложения 15-25 слов, сложные конструкции, метафоры\n"
        "• Богатый словарный запас\n"
        "• Обращение на «вы»\n"
        "• 1-2 эмодзи на весь пост\n"
        "ЗАПРЕЩЕНО: сленг, рубленые фразы."
    ),
    "simple": (
        "СТИЛЬ: ПРОСТОЙ (для всех).\n"
        "• Короткие предложения — 7-10 слов максимум\n"
        "• Только бытовые слова\n"
        "• Один абзац — одна мысль\n"
        "• Обращение на «ты», дружелюбный тон\n"
        "• 3-5 эмодзи на весь пост"
    ),
    "anti_ai": (
        "СТИЛЬ: АНТИ-ИИ (живой человеческий).\n"
        "• Неровный ритм: чередуй короткие и длинные фразы\n"
        "• Живые обороты: «короче», «в общем»\n"
        "ЗАПРЕЩЕНО: «в современном мире», «важно отметить»."
    ),
    "humor": (
        "СТИЛЬ: ЮМОР.\n"
        "• Лёгкий, ироничный, с шутками\n"
        "• Неожиданные сравнения, игра слов\n"
        "• 3-5 эмодзи\n"
        "• Не пошло, не обидно"
    ),
    "scientific": (
        "СТИЛЬ: НАУЧНЫЙ.\n"
        "• Точные формулировки, факты\n"
        "• Нейтральный тон, без эмоций\n"
        "• Минимум эмодзи (0-1)\n"
        "ЗАПРЕЩЕНО: сленг, шутки, восклицания."
    ),
    "story": (
        "СТИЛЬ: ИСТОРИЯ ОТ ПЕРВОГО ЛИЦА.\n"
        "• Расскажи случай из жизни\n"
        "• Финал — вывод или мораль\n"
        "• 2-3 эмодзи"
    ),
    "list": (
        "СТИЛЬ: СПИСКОМ.\n"
        "• Заголовок + нумерованный список (3-5 пунктов)\n"
        "• Каждый пункт — 1 короткое предложение"
    ),
    "question": (
        "СТИЛЬ: ВОПРОС-ОТВЕТ.\n"
        "• Начни с вопроса читателю\n"
        "• Дай ответ или развей тему\n"
        "• Дружелюбный тон, 2-3 эмодзи"
    ),
    "ad": (
        "СТИЛЬ: РЕКЛАМНЫЙ (продающий).\n"
        "• Яркий заголовок\n"
        "• Польза для читателя\n"
        "• Призыв к действию\n"
        "• Без давления, честно"
    ),
    "philosophy": (
        "СТИЛЬ: ФИЛОСОФСКИЙ.\n"
        "• Размышления о жизни, смысле, ценностях\n"
        "• Глубокие мысли, метафоры\n"
        "• Минимум эмодзи"
    ),
    "provocation": (
        "СТИЛЬ: ПРОВОКАЦИОННЫЙ.\n"
        "• Резкое начало, ломающее шаблоны\n"
        "• Спорное утверждение, вопрос-вызов\n"
        "• 1-2 эмодзи"
    ),
}


HASHTAG_STYLES = {
    "wide": "Простые широкие хештеги: #жизнь #утро #счастье",
    "medium": "Средние тематические: #утренняяпробежка #ппрецепты",
    "niche": "Нишевые длинные: #бегоутрамдляначинающих",
    "mixed": "Смешанные: 2-3 широких + 3-4 средних + 2-3 нишевых",
}


# ===========================================================================
# Премиум-эмодзи Telegram (Animated News Emoji)
# ===========================================================================

PREMIUM_EMOJI = {
    "breaking":    ("5456140674028019486",  "⚡️", "срочная новость, важное событие"),
    "ban":         ("5260293700088511294",  "🚫", "запрет, блокировка"),
    "cancel":      ("5240241223632954241",  "❌", "отмена, отказ"),
    "exclamation": ("52740999962655816924", "❗️", "важное замечание, акцент"),
    "double_excl": ("5440660757194744323",  "‼️", "очень важное, двойной акцент"),
    "question":    ("5436113877181941026",  "❓", "вопрос, неизвестность"),
    "warning_red": ("5420323339723881652",  "🔴", "тревога, опасность"),
    "cloud_text":  ("5467538555158943525",  "💬", "цитата, слова, речь"),
    "chat":        ("5443038326535759644",  "💬", "общение, диалог"),
    "stats":       ("5231200819986047254",  "📊", "цифры, статистика, данные"),
    "checkmark":   ("5206607081334906820",  "✅", "подтверждение, готово, факт"),
    "bell":        ("5458603043203327669",  "🔔", "напоминание, уведомление"),
    "fire":        ("5424972470023104089",  "🔥", "огонь, хит, крутое"),
}


def _premium_emoji_catalog_text() -> str:
    lines = []
    for key, data in PREMIUM_EMOJI.items():
        emoji_id = data[0]
        symbol = data[1]
        meaning = data[2]
        lines.append(
            f'  • «{meaning}» — <tg-emoji emoji-id="{emoji_id}">{symbol}</tg-emoji>'
        )
    return "\n".join(lines)


# ===========================================================================
# АВТОЗАМЕНА обычных эмодзи → премиум (расширенная)
# ===========================================================================

_PLAIN_TO_PREMIUM = {
    "⚡": ("5456140674028019486",  "⚡️"),
    "🚫": ("5260293700088511294",  "🚫"),
    "❌": ("5240241223632954241",  "❌"),
    "⛔": ("5260293700088511294",  "🚫"),
    "❗": ("52740999962655816924", "❗️"),
    "‼": ("5440660757194744323",  "‼️"),
    "❓": ("5436113877181941026",  "❓"),
    "🔴": ("5420323339723881652",  "🔴"),
    "💬": ("5467538555158943525",  "💬"),
    "📊": ("5231200819986047254",  "📊"),
    "✅": ("5206607081334906820",  "✅"),
    "✔": ("5206607081334906820",  "✅"),
    "🔔": ("5458603043203327669",  "🔔"),
    "🔥": ("5424972470023104089",  "🔥"),
    "💥": ("5456140674028019486",  "⚡️"),
    "⚠": ("5420323339723881652",  "🔴"),
}


def _replace_plain_with_premium(text: str) -> str:
    """Заменяет обычные эмодзи на <tg-emoji> премиум-версии."""
    if not text:
        return text

    placeholders = {}

    def _stash_existing(m):
        key = f"\x00PREMIUM{len(placeholders)}\x00"
        placeholders[key] = m.group(0)
        return key

    text = re.sub(
        r'<tg-emoji[^>]*>.*?</tg-emoji>',
        _stash_existing,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    items = sorted(_PLAIN_TO_PREMIUM.items(), key=lambda x: -len(x[0]))
    for plain, data in items:
        emoji_id = data[0]
        symbol = data[1]
        pattern = re.escape(plain) + "[\ufe0f\ufe0e]?"
        text = re.sub(
            pattern,
            f'<tg-emoji emoji-id="{emoji_id}">{symbol}</tg-emoji>',
            text,
        )

    for key, val in placeholders.items():
        text = text.replace(key, val)

    return text


def _strip_all_plain_emoji(text: str) -> str:
    """Удаляет все обычные эмодзи из текста (не трогает <tg-emoji>)."""
    if not text:
        return text

    placeholders = {}

    def _stash(m):
        key = f"\x00PREMIUM{len(placeholders)}\x00"
        placeholders[key] = m.group(0)
        return key

    text = re.sub(
        r'<tg-emoji[^>]*>.*?</tg-emoji>',
        _stash,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\U00002600-\U000026FF"
        "\U00002700-\U000027BF"
        "\U0001F1E0-\U0001F1FF"
        "\U0000FE00-\U0000FE0F"
        "\U0001F3FB-\U0001F3FF"
        "\U0000200D"
        "]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)

    for key, val in placeholders.items():
        text = text.replace(key, val)

    text = re.sub(r"  +", " ", text)
    text = re.sub(r" +\n", "\n", text)
    return text


def _force_insert_premium(text: str) -> str:
    """Если в тексте нет ни одного <tg-emoji>, вставляет один после заголовка."""
    fire_data = PREMIUM_EMOJI["fire"]
    fire_id = fire_data[0]
    fire_symbol = fire_data[1]
    fire_tag = f'<tg-emoji emoji-id="{fire_id}">{fire_symbol}</tg-emoji>'

    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip():
            lines[i] = f"{fire_tag} {lines[i].lstrip()}"
            break
    else:
        text = text + f" {fire_tag}"

    return "\n".join(lines)


def _ensure_first_line_bold(text: str) -> str:
    """Гарантирует, что первая непустая строка (заголовок) в <b>…</b>."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<b>") and stripped.endswith("</b>"):
            return text
        lines[i] = f"<b>{stripped}</b>"
        return "\n".join(lines)
    return text


# ===========================================================================
# Случайные вариации
# ===========================================================================

_OPENING_ANGLES = [
    "Начни пост с неожиданного факта по теме.",
    "Начни пост с прямого вопроса читателю.",
    "Начни пост с короткого личного наблюдения.",
    "Начни пост с резкого утверждения.",
    "Начни пост с цифры или статистики по теме.",
    "Начни пост с конкретного примера.",
    "Начни пост с контраста «было — стало».",
    "Начни пост с короткой истории в одно предложение.",
]

_STRUCTURE_STYLES = [
    "Структура: 3 коротких абзаца + список + 1 короткий абзац-вывод.",
    "Структура: 2 абзаца + список + 2 абзаца.",
    "Структура: 1 вводный абзац + список + 1 вывод.",
    "Структура: 4 коротких абзаца без длинных предложений.",
    "Структура: длинный вводный абзац + список + короткий вывод.",
]

_TONE_VARIATIONS = [
    "Тон: дружелюбный, как разговор с другом.",
    "Тон: спокойный, объясняющий.",
    "Тон: уверенный, экспертный.",
    "Тон: лёгкий, с небольшим юмором.",
    "Тон: вдохновляющий.",
]


def _pick_random_variations() -> str:
    opening = random.choice(_OPENING_ANGLES)
    structure = random.choice(_STRUCTURE_STYLES)
    tone = random.choice(_TONE_VARIATIONS)
    return (
        "ВАРИАЦИЯ ЭТОГО КОНКРЕТНОГО ПОСТА:\n"
        f"• {opening}\n"
        f"• {structure}\n"
        f"• {tone}\n"
        "• НЕ повторяй структуру и формулировки из прошлых постов."
    )


# ===========================================================================
# Правила оформления
# ===========================================================================

LANG_RULE = (
    "ЯЗЫК: ТОЛЬКО РУССКИЙ.\n"
    "ЗАПРЕЩЕНО использовать украинские слова (слiд, будь ласка, "
    "дякую, привiт, будь-який и т.п.), белорусские, английские "
    "(кроме общепринятых брендов) и любые другие языки.\n"
    "Пиши ИСКЛЮЧИТЕЛЬНО на литературном русском языке."
)


HTML_FORMAT_RULES = (
    "ОФОРМЛЕНИЕ ДЛЯ TELEGRAM (HTML)\n\n"
    "Разрешённые теги:\n"
    "<b>жирный</b>\n"
    "<i>курсив</i>\n"
    "<blockquote>цитата</blockquote>\n"
    "<tg-spoiler>скрытый текст</tg-spoiler>\n\n"
    "ГЛАВНЫЕ ПРАВИЛА:\n"
    "1. ЗАГОЛОВОК — первая строка, в <b>…</b> с одним эмодзи.\n"
    "2. ВСЕ АБЗАЦЫ ОБОРАЧИВАЙ В <b>…</b> — весь текст поста, "
    "кроме цитаты, должен быть жирным. Это ОБЯЗАТЕЛЬНО.\n"
    "3. <blockquote> используй ТОЛЬКО если это уместно по смыслу. "
    "Если нечего выделять — не добавляй цитату вообще. "
    "Если добавляешь — РОВНО ОДНА, внутри ТОЛЬКО нумерованный "
    "список из 3-5 пунктов:\n"
    "   <blockquote>1. Первый факт\n"
    "   2. Второй факт\n"
    "   3. Третий факт</blockquote>\n"
    "4. Нумерация — цифры с точкой: 1. 2. 3. Без ▫️ ✅ 🔹 • - *.\n"
    "5. Перед <blockquote> и после </blockquote> — пустая строка.\n"
    "6. Пост КОРОТКИЙ: 3-4 абзаца, 1-3 предложения в каждом.\n"
    "7. НЕ пиши префиксы: «Вопрос читателям:», «Вывод:», «Итог:».\n"
    "8. НЕ добавляй в конце вопросов и смайлов типа «А вы как думаете? 👇».\n"
    "9. НЕ повторяй одно слово больше 2 раз.\n"
    "10. Markdown запрещён: **, __, #, `."
)


HTML_FORMAT_RULES_LONG = (
    "ОФОРМЛЕНИЕ ДЛЯ TELEGRAM (HTML)\n\n"
    "ГЛАВНЫЕ ПРАВИЛА:\n"
    "1. ЗАГОЛОВОК — первая строка, в <b>…</b> с одним эмодзи.\n"
    "2. ВСЕ АБЗАЦЫ ОБОРАЧИВАЙ В <b>…</b>.\n"
    "3. <blockquote> — только по смыслу. Если добавляешь — "
    "нумерованный список 1. 2. 3., 3-6 пунктов.\n"
    "4. Перед <blockquote> и после </blockquote> — пустая строка.\n"
    "5. 5-8 абзацев, 2-4 предложения в каждом.\n"
    "6. НЕ пиши префиксы: «Вывод:», «Итог:», «Совет:».\n"
    "7. Markdown запрещён: **, __, #, `."
)


FACT_RULES_ON = (
    "КРИТИЧЕСКОЕ ПРАВИЛО О ФАКТАХ:\n"
    "Используй ТОЛЬКО проверенную, общеизвестную информацию.\n"
    "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдумывать:\n"
    "• имена людей (никаких «соседка Оля»)\n"
    "• случаи из жизни (никаких «вчера в метро»)\n"
    "• конкретные события, места, плакаты, рекламы\n"
    "• статистику, если она не общеизвестна\n"
    "• цитаты, даты, бренды\n"
    "Пиши ОБЩИЕ факты по теме."
)


FACT_RULES_OFF = (
    "СТРОГОЕ ПРАВИЛО:\n"
    "Пиши ТОЛЬКО по информации из темы. Ничего не добавляй.\n"
    "Если в теме меньше 2 конкретных фактов — ВЕРНИ РОВНО ЭТУ СТРОКУ:\n"
    "❌ Недостаточно информации для поста."
)


HTML_FORMAT_EXAMPLE = (
    "ОБРАЗЕЦ ОФОРМЛЕНИЯ:\n\n"
    "<b>🌅 Заголовок в одну строку</b>\n"
    "\n"
    "<b>Первый абзац поста — 1-2 предложения.</b>\n"
    "\n"
    "<blockquote>1. Первый факт\n"
    "2. Второй факт\n"
    "3. Третий факт</blockquote>\n"
    "\n"
    "<b>Второй абзац — короткий вывод.</b>"
)


# ===========================================================================
# НОРМАЛИЗАЦИЯ
# ===========================================================================

_BULLET_MARKERS = ["–", "—", "-"]


def _strip_bullet_glyphs(text: str) -> str:
    for glyph in ("▫️", "▫", "🔹", "🔸", "•", "▪️", "▪"):
        text = text.replace(glyph, "")
    return text


def _number_bullet_lines(text: str) -> str:
    lines = text.split("\n")
    result = []
    counter = 0
    for line in lines:
        s = line.lstrip()
        is_bullet = False
        for m in ("– ", "— ", "- "):
            if s.startswith(m):
                is_bullet = True
                s = s[len(m):]
                break
        if is_bullet:
            counter += 1
            result.append(f"{counter}. {s.rstrip()}")
        else:
            counter = 0
            result.append(line)
    return "\n".join(result)


def _is_bullet_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if re.match(r"^\d+[\.\)]\s", s):
        return True
    for m in _BULLET_MARKERS:
        if s.startswith(m + " "):
            return True
    return False


def _wrap_bullet_runs_in_blockquote(text: str) -> str:
    if "<blockquote" in text.lower():
        return text

    lines = text.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_bullet_line(line):
            run = []
            while i < len(lines) and _is_bullet_line(lines[i]):
                run.append(lines[i].rstrip())
                i += 1
            if run:
                result.append("<blockquote>")
                result.extend(run)
                result.append("</blockquote>")
            continue
        result.append(line)
        i += 1
    return "\n".join(result)


def _strip_question_prefix(text: str) -> str:
    prefixes = [
        "Вопрос читателям:", "Вопрос читателям —", "Вопрос читателям -",
        "Вопрос читателям", "Вопрос:",
        "Вывод:", "Вывод —", "Вывод -",
        "Итог:", "Итог —", "Итог -",
        "Мораль:", "Мораль —", "Мораль -",
        "Заключение:",
        "Главный совет:", "Главный совет —", "Главный совет -",
        "Совет:", "Совет —", "Совет -",
        "Рекомендация:", "Резюме:", "Итак:", "Коротко:",
    ]
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        stripped = line.strip()
        for p in prefixes:
            if stripped.startswith(p):
                remainder = stripped[len(p):].strip()
                remainder = remainder.lstrip(":—-–").strip()
                lines[idx] = remainder
                break
    return "\n".join(lines)


def _limit_single_blockquote(text: str) -> str:
    block_re = re.compile(
        r"<blockquote(?:\s[^>]*)?>(.*?)</blockquote>",
        re.DOTALL | re.IGNORECASE,
    )
    matches = list(block_re.finditer(text))
    if len(matches) <= 1:
        return text

    result = []
    last_end = 0
    for i, m in enumerate(matches):
        if m.start() > last_end:
            result.append(text[last_end:m.start()])
        if i == 0:
            result.append(m.group(0))
        else:
            result.append(m.group(1))
        last_end = m.end()
    if last_end < len(text):
        result.append(text[last_end:])
    return "".join(result)


def _make_all_paragraphs_bold(text: str) -> str:
    block_re = re.compile(
        r"(<blockquote(?:\s[^>]*)?>.*?</blockquote>)",
        re.DOTALL | re.IGNORECASE,
    )
    parts = []
    last_end = 0
    for m in block_re.finditer(text):
        if m.start() > last_end:
            parts.append(("plain", text[last_end:m.start()]))
        parts.append(("quote", m.group(0)))
        last_end = m.end()
    if last_end < len(text):
        parts.append(("plain", text[last_end:]))

    result = []
    for kind, chunk in parts:
        if kind == "quote":
            result.append(chunk)
            continue

        lines = chunk.split("\n")
        out_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                out_lines.append(line)
                continue
            if stripped.startswith("<b>"):
                out_lines.append(line)
                continue
            out_lines.append(f"<b>{stripped}</b>")
        result.append("\n".join(out_lines))
    return "".join(result)


def _clean_whitespace(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" +\n", "\n", text)

    text = re.sub(
        r"(?<![\n])\n(<blockquote)",
        r"\n\n\1",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(</blockquote>)\n(?![\n])",
        r"\1\n\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.rstrip() + "\n"
    return text


def _drop_trailing_call(text: str) -> str:
    lines = text.rstrip().split("\n")
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        low = last.lower()
        drop = False
        if last.endswith("👇"):
            drop = True
        for phrase in (
            "а вы как думаете",
            "как вы думаете",
            "что вы думаете",
            "поделитесь мнением",
            "напишите в комментариях",
        ):
            if phrase in low:
                drop = True
                break
        if drop:
            lines.pop()
            continue
        break
    return "\n".join(lines)


def _postprocess_variant(text: str, learned_mode: bool = False,
                         premium_only: bool = False) -> str:
    if not text:
        return text
    text = text.strip()
    text = _strip_question_prefix(text)
    text = _strip_bullet_glyphs(text)
    text = _number_bullet_lines(text)
    text = _wrap_bullet_runs_in_blockquote(text)
    text = _limit_single_blockquote(text)
    text = _drop_trailing_call(text)

    # Премиум-режим: ВСЕГДА заменяем, потом ВСЕГДА удаляем оставшиеся
    if premium_only:
        text = _replace_plain_with_premium(text)
        text = _strip_all_plain_emoji(text)
        if "<tg-emoji" not in text.lower():
            text = _force_insert_premium(text)

    if not learned_mode:
        text = _make_all_paragraphs_bold(text)
        text = _ensure_first_line_bold(text)

    text = _clean_whitespace(text)
    return text


# ===========================================================================
# ПРОВЕРКА ДОСТАТОЧНОСТИ ДАННЫХ
# ===========================================================================

_VAGUE_WORDS = {
    "что-то", "как-то", "где-то", "когда-то", "почему-то",
    "наверное", "возможно", "может быть", "вроде",
    "интересное", "крутое", "классное", "хорошее", "плохое",
    "всякое", "разное", "тема", "идея", "пост", "контент",
    "про жизнь", "о жизни", "про всё", "обо всём",
}

MIN_WORDS = 2
MIN_SPECIFIC_HINTS = 1


def _count_specific_hints(text: str) -> int:
    text_lower = text.lower()
    hints = 0

    if re.search(r"\d", text):
        hints += 1

    long_words = [
        w for w in re.findall(r"[а-яёa-z]{4,}", text_lower)
        if w not in _VAGUE_WORDS
    ]
    if len(long_words) >= 1:
        hints += 1

    if re.search(
        r"\b(сделать|написать|приготовить|выбрать|купить|начать|"
        r"научиться|попробовать|узнать|понять|разобрать|"
        r"использовать|применять|готовить|варить|жарить|печь|"
        r"читать|смотреть|слушать|играть|бегать|ходить|"
        r"поехать|посетить|создать|построить|собрать|"
        r"рассказать|объяснить|показать|найти|искать|"
        r"решить|спланировать|организовать|"
        r"работать|учиться|заниматься|тренироваться)\b",
        text_lower,
    ):
        hints += 1

    words = text.split()
    for i, w in enumerate(words):
        if i > 0 and w and w[0].isupper() and w[1:].islower():
            hints += 1
            break

    if re.search(r"[:;—\-–]", text):
        hints += 1

    return hints


def _check_idea(idea: str) -> tuple:
    text = (idea or "").strip()

    if not text:
        return False, "Напиши тему поста — что хочешь рассказать?"

    words = text.split()
    if len(words) < MIN_WORDS:
        return False, (
            "Слишком короткая тема. Опиши подробнее:\n"
            "• Что именно рассказать?\n"
            "• Для кого?\n"
            "• Какой результат?"
        )

    text_lower = text.lower()
    non_vague = [
        w for w in re.findall(r"[а-яёa-z]{2,}", text_lower)
        if w not in _VAGUE_WORDS
    ]
    if len(non_vague) < 1:
        return False, (
            "Тема слишком абстрактная. Опиши конкретнее:\n"
            "• Что за тема?\n"
            "• Какие 2-3 факта или действия раскрыть?"
        )

    hints = _count_specific_hints(text)
    if hints < MIN_SPECIFIC_HINTS:
        return False, (
            "Мало конкретики для хорошего поста.\n\n"
            "Добавь хотя бы одно из этого:\n"
            "• Конкретную цифру или срок\n"
            "• Действие («как приготовить», «как выбрать»)\n"
            "• Факт или пример"
        )

    return True, ""


# ===========================================================================
# Промпт
# ===========================================================================

def _build_prompt(idea, style, profile, hashtag_style="mixed",
                  samples=None, auto_add=True, brief=True,
                  use_premium_emoji=False):
    parts = []

    has_samples = bool(samples and any(s.strip() for s in samples if s))

    parts.append(
        "Ты SMM-редактор. ЗАДАЧА: написать ДВА варианта поста.\n"
        "ВАЖНО: Не рассуждай. Сразу выдай готовый текст."
    )

    parts.append(LANG_RULE)

    if has_samples:
        parts.append(
            "РЕЖИМ: ОБУЧЕНИЕ НА ПРИМЕРАХ.\n"
            "Пользователь загрузил посты для обучения. "
            "Соблюдай СТРУКТУРУ этих постов."
        )

        clean_samples = [s for s in samples if s and s.strip()]
        parts.append(
            "ПРИМЕРЫ ПОСТОВ ИЗ КАНАЛА:\n\n"
            + "\n\n— — —\n\n".join(clean_samples[:10])
            + "\n\nВАЖНО: НЕ копируй дословно. "
            "Проанализируй СТРУКТУРУ и пиши НОВЫЙ пост в этом стиле."
        )

    if not has_samples:
        parts.append(HTML_FORMAT_RULES if brief else HTML_FORMAT_RULES_LONG)
        parts.append(FACT_RULES_ON if auto_add else FACT_RULES_OFF)
    else:
        parts.append(FACT_RULES_ON if auto_add else FACT_RULES_OFF)

    if profile:
        user_info = []
        if profile.name:
            user_info.append(f"Имя: {profile.name}")
        if profile.age:
            user_info.append(f"Возраст: {profile.age}")
        if profile.gender == "male":
            user_info.append("Пол: мужской")
        elif profile.gender == "female":
            user_info.append("Пол: женский")
        if profile.audience:
            user_info.append(f"Аудитория: {profile.audience}")
        if user_info:
            parts.append("О пользователе: " + ", ".join(user_info))

    style_prompt = STYLE_PROMPTS.get(
        style or "simple", STYLE_PROMPTS["simple"]
    )
    parts.append(style_prompt)

    if not has_samples:
        parts.append(_pick_random_variations())
        parts.append(HTML_FORMAT_EXAMPLE)

    if brief:
        parts.append(
            "ОБЪЁМ: КОРОТКИЙ. 3-4 абзаца, 1-2 предложения в каждом. "
            "Список — 3-5 пунктов."
        )
    else:
        parts.append(
            "ОБЪЁМ: РАЗВЁРНУТЫЙ. 5-8 абзацев, 2-4 предложения в каждом."
        )

    if use_premium_emoji:
        parts.append(
            "ПРЕМИУМ-ЭМОДЗИ TELEGRAM — ОБЯЗАТЕЛЬНО\n\n"
            "В этом режиме ты используешь ТОЛЬКО премиум-эмодзи "
            "из каталога ниже. ОБЫЧНЫЕ эмодзи (⚡ 📊 ✅ 🔥 ❗ ❓ 🔴 🚫 ❌ 💬 🔔 ⛔) "
            "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ.\n\n"
            "ФОРМАТ ВСТАВКИ:\n"
            '<tg-emoji emoji-id="ID">символ</tg-emoji>\n\n'
            "КАТАЛОГ (ID + символ + смысл):\n"
            + _premium_emoji_catalog_text()
            + "\n\n"
            "ПРАВИЛА:\n"
            "1. ОБЯЗАТЕЛЬНО вставь 1-3 премиум-эмодзи. "
            "Это НЕ опционально.\n"
            "2. Вставляй ПО СМЫСЛУ — рядом с подходящим словом "
            "В СЕРЕДИНЕ предложения. Пример:\n"
            "   <b>Россия занимает "
            '<tg-emoji emoji-id="5231200819986047254">📊</tg-emoji> '
            "второе место в мире.</b>\n"
            "3. НЕ ставь эмодзи только в начало или конец абзаца.\n"
            "4. НЕ используй обычные эмодзи. Только <tg-emoji>."
        )

    parts.append(
        "ФОРМАТ ОТВЕТА:\n\n"
        "===ВАРИАНТ1===\n<текст>\n\n"
        "===ВАРИАНТ2===\n<второй вариант>\n\n"
        f"ИДЕЯ ПОСТА: {idea}\n\n"
        "НАЧНИ ОТВЕТ С «===ВАРИАНТ1===»."
    )
    return "\n\n".join(parts)


# ===========================================================================
# Парсинг
# ===========================================================================

def _parse_variants(raw: str, learned_mode: bool = False,
                    premium_only: bool = False) -> list:
    if not raw:
        return ["Пустой ответ", "Пустой ответ"]
    raw = raw.strip()

    if "===ВАРИАНТ2===" in raw:
        parts = raw.split("===ВАРИАНТ2===")
        v1 = parts[0].replace("===ВАРИАНТ1===", "").strip()
        v2 = parts[1].strip() if len(parts) > 1 else ""
        if v1 and v2:
            return [
                _postprocess_variant(v1, learned_mode, premium_only),
                _postprocess_variant(v2, learned_mode, premium_only),
            ]

    if "===ВАРИАНТ1===" in raw:
        v1 = raw.replace("===ВАРИАНТ1===", "").strip()
        return [_postprocess_variant(v1, learned_mode, premium_only)]

    paragraphs = [p.strip() for p in raw.split("\n\n") if len(p.strip()) > 100]
    if len(paragraphs) >= 2:
        return [
            _postprocess_variant(paragraphs[0], learned_mode, premium_only),
            _postprocess_variant(paragraphs[1], learned_mode, premium_only),
        ]
    return [_postprocess_variant(raw, learned_mode, premium_only)]


# ===========================================================================
# Публичные функции
# ===========================================================================

def generate_content(idea, style, history=None, profile=None,
                     hashtag_style="mixed", samples=None, auto_add=True,
                     brief=True, use_premium_emoji=False):
    ok_data, reason = _check_idea(idea)
    if not ok_data:
        print(f"[TEXT_AI] мало данных: {reason[:80]}")
        return [
            f"❌ Недостаточно информации\n\n{reason}",
            "Напиши подробнее — и я напишу пост.",
        ]

    ok, hits = bad_words.check_text(idea)
    if not ok:
        return [bad_words.forbidden_message(hits)]

    try:
        from services import cf_config
        account, token = cf_config.get_cf_credentials()
        if not account or not token:
            err = cf_config.last_error or "Ключ Cloudflare не задан"
            return [
                f"❌ {err}",
                "Открой Настройки → Cloudflare ключ и вставь токен.",
            ]
    except Exception as ex:
        print(f"[TEXT_AI] cf_config error: {ex}")

    has_samples = bool(samples and any(s.strip() for s in samples if s))

    full_prompt = _build_prompt(idea, style, profile, hashtag_style,
                                samples, auto_add, brief, use_premium_emoji)

    result = cf_text.ask(
        full_prompt,
        system="Ты SMM-редактор. Выдаёшь только готовый текст на русском языке.",
        max_tokens=1500,
    )
    if not result:
        err = getattr(cf_text, "last_error", "") or "неизвестная ошибка"
        return [
            f"❌ Не удалось сгенерировать ({err}).",
            "Проверь ключ Cloudflare и интернет.",
        ]

    if result.strip().startswith("❌ Недостаточно информации"):
        return [
            "❌ Недостаточно информации для поста.",
            "Опиши тему конкретнее: что, для кого, зачем.",
        ]

    return _parse_variants(
        result,
        learned_mode=has_samples,
        premium_only=use_premium_emoji,
    )

def generate_hashtags(topic, style="simple", hashtag_style="mixed", count=20):
    """Генерирует хештеги СТРОГО по теме.

    Только ОДНО русское слово в хештеге. Никаких склеек.
    """
    ok, hits = bad_words.check_text(topic)
    if not ok:
        return bad_words.forbidden_message(hits)

    count = max(5, min(40, int(count or 20)))

    style_hint = {
        "mixed": "Комбинируй разные типы: широкие + средние + нишевые.",
        "content": "Контентные. Прямые и описательные слова о предметах, действиях.",
        "wide": "Широкие массовые слова — самые общие по теме.",
        "medium": "Средние тематические слова — не общие, не узкие.",
        "niche": "Узкие точные слова по теме.",
        "trending": "Актуальные современные слова по теме.",
        "branded": "Слова для личного бренда — качества, характеристики.",
        "audience": "Слова для целевой аудитории — по профессии, интересам.",
        "flashmob": "Слова-призывы к действию, короткие и запоминающиеся.",
        "emotion": "Слова-эмоции и настроения: счастье, уют, вдохновение.",
        "humor": "Ироничные слова по теме, с юмором.",
        "spam": "Общие хештеги, но НЕ спамные — просто широкие по теме.",
        "abstract": "Абстрактные общие слова: жизнь, любовь, момент.",
    }.get(hashtag_style, "Разные односложные слова по теме.")

    # Извлекаем ключевые слова из темы для проверки
    topic_words = [w.lower() for w in topic.split() if len(w) > 2]

    prompt = (
        f"Тема: «{topic.strip().lower()}»\n\n"
        f"Сгенерируй РОВНО {count} хештегов СТРОГО по этой теме.\n\n"
        "КРИТИЧЕСКИЕ ПРАВИЛА:\n"
        "1. Каждый хештег — ОДНО обычное русское слово.\n"
        "2. НЕЛЬЗЯ склеивать слова! Плохие примеры (ТАК НЕ ДЕЛАЙ):\n"
        "   #домашнеуютникошки #летишикошки #мирочковокошкиники "
        "#волнырадости #солнечнолюбовь #домашнекаринка\n"
        "   Хорошие примеры: #кошки #дом #уют #радость #солнце\n"
        "3. Хештег — это ОДНО существующее русское слово, "
        "которое можно найти в словаре.\n"
        "4. НЕ придумывай новые слова! Если не уверен — не пиши.\n"
        "5. Длина слова — от 4 до 15 символов.\n"
        "6. Без подчёркиваний (_), без английских букв, без цифр.\n"
        "7. Слова должны быть ПРЯМО связаны с темой выше.\n"
        "8. Каждое слово на новой строке с # в начале.\n\n"
        "ПРИМЕР ПРАВИЛЬНОГО ВЫВОДА для темы «кошки»:\n"
        "#кошки\n"
        "#кот\n"
        "#котята\n"
        "#мурлыка\n"
        "#питомец\n"
        "#пушистый\n"
        "#ласка\n"
        "#игра\n"
        "#корм\n"
        "#уход\n"
        "...\n\n"
        f"СТИЛЬ: {style_hint}\n\n"
        f"Сгенерируй РОВНО {count} хештегов. Каждое слово — "
        "настоящее русское слово, без склеек."
    )

    result = cf_text.ask(prompt, max_tokens=800)

    tags = []
    if result:
        raw_tags = re.findall(r"#([\wа-яё]+)", result, re.IGNORECASE)
        for body in raw_tags:
            if not body:
                continue
            # Только русские буквы, без _
            if not re.fullmatch(r"[а-яё]+", body, re.IGNORECASE):
                continue
            # Длина 4-15
            if len(body) < 4 or len(body) > 15:
                continue
            # Запрет длинных "склеек" — слов с 3+ согласными подряд,
            # что редко бывает в русском
            if re.search(r"[бвгджзйклмнпрстфхцчшщ]{4,}", body.lower()):
                continue
            formatted = "#" + body.lower()
            if formatted not in tags:
                tags.append(formatted)
            if len(tags) >= count:
                break

    # Fallback: слова из темы
    if len(tags) < count:
        for w in topic_words:
            if len(tags) >= count:
                break
            w_clean = "".join(ch for ch in w if ch.isalpha())
            if len(w_clean) < 4:
                continue
            formatted = f"#{w_clean}"
            if formatted not in tags:
                tags.append(formatted)

    return "\n".join(tags[:count])