"""
Конфигурация AI-агента
Все настройки, константы и маппинги.
"""

import os

# Загружаем переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ═══════════════════════════════════════════════════════
#                     API НАСТРОЙКИ
# ═══════════════════════════════════════════════════════

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
HTTP_REFERRER = "http://localhost:8080"
APP_TITLE = "AI-Agent-Extended"


# ═══════════════════════════════════════════════════════
#                     МОДЕЛЬ
# ═══════════════════════════════════════════════════════

MODEL_NAME = "stealth/space-bunny-alpha"

# Reasoning
ENABLE_REASONING = True
REASONING_EFFORT = "high"  # "low", "medium", "high"


# ═══════════════════════════════════════════════════════
#                    АГЕНТ
# ═══════════════════════════════════════════════════════

SCREEN_WIDTH = 1280       # Ширина скриншота для модели
CLICK_DELAY = 2           # Задержка перед кликом (сек)
MAX_STEPS = 100           # Максимум шагов за задачу
WAIT_AFTER = 1.5          # Пауза после действия (сек)
MAX_RETRIES = 2           # Повторных попыток API
TIMEOUT = 90              # Таймаут запроса (сек)
MAX_HISTORY = 100         # Сколько шагов хранить в контексте


# ═══════════════════════════════════════════════════════
#                    ОТЛАДКА
# ═══════════════════════════════════════════════════════

SAVE_LOG = True
LOG_FILE = "agent_log.txt"
DEBUG = True
DEBUG_DIR = "debug_screenshots"
MOUSE_SPEED = 0.3
FAILSAFE = True


# ═══════════════════════════════════════════════════════
#              ПОЛНЫЙ МАППИНГ КЛАВИШ PYAUTOGUI
# ═══════════════════════════════════════════════════════

KEY_ALIASES = {
    # Базовые
    "enter": "enter", "return": "enter",
    "esc": "escape", "escape": "escape",
    "tab": "tab", "backspace": "backspace",
    "delete": "delete", "del": "delete",
    "insert": "insert", "ins": "insert",
    "space": "space", "spacebar": "space",

    # Стрелки
    "up": "up", "down": "down", "left": "left", "right": "right",
    "arrow_up": "up", "arrow_down": "down",
    "arrow_left": "left", "arrow_right": "right",

    # Навигация
    "home": "home", "end": "end",
    "pageup": "pageup", "pgup": "pageup", "page_up": "pageup",
    "pagedown": "pagedown", "pgdn": "pagedown", "page_down": "pagedown",

    # Модификаторы
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift",
    "alt": "alt", "option": "alt",
    "win": "win", "windows": "win", "cmd": "win",
    "command": "win", "super": "win",

    # Функциональные f1-f24
    **{f"f{i}": f"f{i}" for i in range(1, 25)},

    # NumPad
    **{f"numpad{i}": f"num{i}" for i in range(10)},
    **{f"num{i}": f"num{i}" for i in range(10)},
    "numpad_enter": "enter",
    "numpad_add": "add", "numpad_plus": "add",
    "numpad_subtract": "subtract", "numpad_minus": "subtract",
    "numpad_multiply": "multiply", "numpad_star": "multiply",
    "numpad_divide": "divide", "numpad_slash": "divide",
    "numpad_decimal": "decimal", "numpad_dot": "decimal",

    # Специальные
    "printscreen": "printscreen", "prtsc": "printscreen",
    "print_screen": "printscreen",
    "scrolllock": "scrolllock", "scroll_lock": "scrolllock",
    "capslock": "capslock", "caps_lock": "capslock",
    "numlock": "numlock", "num_lock": "numlock",
    "pause": "pause", "break": "pause",

    # Медиа
    "volumeup": "volumeup", "volume_up": "volumeup", "volup": "volumeup",
    "volumedown": "volumedown", "volume_down": "volumedown",
    "volumemute": "volumemute", "volume_mute": "volumemute", "mute": "volumemute",
    "playpause": "playpause", "play": "playpause",
    "nexttrack": "nexttrack", "next": "nexttrack",
    "prevtrack": "prevtrack", "prev": "prevtrack", "previous": "prevtrack",

    # Символы
    "minus": "minus", "dash": "minus",
    "equals": "equals", "equal": "equals",
    "leftbracket": "leftbracket",
    "rightbracket": "rightbracket",
    "backslash": "backslash",
    "semicolon": "semicolon",
    "apostrophe": "apostrophe", "quote": "apostrophe",
    "comma": "comma",
    "period": "period", "dot": "period",
    "slash": "slash", "divide": "slash",

    # Мышь (для key_down/key_up)
    "mouse_left": "left", "mouse_right": "right", "mouse_middle": "middle",
}