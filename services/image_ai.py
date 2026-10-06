"""Генерация картинок.

Основной провайдер — Cloudflare Workers AI (FLUX.1-schnell).
Резервный — Pollinations.
Перевод RU→EN — через Cloudflare (Llama 3.1).
"""

import re
import time
from typing import Optional, Tuple

from services import image_providers, cf_text


# ---------- Стили ----------

IMAGE_STYLES = {
    "photo": {
        "label": "Реализм",
        "prompt_suffix": (
            "RAW photo, natural lighting, photorealistic, hyperrealistic, "
            "sharp focus, 8k, film grain, depth of field, "
            "professional photography, ultra realistic"
        ),
    },
    "anime": {
        "label": "Аниме",
        "prompt_suffix": (
            "anime artwork, Studio Ghibli style, soft cel shading, "
            "hand-drawn, vibrant pastel colors, detailed background, "
            "japanese animation, high quality anime illustration, "
            "beautiful scenery"
        ),
    },
    "3d": {
        "label": "3D",
        "prompt_suffix": (
            "3D render, octane render, cinematic lighting, volumetric fog, "
            "subsurface scattering, ray tracing, physically based rendering, "
            "highly detailed, 8k, ambient occlusion"
        ),
    },
    "cyberpunk": {
        "label": "Киберпанк",
        "prompt_suffix": (
            "cyberpunk style, neon lights, blade runner aesthetic, "
            "rainy night city, holographic ads, purple and cyan glow, "
            "futuristic high-tech, chrome details, atmospheric fog, "
            "cinematic, moody lighting"
        ),
    },
    "fantasy": {
        "label": "Фэнтези",
        "prompt_suffix": (
            "epic fantasy art, magical atmosphere, glowing runes, "
            "dramatic lighting, concept art, intricate details, "
            "cinematic composition, masterpiece, highly detailed"
        ),
    },
    "sketch": {
        "label": "Скетч",
        "prompt_suffix": (
            "pencil sketch, hand-drawn graphite illustration, "
            "cross-hatching, black and white, detailed linework, "
            "fine art drawing, sketchbook style, monochrome, "
            "artist sketch"
        ),
    },
    "minimal": {
        "label": "Минимализм",
        "prompt_suffix": (
            "minimalist design, flat vector illustration, clean lines, "
            "solid colors, negative space, geometric shapes, "
            "simple composition, modern art, swiss design, poster style"
        ),
    },
}


# ---------- Мини-словарь (быстрый перевод) ----------

_RU_EN_DICT = {
    "кот": "cat", "кошка": "cat", "котик": "kitten", "котёнок": "kitten",
    "собака": "dog", "пёс": "dog", "щенок": "puppy", "птица": "bird",
    "попугай": "parrot", "рыба": "fish", "лошадь": "horse",
    "медведь": "bear", "лиса": "fox", "волк": "wolf", "тигр": "tiger",
    "лев": "lion", "слон": "elephant", "дракон": "dragon",
    "лес": "forest", "дерево": "tree", "цветок": "flower",
    "цветы": "flowers", "трава": "grass", "гора": "mountain",
    "горы": "mountains", "река": "river", "озеро": "lake",
    "море": "sea", "океан": "ocean", "пляж": "beach",
    "небо": "sky", "облако": "cloud", "облака": "clouds",
    "солнце": "sun", "луна": "moon", "звёзды": "stars",
    "закат": "sunset", "рассвет": "sunrise", "радуга": "rainbow",
    "снег": "snow", "дождь": "rain", "гроза": "thunderstorm",
    "туман": "fog", "вода": "water", "огонь": "fire",
    "дом": "house", "квартира": "apartment", "замок": "castle",
    "город": "city", "деревня": "village", "улица": "street",
    "мост": "bridge", "дорога": "road", "машина": "car",
    "корабль": "ship", "самолёт": "airplane", "ракета": "rocket",
    "космос": "space", "планета": "planet",
    "стол": "table", "стул": "chair", "кровать": "bed",
    "диван": "sofa", "шкаф": "wardrobe", "лампа": "lamp",
    "окно": "window", "дверь": "door", "кухня": "kitchen",
    "еда": "food", "пицца": "pizza", "кофе": "coffee", "чай": "tea",
    "торт": "cake", "хлеб": "bread", "яблоко": "apple",
    "девушка": "young woman", "парень": "young man",
    "мужчина": "man", "женщина": "woman", "ребёнок": "child",
    "дети": "children", "мальчик": "boy", "девочка": "girl",
    "друзья": "friends", "семья": "family",
    "робот": "robot", "рыцарь": "knight", "воин": "warrior",
    "ангел": "angel", "демон": "demon", "магия": "magic",
    "любовь": "love", "счастье": "happiness", "грусть": "sadness",
    "дачный": "countryside", "старый": "old", "новый": "new",
    "большой": "big", "маленький": "small", "красивый": "beautiful",
    "тёмный": "dark", "светлый": "bright", "ночной": "night",
    "зимний": "winter", "летний": "summer", "осенний": "autumn",
    "весенний": "spring",
}

