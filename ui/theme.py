"""Цветовые палитры и константы оформления.

Поддерживается 3 темы. Переключение — через `apply(theme_key)`.
Тема хранится в профиле пользователя (поле `ui_theme`).
"""


# ===========================================================================
# ПАЛИТРЫ
# ===========================================================================

THEMES = {
    # -----------------------------------------------------------------------
    # 1. Фиолетовый и чёрный
    # -----------------------------------------------------------------------
    "dark_purple": {
        "label": "Фиолетовый и чёрный",
        "icon": "🟣",
        "PRIMARY": "#9C27B0",
        "PRIMARY_DARK": "#7B1FA2",
        "PRIMARY_LIGHT": "#CE93D8",
        "BG_DARK": "#151518",
        "BG_ELEVATED": "#1C1C20",
        "SURFACE": "#222226",
        "SURFACE_HOVER": "#2C2C32",
        "USER_BUBBLE": "#7B1FA2",
        "AI_BUBBLE": "#26262B",
        "TEXT_PRIMARY": "#FFFFFF",
        "TEXT_SECONDARY": "#A8A8A8",
        "TEXT_MUTED": "#707076",
        "DIVIDER": "#2E2E34",
        "SIDEBAR_BG": "#050505",
        "SIDEBAR_ITEM_HOVER": "#141418",
        "SIDEBAR_BORDER": "#141418",
        "DRAWER_BG": "#050505",
        "DRAWER_ITEM_BG": "#101014",
        "DRAWER_ITEM_HOVER": "#1A1A1E",
        "DRAWER_ITEM_BORDER": "#1E1E24",
        "SUCCESS": "#4CAF50",
        "WARNING": "#FF9800",
        "DANGER": "#FF5252",
        "INFO": "#2196F3",
        "is_dark": True,
    },

    # -----------------------------------------------------------------------
    # 2. Синий и белый (тёмная)
    # -----------------------------------------------------------------------
    "dark_blue": {
        "label": "Синий и белый",
        "icon": "🔵",
        "PRIMARY": "#2196F3",
        "PRIMARY_DARK": "#1976D2",
        "PRIMARY_LIGHT": "#64B5F6",
        "BG_DARK": "#0D1117",
        "BG_ELEVATED": "#141A22",
        "SURFACE": "#1A1F29",
        "SURFACE_HOVER": "#232A36",
        "USER_BUBBLE": "#1976D2",
        "AI_BUBBLE": "#1F2632",
        "TEXT_PRIMARY": "#FFFFFF",
        "TEXT_SECONDARY": "#A8B0BD",
        "TEXT_MUTED": "#6B7585",
        "DIVIDER": "#232A36",
        "SIDEBAR_BG": "#070A0F",
        "SIDEBAR_ITEM_HOVER": "#121823",
        "SIDEBAR_BORDER": "#121823",
        "DRAWER_BG": "#070A0F",
        "DRAWER_ITEM_BG": "#0E131B",
        "DRAWER_ITEM_HOVER": "#182030",
        "DRAWER_ITEM_BORDER": "#1A2230",
        "SUCCESS": "#4CAF50",
        "WARNING": "#FF9800",
        "DANGER": "#FF5252",
        "INFO": "#2196F3",
        "is_dark": True,
    },

    # -----------------------------------------------------------------------
    # 3. Алый и чёрный
    # -----------------------------------------------------------------------
    "red_black": {
        "label": "Алый и чёрный",
        "icon": "🔴",
        "PRIMARY": "#E53935",
        "PRIMARY_DARK": "#B71C1C",
        "PRIMARY_LIGHT": "#EF5350",
        "BG_DARK": "#151515",
        "BG_ELEVATED": "#1C1C1C",
        "SURFACE": "#222222",
        "SURFACE_HOVER": "#2C2C2C",
        "USER_BUBBLE": "#B71C1C",
        "AI_BUBBLE": "#262626",
        "TEXT_PRIMARY": "#FFFFFF",
        "TEXT_SECONDARY": "#A8A8A8",
        "TEXT_MUTED": "#707070",
        "DIVIDER": "#2E2E2E",
        "SIDEBAR_BG": "#0A0A0A",
        "SIDEBAR_ITEM_HOVER": "#1A1A1A",
        "SIDEBAR_BORDER": "#1A1A1A",
        "DRAWER_BG": "#0A0A0A",
        "DRAWER_ITEM_BG": "#141414",
        "DRAWER_ITEM_HOVER": "#1E1E1E",
        "DRAWER_ITEM_BORDER": "#242424",
        "SUCCESS": "#66BB6A",
        "WARNING": "#FFA726",
        "DANGER": "#EF5350",
        "INFO": "#42A5F5",
        "is_dark": True,
    },
}