_TRANSLATION_CACHE: dict = {}


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[а-яА-ЯёЁ]", text))


def _dict_translate(text: str) -> Optional[str]:
    words = text.lower().strip().split()
    if not words or len(words) > 5:
        return None
    translated, found = [], 0
    for w in words:
        w_clean = "".join(ch for ch in w if ch.isalpha())
        if w_clean in _RU_EN_DICT:
            translated.append(_RU_EN_DICT[w_clean])
            found += 1
        else:
            translated.append(w)
    if found == 0 or found / len(words) < 0.6:
        return None
    return " ".join(translated)


def _translate_to_english(text: str) -> str:
    """Переводит RU → EN.

    1. Словарь — быстро.
    2. Cloudflare Llama — если слова нет.
    3. Оригинал — если всё упало.
    """
    text = text.strip()
    if not text:
        return text
    if text in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[text]
    if not _has_cyrillic(text):
        _TRANSLATION_CACHE[text] = text
        return text

    # 1. Словарь
    quick = _dict_translate(text)
    if quick:
        _TRANSLATION_CACHE[text] = quick
        print(f"[TRANSLATE-DICT] «{text}» → «{quick}»")
        return quick

    # 2. Cloudflare
    prompt = (
        "Translate the following Russian text to English. "
        "Output ONLY the English translation, no quotes, no notes, "
        "no explanations, no prefixes.\n\n"
        f"{text}"
    )
    result = cf_text.ask(
        prompt,
        system="You are a translator. Output only the translation.",
        max_tokens=200,
    )
    if result:
        out = result.strip().strip('"').strip("'").strip()
        for prefix in ("Translation:", "Перевод:", "English:"):
            if out.lower().startswith(prefix.lower()):
                out = out[len(prefix):].strip()
        if out and not _has_cyrillic(out):
            _TRANSLATION_CACHE[text] = out
            print(f"[TRANSLATE-CF] «{text}» → «{out}»")
            return out

    print(f"[TRANSLATE] Не удалось перевести «{text}», оставляю как есть")
    _TRANSLATION_CACHE[text] = text
    return text


# ---------- Сборка промпта ----------

QUALITY_BOOST = "masterpiece, best quality, highly detailed, sharp focus"


def _needs_quality_boost(text: str) -> bool:
    return len(text.split()) <= 3


def build_full_prompt(user_prompt: str, style_key: str) -> str:
    user_prompt = user_prompt.strip()
    if _has_cyrillic(user_prompt):
        user_prompt = _translate_to_english(user_prompt)
    style = IMAGE_STYLES.get(style_key)
    suffix = style["prompt_suffix"] if style else ""
    if len(user_prompt.split()) <= 2:
        core = f"{user_prompt}, main subject: {user_prompt}"
    else:
        core = user_prompt
    parts = [core]
    if _needs_quality_boost(user_prompt):
        parts.append(QUALITY_BOOST)
    if suffix:
        parts.append(suffix)
    return ", ".join(parts)


# ---------- Публичная функция ----------

def generate_image(
    prompt: str,
    style_key: str = "photo",
    width: int = 1024,
    height: int = 1024,
) -> Tuple[Optional[bytes], str]:
    """Генерирует картинку.

    Возвращает (bytes, "") при успехе или (None, "текст ошибки").
    """
    full_prompt = build_full_prompt(prompt, style_key)
    print(f"[PROMPT] {full_prompt}")

    errors = []

    # 1. Cloudflare (основной)
    result, err = image_providers.generate_cloudflare(full_prompt, width, height)
    if result:
        return result, ""
    if err:
        errors.append(err)
    print("[IMAGE] Cloudflare не справился, пробуем Pollinations")

    # 2. Pollinations (резерв)
    result, err = image_providers.generate_pollinations(full_prompt, width, height)
    if result:
        return result, ""
    if err:
        errors.append(err)

    summary = errors[0] if errors else "Все провайдеры недоступны"
    print(f"[IMAGE] Ошибка: {summary}")
    return None, summary