DEFAULT_THEME = "dark_purple"


# ===========================================================================
# ТЕКУЩАЯ ТЕМА
# ===========================================================================

CURRENT_THEME = DEFAULT_THEME

# Значения по умолчанию — вычисляются при импорте
PRIMARY = "#9C27B0"
PRIMARY_DARK = "#7B1FA2"
PRIMARY_LIGHT = "#CE93D8"
BG_DARK = "#151518"
BG_ELEVATED = "#1C1C20"
SURFACE = "#222226"
SURFACE_HOVER = "#2C2C32"
USER_BUBBLE = "#7B1FA2"
AI_BUBBLE = "#26262B"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#A8A8A8"
TEXT_MUTED = "#707076"
DIVIDER = "#2E2E34"
SIDEBAR_BG = "#050505"
SIDEBAR_ITEM_HOVER = "#141418"
SIDEBAR_BORDER = "#141418"
DRAWER_BG = "#050505"
DRAWER_ITEM_BG = "#101014"
DRAWER_ITEM_HOVER = "#1A1A1E"
DRAWER_ITEM_BORDER = "#1E1E24"
SUCCESS = "#4CAF50"
WARNING = "#FF9800"
DANGER = "#FF5252"
INFO = "#2196F3"
IS_DARK = True


# ===========================================================================
# ПУБЛИЧНЫЕ ФУНКЦИИ
# ===========================================================================

def apply(theme_key):
    """Меняет текущую тему.

    Переприсваивает все модульные переменные под новую палитру.
    После вызова нужно перезагрузить UI (обычно через _reload_app).
    """
    global CURRENT_THEME
    global PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT
    global BG_DARK, BG_ELEVATED, SURFACE, SURFACE_HOVER
    global USER_BUBBLE, AI_BUBBLE
    global TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
    global DIVIDER
    global SIDEBAR_BG, SIDEBAR_ITEM_HOVER, SIDEBAR_BORDER
    global DRAWER_BG, DRAWER_ITEM_BG, DRAWER_ITEM_HOVER, DRAWER_ITEM_BORDER
    global SUCCESS, WARNING, DANGER, INFO
    global IS_DARK

    palette = THEMES.get(theme_key)
    if not palette:
        theme_key = DEFAULT_THEME
        palette = THEMES[theme_key]

    CURRENT_THEME = theme_key

    PRIMARY = palette["PRIMARY"]
    PRIMARY_DARK = palette["PRIMARY_DARK"]
    PRIMARY_LIGHT = palette["PRIMARY_LIGHT"]
    BG_DARK = palette["BG_DARK"]
    BG_ELEVATED = palette["BG_ELEVATED"]
    SURFACE = palette["SURFACE"]
    SURFACE_HOVER = palette["SURFACE_HOVER"]
    USER_BUBBLE = palette["USER_BUBBLE"]
    AI_BUBBLE = palette["AI_BUBBLE"]
    TEXT_PRIMARY = palette["TEXT_PRIMARY"]
    TEXT_SECONDARY = palette["TEXT_SECONDARY"]
    TEXT_MUTED = palette["TEXT_MUTED"]
    DIVIDER = palette["DIVIDER"]
    SIDEBAR_BG = palette["SIDEBAR_BG"]
    SIDEBAR_ITEM_HOVER = palette["SIDEBAR_ITEM_HOVER"]
    SIDEBAR_BORDER = palette["SIDEBAR_BORDER"]
    DRAWER_BG = palette["DRAWER_BG"]
    DRAWER_ITEM_BG = palette["DRAWER_ITEM_BG"]
    DRAWER_ITEM_HOVER = palette["DRAWER_ITEM_HOVER"]
    DRAWER_ITEM_BORDER = palette["DRAWER_ITEM_BORDER"]
    SUCCESS = palette["SUCCESS"]
    WARNING = palette["WARNING"]
    DANGER = palette["DANGER"]
    INFO = palette["INFO"]
    IS_DARK = palette["is_dark"]

    print(f"[THEME] применена тема: {theme_key} ({palette['label']})")


def get_themes():
    """Возвращает список (ключ, словарь) для UI-выбора."""
    return [(k, v) for k, v in THEMES.items()]


# ===========================================================================
# КОНСТАНТЫ (не зависят от темы)
# ===========================================================================

RADIUS = 14
RADIUS_SMALL = 10
RADIUS_LARGE = 20
PADDING = 16
SPACING = 10

DRAWER_ANIMATION_MS = 300

SIDEBAR_COLLAPSED = 64
SIDEBAR_EXPANDED = 220
SIDEBAR_ANIM_MS = 200
SIDEBAR_ITEM_RADIUS = 14