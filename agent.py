#!/usr/bin/env python3
"""
AI-Агент через OpenRouter API с расширенными возможностями:
- Drag & Drop (перетаскивание)
- Любые клавиши и комбинации
- Удержание клавиш (key_down / key_up)
- Модели: Qwen3.8-27B, Gemini, Claude, GPT-4o
"""

import ctypes
from ctypes import wintypes
import requests
import pyautogui
import base64
from PIL import Image, ImageChops, ImageDraw
import io
import json
import time
import sys
import os
import signal
import subprocess
import ctypes
from datetime import datetime

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    import pyperclip

    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

# ═══════════════════════════════════════════════════════
#                  DPI AWARENESS (Windows)
# ═══════════════════════════════════════════════════════
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ═══════════════════════════════════════════════════════
#                     НАСТРОЙКИ
# ═══════════════════════════════════════════════════════

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
HTTP_REFERRER = "http://localhost:8080"
APP_TITLE = "AI-Agent-Extended"

# ── Модель ──
MODEL_NAME = "nvidia/nemotron-3.5-super-vl:free"

# ── Reasoning ──
ENABLE_REASONING = True
REASONING_EFFORT = "high"

# ── Агент ──
SCREEN_WIDTH = 1280
CLICK_DELAY = 0
MAX_STEPS = 1000

WAIT_AFTER = 1.5
MAX_RETRIES = 2
TIMEOUT = 90
MAX_HISTORY = 100

SCROLL_PIXELS_PER_CLICK = 200  # Сколько пикселей прокручивает 1 клик колеса

# ── Отладка ──
SAVE_LOG = True
LOG_FILE = "agent_log.txt"
DEBUG = True
DEBUG_DIR = "debug_screenshots"
MOUSE_SPEED = 0.3
FAILSAFE = True
# ═══════════════════════════════════════════════════════

REAL_W, REAL_H = pyautogui.size()
pyautogui.FAILSAFE = FAILSAFE
pyautogui.PAUSE = 0.05

previous_screenshot = None
action_history = []
log_lines = []
running = True
step_counter = 0
total_cost = 0.0
conversation_history = []

# ═══════════════════════════════════════════════════════
#   ПОЛНЫЙ МАППИНГ КЛАВИШ PYAUTOGUI
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
    "arrow_up": "up", "arrow_down": "down", "arrow_left": "left", "arrow_right": "right",

    # Навигация
    "home": "home", "end": "end",
    "pageup": "pageup", "pgup": "pageup", "page_up": "pageup",
    "pagedown": "pagedown", "pgdn": "pagedown", "page_down": "pagedown",

    # Модификаторы
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift",
    "alt": "alt", "option": "alt",
    "win": "win", "windows": "win", "cmd": "win", "command": "win", "super": "win",

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
    "printscreen": "printscreen", "prtsc": "printscreen", "print_screen": "printscreen",
    "scrolllock": "scrolllock", "scroll_lock": "scrolllock",
    "capslock": "capslock", "caps_lock": "capslock",
    "numlock": "numlock", "num_lock": "numlock",
    "pause": "pause", "break": "pause",

    # Медиа
    "volumeup": "volumeup", "volume_up": "volumeup", "volup": "volumeup",
    "volumedown": "volumedown", "volume_down": "volumedown", "voldn": "volumedown",
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


# ───────────────────────────────────────────────────────
#                    УТИЛИТЫ
# ───────────────────────────────────────────────────────

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"

    colors = {
        "ERROR": "\033[91m[✗]\033[0m",
        "SUCCESS": "\033[92m[✓]\033[0m",
        "WARN": "\033[93m[!]\033[0m",
        "DEBUG": "\033[90m[·]\033[0m",
        "API": "\033[96m[API]\033[0m",
        "REASONING": "\033[95m[💭]\033[0m",
        "INFO": "[i]"
    }

    prefix = colors.get(level, "")
    print(f"  {prefix} {msg}")

    if SAVE_LOG:
        log_lines.append(line)


def save_log():
    if SAVE_LOG and log_lines:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"Сессия: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Модель: {MODEL_NAME}\n")
            f.write(f"Reasoning: {'ON' if ENABLE_REASONING else 'OFF'}\n")
            f.write(f"Стоимость: ${total_cost:.6f}\n")
            f.write(f"{'=' * 60}\n")
            f.write("\n".join(log_lines) + "\n\n")


def signal_handler(sig, frame):
    global running
    log("Остановлено пользователем", "WARN")
    # Отпускаем все зажатые клавиши при выходе
    try:
        for key in ["ctrl", "shift", "alt", "win", "command"]:
            try:
                pyautogui.keyUp(key)
            except Exception:
                pass
        for btn in ["left", "right", "middle"]:
            try:
                pyautogui.mouseUp(button=btn)
            except Exception:
                pass
    except Exception:
        pass
    running = False
    save_log()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def copy_to_clipboard(text):
    try:
        if HAS_PYPERCLIP:
            pyperclip.copy(text)
            return True
        if sys.platform == "win32":
            process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
            process.communicate(text.encode('utf-16-le'))
            return True
        else:
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))
            return True
    except Exception:
        return False


def save_debug_screenshot(screenshot, x=None, y=None, action="", label=""):
    if not DEBUG:
        return
    os.makedirs(DEBUG_DIR, exist_ok=True)

    draw = ImageDraw.Draw(screenshot)
    if x is not None and y is not None:
        r = 15
        draw.ellipse([x - r, y - r, x + r, y + r], outline="red", width=3)
        draw.line([x - r - 5, y, x + r + 5, y], fill="red", width=2)
        draw.line([x, y - r - 5, x, y + r + 5], fill="red", width=2)
        text = f"{action} ({x},{y})"
        draw.text((x + 20, y - 10), text, fill="red")

    filename = f"{step_counter:03d}_{label}.png"
    filepath = os.path.join(DEBUG_DIR, filename)
    screenshot.save(filepath)


# ───────────────────────────────────────────────────────
#                 ПРОВЕРКА ОКРУЖЕНИЯ
# ───────────────────────────────────────────────────────

def check_environment():
    global REAL_W, REAL_H

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║   🪟 AI-Агент (расширенная версия)                 ║")
    print("║   • Drag & Drop   • Любые клавиши                  ║")
    print("║   • Комбинации    • Удержание                      ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    if not OPENROUTER_API_KEY:
        log("API ключ OpenRouter не найден!", "ERROR")
        log("Создайте .env: OPENROUTER_API_KEY=sk-or-v1-...", "ERROR")
        return False
    log(f"API ключ: {'*' * 10}...{OPENROUTER_API_KEY[-4:]}", "SUCCESS")

    REAL_W, REAL_H = pyautogui.size()
    log(f"Экран: {REAL_W}x{REAL_H}")

    if sys.platform == "win32":
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
            scale = dpi / 96.0
            log(f"Масштаб: {scale * 100:.0f}% (DPI={dpi})")
        except Exception:
            pass

    log("Проверяю API...")
    try:
        test_payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "Hi"}]}
            ],
            "max_tokens": 5
        }
        if ENABLE_REASONING:
            test_payload["reasoning"] = {"enabled": True}

        r = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": HTTP_REFERRER,
                "X-Title": APP_TITLE
            },
            json=test_payload,
            timeout=30
        )

        if r.status_code == 200:
            log(f"API работает ✓", "SUCCESS")
        elif r.status_code == 401:
            log("Неверный API ключ!", "ERROR")
            return False
        elif r.status_code == 402:
            log("Недостаточно кредитов", "ERROR")
            return False
        elif r.status_code == 404:
            log(f"Модель {MODEL_NAME} не найдена", "ERROR")
            return False
        else:
            log(f"Ошибка API: {r.status_code} - {r.text[:200]}", "WARN")
    except Exception as e:
        log(f"Не удалось подключиться: {e}", "ERROR")
        return False

    try:
        pyautogui.position()
        pyautogui.screenshot()
        log("Мышь и скриншоты работают ✓", "SUCCESS")
    except Exception as e:
        log(f"Ошибка: {e}", "ERROR")
        return False

    if DEBUG:
        os.makedirs(DEBUG_DIR, exist_ok=True)

    print()
    log(f"Модель: {MODEL_NAME}")
    log(f"Reasoning: {'ON (effort=' + REASONING_EFFORT + ')' if ENABLE_REASONING else 'OFF'}")
    log(f"Скриншот: {SCREEN_WIDTH}px")
    log(f"Максимум шагов: {MAX_STEPS}")
    print()
    return True


# ───────────────────────────────────────────────────────
#                  РАБОТА С ЭКРАНОМ
# ───────────────────────────────────────────────────────

def take_screenshot():
    full_screenshot = pyautogui.screenshot()
    full_w, full_h = full_screenshot.size

    if full_w > SCREEN_WIDTH:
        ratio = SCREEN_WIDTH / full_w
        new_h = int(full_h * ratio)
        model_screenshot = full_screenshot.resize((SCREEN_WIDTH, new_h), Image.LANCZOS)
    else:
        model_screenshot = full_screenshot.copy()

    model_w, model_h = model_screenshot.size
    scale_x = full_w / model_w
    scale_y = full_h / model_h

    buffered = io.BytesIO()
    model_screenshot.save(buffered, format="JPEG", quality=85, optimize=True)
    b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return b64, full_screenshot, model_screenshot, scale_x, scale_y


def screen_changed(new_screenshot):
    global previous_screenshot
    if previous_screenshot is None:
        previous_screenshot = new_screenshot
        return True
    try:
        if previous_screenshot.size != new_screenshot.size:
            previous_screenshot = new_screenshot
            return True
        diff = ImageChops.difference(previous_screenshot, new_screenshot)
        bbox = diff.getbbox()
        previous_screenshot = new_screenshot
        return bbox is not None
    except Exception:
        previous_screenshot = new_screenshot
        return True


# ───────────────────────────────────────────────────────
#      ПРОМПТЫ (расширенные)
# ───────────────────────────────────────────────────────

def build_system_prompt():
    return """You are an expert desktop computer control agent with advanced vision, reasoning, and full keyboard/mouse control capabilities.

Your capabilities:
- Analyze screenshots with pixel-perfect precision
- Reason about UI elements and their locations
- Plan multi-step actions
- Track progress through conversation history
- Full mouse control: click, double-click, right-click, DRAG & DROP
- Full keyboard control: any key, any combination, key hold/release

Available actions:
- click(x, y): Left-click
- right_click(x, y): Right-click
- double_click(x, y): Double-click
- drag(x, y, to_x, to_y, button="left", duration=0.5): Drag from (x,y) to (to_x,to_y)
- mouse_down(x, y, button="left"): Press and HOLD mouse button
- mouse_up(x, y, button="left"): Release mouse button
- type_text(text): Type into focused field
- press_key(key): Press any single key
- hotkey(keys): Press key combination (e.g., ctrl+shift+alt+f12)
- key_down(key): Press and HOLD a key
- key_up(key): Release a held key
- scroll_percent(percent, direction, x, y): Scroll by percentage of screen. percent=1-100, direction="up"/"down"/"left"/"right"
- scroll_down(x, y, clicks=3): Scroll DOWN at coordinates (small precise scrolling)
- scroll_up(x, y, clicks=3): Scroll UP at coordinates
- scroll_left(x, y, clicks=3): Scroll LEFT
- scroll_right(x, y, clicks=3): Scroll RIGHT
- wait: Wait for updates
- finish(reason): Task complete

SCROLL RULES (CRITICAL):
1. For LARGE scrolling (half screen or more): use scroll_percent with percent 50-80
2. For SMALL scrolling (a few lines): use scroll_down/scroll_up with clicks 1-3
3. scroll_percent example: {{"action":"scroll_percent", "percent":70, "direction":"down", "x":640, "y":400}}
4. Always specify coordinates in the CENTER of the content area
5. Do NOT use large clicks values (more than 5) with scroll_down/up - use scroll_percent instead

ALL SUPPORTED KEYS (use exact names):
Letters: a-z
Numbers: 0-9, numpad0-numpad9
Function: f1-f24
Arrows: up, down, left, right
Modifiers: ctrl, shift, alt, win
Special: enter, return, escape, tab, backspace, delete, insert, space
Navigation: home, end, pageup, pagedown, printscreen, scrolllock, pause, capslock, numlock
Media: volumeup, volumedown, volumemute, playpause, nexttrack, prevtrack
Punctuation: minus, equals, leftbracket, rightbracket, backslash, semicolon, apostrophe, comma, period, slash

DRAG & DROP RULES:
1. (x, y) is where you CLICK AND HOLD (start point - the object to drag)
2. (to_x, to_y) is where you RELEASE (destination)
3. Use duration 0.3-1.0 for smooth movement
4. Use button="left" for most operations, "right" for right-drag

KEY COMBINATION RULES:
- Use "+" to combine keys: ctrl+shift+a, ctrl+alt+delete, win+shift+s
- Maximum 5 keys in one combination

CRITICAL:
1. Coordinates MUST be within screenshot dimensions
2. Aim for EXACT CENTER of target elements
3. Output only ONE action per response
4. On Windows use ctrl (not cmd), win for Windows key
5. Be precise - pixels matter!"""


def build_user_prompt(task, step, img_w, img_h, action_history_text):
    return f"""Current screenshot: {img_w} x {img_h} pixels

TASK: {task}
STEP: {step} of {MAX_STEPS}
PREVIOUS ACTIONS: {action_history_text if action_history_text else "none"}

Think step by step:
1. What do you see in the screenshot?
2. What is the current state of the task?
3. What specific element do you need to interact with?
4. What are its EXACT pixel coordinates?
5. What is the best next action?

Respond ONLY with valid JSON examples:

{{"thought":"...", "action":"click", "x":500, "y":300, "text":""}}
{{"thought":"...", "action":"drag", "x":100, "y":200, "to_x":500, "to_y":400, "text":"left"}}
{{"thought":"...", "action":"mouse_down", "x":100, "y":200, "text":"left"}}
{{"thought":"...", "action":"mouse_up", "x":500, "y":400, "text":"left"}}
{{"thought":"...", "action":"type_text", "x":0, "y":0, "text":"hello world"}}
{{"thought":"...", "action":"press_key", "x":0, "y":0, "text":"f5"}}
{{"thought":"...", "action":"press_key", "x":0, "y":0, "text":"numpad5"}}
{{"thought":"...", "action":"hotkey", "x":0, "y":0, "text":"ctrl+shift+alt+f12"}}
{{"thought":"...", "action":"hotkey", "x":0, "y":0, "text":"win+shift+s"}}
{{"thought":"...", "action":"key_down", "x":0, "y":0, "text":"shift"}}
{{"thought":"...", "action":"key_up", "x":0, "y":0, "text":"shift"}}
{{"thought":"...", "action":"scroll_down", "x":640, "y":400, "text":"3"}}
{{"thought":"...", "action":"scroll_up", "x":640, "y":400, "text":"5"}}
{{"thought":"Task complete", "action":"finish", "x":0, "y":0, "text":"", "reason":"done"}}

Note: For drag/mouse_down/mouse_up, the 'text' field holds the button name: "left", "right", or "middle".
For press_key/hotkey/key_down/key_up, the 'text' field holds the key name(s).

JSON only, no markdown."""


# ───────────────────────────────────────────────────────
#       ЗАПРОС К МОДЕЛИ С REASONING CONTINUITY
# ───────────────────────────────────────────────────────

def ask_agent(task, image_b64, step, action_history_text, img_w, img_h):
    global conversation_history

    if step == 1 or not conversation_history:
        conversation_history = [
            {"role": "system", "content": build_system_prompt()}
        ]

    user_message = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
            },
            {
                "type": "text",
                "text": build_user_prompt(task, step, img_w, img_h, action_history_text)
            }
        ]
    }

    conversation_history.append(user_message)

    if len(conversation_history) > 2 + MAX_HISTORY * 2:
        conversation_history = [conversation_history[0]] + conversation_history[-(MAX_HISTORY * 2):]

    payload = {
        "model": MODEL_NAME,
        "messages": conversation_history,
        "max_tokens": 2048,
        "temperature": 0.1
    }

    if ENABLE_REASONING:
        payload["reasoning"] = {
            "enabled": True,
            "effort": REASONING_EFFORT
        }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": HTTP_REFERRER,
        "X-Title": APP_TITLE
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            log(f"Запрос к API (попытка {attempt + 1})...", "API")
            response = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()

                usage = data.get("usage", {})
                if "cost" in usage:
                    cost = usage["cost"]
                    global total_cost
                    total_cost += cost
                    log(f"Токены: {usage.get('prompt_tokens', 0)} in / {usage.get('completion_tokens', 0)} out | ${cost:.6f}",
                        "API")

                choice = data["choices"][0]
                message = choice["message"]
                content = message.get("content", "").strip()

                reasoning_details = message.get("reasoning_details")
                reasoning = message.get("reasoning")

                if reasoning_details:
                    if isinstance(reasoning_details, list):
                        for r in reasoning_details:
                            if isinstance(r, dict):
                                text = r.get("text", r.get("content", ""))
                                if text:
                                    log(f"💭 {text[:300]}", "REASONING")
                    elif isinstance(reasoning_details, str):
                        log(f"💭 {reasoning_details[:300]}", "REASONING")
                elif reasoning:
                    if isinstance(reasoning, str):
                        log(f"💭 {reasoning[:300]}", "REASONING")

                assistant_message = {"role": "assistant", "content": content}
                if reasoning_details:
                    assistant_message["reasoning_details"] = reasoning_details
                elif reasoning:
                    assistant_message["reasoning"] = reasoning

                conversation_history.append(assistant_message)

                start = content.find('{')
                end = content.rfind('}') + 1

                if start != -1 and end != -1:
                    json_str = content[start:end]
                    try:
                        result = json.loads(json_str)
                        thought = result.get("thought", "")
                        if thought:
                            log(f"💭 Thought: {thought[:300]}", "REASONING")
                        return result
                    except json.JSONDecodeError as e:
                        log(f"JSON parse error: {e}", "WARN")
                        log(f"Raw: {json_str[:200]}", "DEBUG")
                else:
                    log(f"JSON не найден", "WARN")
                    log(f"Content: {content[:300]}", "DEBUG")

            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait_time = int(retry_after)
                else:
                    wait_time = min(30 * (2 ** attempt), 120)
                log(f"⚠ Rate limit! Жду {wait_time}с...", "WARN")
                for i in range(wait_time, 0, -1):
                    print(f"    ⏳ {i}с... ", end="\r")
                    time.sleep(1)
                print()
                continue
            elif response.status_code == 400:
                error_text = response.text[:300]
                log(f"Bad request: {error_text}", "ERROR")
                if "reasoning" in error_text.lower():
                    log("Повторяю без reasoning...", "WARN")
                    payload.pop("reasoning", None)
                    continue
                return None
            elif response.status_code == 402:
                log("Недостаточно кредитов", "ERROR")
                return None
            else:
                log(f"HTTP {response.status_code}: {response.text[:200]}", "ERROR")

        except requests.exceptions.Timeout:
            log(f"Timeout (попытка {attempt + 1})", "WARN")
        except requests.exceptions.ConnectionError:
            log("Потеряна связь", "ERROR")
            return None
        except Exception as e:
            log(f"Ошибка: {e}", "WARN")

        if attempt < MAX_RETRIES:
            time.sleep(2)

    return None


# ───────────────────────────────────────────────────────
#         ВЕРИФИКАЦИЯ И ВЫПОЛНЕНИЕ ДЕЙСТВИЙ
# ───────────────────────────────────────────────────────

def verify_coordinates(x, y, img_w, img_h):
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None, None, "не числовые"

    x, y = float(x), float(y)

    if 0 <= x <= 1000 and 0 <= y <= 1000 and (x > img_w or y > img_h):
        nx = x / 1000.0 * img_w
        ny = y / 1000.0 * img_h
        log(f"Нормализовано (0-1000): ({nx:.0f},{ny:.0f})", "DEBUG")
        return int(nx), int(ny), "нормализовано"

    if 0 <= x <= 1 and 0 <= y <= 1:
        px = x * img_w
        py = y * img_h
        log(f"Проценты: ({px:.0f},{py:.0f})", "DEBUG")
        return int(px), int(py), "проценты"

    if x < 0 or x > img_w or y < 0 or y > img_h:
        log(f"Вне границ: ({x},{y}) при ({img_w}x{img_h})", "WARN")
        x = max(0, min(x, img_w - 1))
        y = max(0, min(y, img_h - 1))
        return int(x), int(y), "ограничено"

    return int(x), int(y), "OK"


def execute_action(action_data, scale_x, scale_y, img_w, img_h, full_screenshot):
    global running, step_counter

    if not action_data or not running:
        return None

    action = action_data.get("action", "").lower().strip()

    def calculate_clicks_from_percent(percent, direction="vertical"):
        """
        Вычисляет количество кликов колеса для прокрутки на заданный процент экрана.

        Args:
            percent: процент экрана (0-100)
            direction: "vertical" или "horizontal"

        Returns:
            количество кликов колеса (1-50)
        """
        # Определяем размер экрана в нужном направлении
        screen_size = REAL_H if direction == "vertical" else REAL_W

        # Сколько пикселей нужно прокрутить
        target_pixels = (percent / 100.0) * screen_size

        # Сколько кликов колеса нужно
        clicks = target_pixels / SCROLL_PIXELS_PER_CLICK

        # Округляем и ограничиваем
        clicks = max(1, min(int(round(clicks)), 50))

        return clicks

    def scroll_at_point(x, y, clicks, direction="down"):
        """
        Надёжная прокрутка с использованием 4 методов по приоритету:
        1. pynput (самый надёжный)
        2. Win32 SendInput
        3. pyautogui
        4. Клавиши PageUp/PageDown/стрелки (работает везде)
        """
        x = max(0, min(int(x), REAL_W - 1))
        y = max(0, min(int(y), REAL_H - 1))
        clicks = max(1, min(int(clicks), 20))

        log(f"📜 {direction} на {clicks} кликов в точке ({x},{y})", "DEBUG")

        # ШАГ 1: Двигаем мышь в нужную точку (без клика, чтобы не сломать интерфейс)
        pyautogui.moveTo(x, y, duration=MOUSE_SPEED)
        time.sleep(0.15)

        # Определяем направление
        dy = -clicks if direction == "down" else clicks
        dx = -clicks if direction == "left" else clicks
        is_horizontal = direction in ("left", "right")

        # ── МЕТОД 1: pynput (лучший) ──
        try:
            from pynput.mouse import Controller as MouseController
            mouse = MouseController()
            mouse.position = (x, y)
            time.sleep(0.1)

            if is_horizontal:
                # Горизонтальный скролл через Shift + Wheel
                pyautogui.keyDown('shift')
                mouse.scroll(dx, 0)
                pyautogui.keyUp('shift')
            else:
                mouse.scroll(0, dy)

            time.sleep(0.2)
            log(f"✓ Метод 1 (pynput) сработал", "SUCCESS")
            return True
        except ImportError:
            log("pynput не установлен, пробую следующий метод", "DEBUG")
        except Exception as e:
            log(f"pynput failed: {e}", "DEBUG")

        # ── МЕТОД 2: Win32 SendInput ──
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                INPUT_MOUSE = 0
                MOUSEEVENTF_WHEEL = 0x0800
                MOUSEEVENTF_HWHEEL = 0x1000
                WHEEL_DELTA = 120

                class MOUSEINPUT(ctypes.Structure):
                    _fields_ = [
                        ("dx", wintypes.LONG),
                        ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD),
                        ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
                    ]

                class INPUT_UNION(ctypes.Union):
                    _fields_ = [("mi", MOUSEINPUT)]

                class INPUT(ctypes.Structure):
                    _fields_ = [
                        ("type", wintypes.DWORD),
                        ("union", INPUT_UNION),
                    ]

                wheel_delta = (dy if not is_horizontal else dx) * WHEEL_DELTA

                inp = INPUT()
                inp.type = INPUT_MOUSE
                inp.union.mi.dwFlags = MOUSEEVENTF_HWHEEL if is_horizontal else MOUSEEVENTF_WHEEL
                inp.union.mi.mouseData = wheel_delta & 0xFFFFFFFF

                # Несколько событий подряд для надёжности
                for _ in range(clicks):
                    result = ctypes.windll.user32.SendInput(
                        1, ctypes.byref(inp), ctypes.sizeof(INPUT)
                    )
                    if result == 0:
                        raise Exception(f"SendInput failed, error={ctypes.get_last_error()}")
                    time.sleep(0.03)

                log(f"✓ Метод 2 (SendInput) сработал", "SUCCESS")
                return True
            except Exception as e:
                log(f"SendInput failed: {e}", "DEBUG")

        # ── МЕТОД 3: pyautogui (запасной) ──
        try:
            amount = dy if not is_horizontal else dx
            if is_horizontal:
                try:
                    pyautogui.hscroll(amount)
                except AttributeError:
                    pyautogui.scroll(amount)
            else:
                pyautogui.scroll(amount)
            log(f"✓ Метод 3 (pyautogui) сработал", "SUCCESS")
            return True
        except Exception as e:
            log(f"pyautogui failed: {e}", "DEBUG")

        # ── МЕТОД 4: Клавиши (работает почти везде) ──
        try:
            log("Fallback на клавиши", "DEBUG")

            # Сначала кликаем, чтобы окно получило фокус
            pyautogui.click()
            time.sleep(0.1)

            if direction == "down":
                for _ in range(min(clicks, 10)):
                    pyautogui.press("pagedown")
                    time.sleep(0.05)
            elif direction == "up":
                for _ in range(min(clicks, 10)):
                    pyautogui.press("pageup")
                    time.sleep(0.05)
            elif direction == "left":
                for _ in range(min(clicks * 3, 30)):
                    pyautogui.press("left")
                    time.sleep(0.02)
            elif direction == "right":
                for _ in range(min(clicks * 3, 30)):
                    pyautogui.press("right")
                    time.sleep(0.02)

            log(f"✓ Метод 4 (клавиши) сработал", "SUCCESS")
            return True
        except Exception as e:
            log(f"Клавиши тоже не сработали: {e}", "ERROR")
            return False
        прокрути
        эту
        страницу
        вверх

    def resolve_key(key_name):
        key_name = key_name.lower().strip()
        return KEY_ALIASES.get(key_name, key_name)

    def to_screen_coords(x, y):
        vx, vy, status = verify_coordinates(x, y, img_w, img_h)
        if vx is None:
            return None, None
        if status != "OK":
            log(f"Скорректированы: {status}", "WARN")
        real_x = int(vx * scale_x)
        real_y = int(vy * scale_y)
        real_x = max(0, min(real_x, REAL_W - 1))
        real_y = max(0, min(real_y, REAL_H - 1))
        return real_x, real_y

    try:
        # ── КЛИКИ ──
        if action in ("click", "right_click", "double_click", "left_click"):
            raw_x = action_data.get("x", 0)
            raw_y = action_data.get("y", 0)

            real_x, real_y = to_screen_coords(raw_x, raw_y)
            if real_x is None:
                return None

            log(f"🎯 ({raw_x},{raw_y}) → ({real_x},{real_y})")

            if DEBUG:
                save_debug_screenshot(full_screenshot.copy(), real_x, real_y, action, f"step{step_counter}")

            if CLICK_DELAY > 0:
                log(f"Клик через {CLICK_DELAY}с (Ctrl+C = отмена)")
                for i in range(CLICK_DELAY, 0, -1):
                    if not running:
                        return None
                    print(f"    {i}...", end="\r")
                    time.sleep(1)
                print("    " + " " * 20, end="\r")

            pyautogui.moveTo(real_x, real_y, duration=MOUSE_SPEED)
            time.sleep(0.1)

            pos = pyautogui.position()
            if abs(pos.x - real_x) > 3 or abs(pos.y - real_y) > 3:
                pyautogui.moveTo(real_x, real_y, duration=0.2)
                time.sleep(0.1)

            if action == "right_click":
                pyautogui.rightClick()
                desc = f"right_click({real_x},{real_y})"
            elif action == "double_click":
                pyautogui.doubleClick()
                desc = f"double_click({real_x},{real_y})"
            else:
                pyautogui.click()
                desc = f"click({real_x},{real_y})"

            log(f"✓ {desc}", "SUCCESS")
            return desc

        # ── DRAG & DROP ──
        elif action == "drag":
            raw_x = action_data.get("x", 0)
            raw_y = action_data.get("y", 0)
            raw_to_x = action_data.get("to_x", action_data.get("x2", 0))
            raw_to_y = action_data.get("to_y", action_data.get("y2", 0))
            button = action_data.get("text", action_data.get("button", "left")).lower()
            duration = float(action_data.get("duration", 0.5))

            if button not in ("left", "right", "middle"):
                button = "left"

            start_x, start_y = to_screen_coords(raw_x, raw_y)
            if start_x is None:
                return None

            end_x, end_y = to_screen_coords(raw_to_x, raw_to_y)
            if end_x is None:
                return None

            log(f"🎯 Drag: ({start_x},{start_y}) → ({end_x},{end_y}) [{button}]")

            if DEBUG:
                debug_img = full_screenshot.copy()
                draw = ImageDraw.Draw(debug_img)
                r = 15
                draw.ellipse([start_x - r, start_y - r, start_x + r, start_y + r], outline="blue", width=3)
                draw.text((start_x + 20, start_y - 10), f"FROM ({start_x},{start_y})", fill="blue")
                draw.ellipse([end_x - r, end_y - r, end_x + r, end_y + r], outline="red", width=3)
                draw.text((end_x + 20, end_y - 10), f"TO ({end_x},{end_y})", fill="red")
                draw.line([start_x, start_y, end_x, end_y], fill="purple", width=2)

                os.makedirs(DEBUG_DIR, exist_ok=True)
                filename = f"{step_counter:03d}_drag.png"
                debug_img.save(os.path.join(DEBUG_DIR, filename))
                log(f"📷 Drag визуализация сохранена", "DEBUG")

            if CLICK_DELAY > 0:
                log(f"Drag через {CLICK_DELAY}с (Ctrl+C = отмена)")
                for i in range(CLICK_DELAY, 0, -1):
                    if not running:
                        return None
                    print(f"    {i}...", end="\r")
                    time.sleep(1)
                print("    " + " " * 20, end="\r")

            pyautogui.moveTo(start_x, start_y, duration=MOUSE_SPEED)
            time.sleep(0.1)

            dx = end_x - start_x
            dy = end_y - start_y
            pyautogui.drag(dx, dy, duration=duration, button=button)

            desc = f"drag({start_x},{start_y}→{end_x},{end_y},{button})"
            log(f"✓ {desc}", "SUCCESS")
            return desc

        # ── MOUSE DOWN / UP ──
        elif action == "mouse_down":
            raw_x = action_data.get("x", 0)
            raw_y = action_data.get("y", 0)
            button = action_data.get("text", action_data.get("button", "left")).lower()
            if button not in ("left", "right", "middle"):
                button = "left"

            real_x, real_y = to_screen_coords(raw_x, raw_y)
            if real_x is None:
                return None

            log(f"🎯 Mouse DOWN: ({real_x},{real_y}) [{button}]")

            pyautogui.moveTo(real_x, real_y, duration=MOUSE_SPEED)
            time.sleep(0.1)
            pyautogui.mouseDown(button=button)

            desc = f"mouse_down({real_x},{real_y},{button})"
            log(f"✓ {desc} (удерживаю)", "SUCCESS")
            return desc

        elif action == "mouse_up":
            raw_x = action_data.get("x", 0)
            raw_y = action_data.get("y", 0)
            button = action_data.get("text", action_data.get("button", "left")).lower()
            if button not in ("left", "right", "middle"):
                button = "left"

            real_x, real_y = to_screen_coords(raw_x, raw_y)
            if real_x is None:
                return None

            log(f"🎯 Mouse UP: ({real_x},{real_y}) [{button}]")

            pyautogui.moveTo(real_x, real_y, duration=MOUSE_SPEED)
            time.sleep(0.1)
            pyautogui.mouseUp(button=button)

            desc = f"mouse_up({real_x},{real_y},{button})"
            log(f"✓ {desc}", "SUCCESS")
            return desc

        # ── ТЕКСТ (УНИВЕРСАЛЬНЫЙ ВВОД) ──
        elif action == "type_text":
            text = action_data.get("text", "")
            if not text:
                return None

            log(f"⌨ Текст: '{text[:50]}{'...' if len(text) > 50 else ''}'")

            # 1. Сбрасываем все модификаторы
            for mod in ["shift", "shiftleft", "shiftright", "ctrl", "ctrlleft", "ctrlright",
                        "alt", "altleft", "altright"]:
                try:
                    pyautogui.keyUp(mod)
                except Exception:
                    pass

            time.sleep(0.15)

            # 2. ВСЕГДА используем буфер обмена — это 100% надёжно
            # Работает с любой раскладкой, любыми символами, любой длиной
            old_clip = ""
            try:
                if HAS_PYPERCLIP:
                    old_clip = pyperclip.paste() or ""
            except Exception:
                old_clip = ""

            if not copy_to_clipboard(text):
                log("Не удалось скопировать в буфер", "ERROR")
                return None

            time.sleep(0.1)

            # 3. Вставка через горячие клавиши
            paste_mod = 'command' if sys.platform == "darwin" else 'ctrl'

            # Убеждаемся, что никакие другие модификаторы не зажаты
            pyautogui.keyUp('shift')
            pyautogui.keyUp('alt')
            time.sleep(0.05)

            pyautogui.hotkey(paste_mod, 'v')
            time.sleep(0.2)

            # 4. Восстанавливаем буфер пользователя
            if old_clip:
                def _restore():
                    time.sleep(1.5)
                    try:
                        copy_to_clipboard(old_clip)
                    except Exception:
                        pass

                import threading
                threading.Thread(target=_restore, daemon=True).start()

            desc = f"type('{text[:30]}')" if len(text) <= 30 else f"type('{text[:30]}...')"
            log(f"✓ Вставлено через буфер", "SUCCESS")
            return desc

        # ── ОДИНАРНАЯ КЛАВИША ──
        elif action == "press_key":
            key_raw = action_data.get("text", action_data.get("key", ""))
            if not key_raw:
                return None
            key = resolve_key(key_raw)
            log(f"⌨ press({key})")
            try:
                pyautogui.press(key)
                return f"press({key})"
            except Exception as e:
                log(f"Клавиша '{key}' не поддерживается: {e}", "ERROR")
                return None

        # ── ГОРЯЧИЕ КЛАВИШИ ──
        elif action == "hotkey":
            keys_str = action_data.get("text", action_data.get("keys", ""))
            if not keys_str:
                return None

            if sys.platform == "darwin":
                keys_str = keys_str.replace("ctrl", "command").replace("win", "command")
            else:
                keys_str = keys_str.replace("command", "ctrl").replace("cmd", "ctrl")
                keys_str = keys_str.replace("super", "win").replace("option", "alt")

            raw_keys = [k.strip() for k in keys_str.split("+")]
            resolved_keys = [resolve_key(k) for k in raw_keys if k]

            if not resolved_keys:
                return None

            log(f"⌨ hotkey({' + '.join(resolved_keys)})")
            try:
                pyautogui.hotkey(*resolved_keys)
                return f"hotkey({' + '.join(resolved_keys)})"
            except Exception as e:
                log(f"Комбинация не поддерживается: {e}", "ERROR")
                return None

        # ── KEY DOWN / KEY UP ──
        elif action == "key_down":
            key_raw = action_data.get("text", action_data.get("key", ""))
            if not key_raw:
                return None
            key = resolve_key(key_raw)
            log(f"⌨ key_down({key}) — удерживаю")
            try:
                pyautogui.keyDown(key)
                return f"key_down({key})"
            except Exception as e:
                log(f"Клавиша не поддерживается: {e}", "ERROR")
                return None

        elif action == "key_up":
            key_raw = action_data.get("text", action_data.get("key", ""))
            if not key_raw:
                return None
            key = resolve_key(key_raw)
            log(f"⌨ key_up({key}) — отпускаю")
            try:
                pyautogui.keyUp(key)
                return f"key_up({key})"
            except Exception as e:
                log(f"Клавиша не поддерживается: {e}", "ERROR")
                return None

        # ── СКРОЛЛ ──
        elif action in ("scroll_down", "scroll_up", "scroll_left", "scroll_right"):
            raw_x = action_data.get("x", 0)
            raw_y = action_data.get("y", 0)

            # Количество кликов колеса
            raw_clicks = action_data.get("clicks", action_data.get("text", 3))
            try:
                clicks = int(raw_clicks) if raw_clicks not in (None, "") else 3
                clicks = max(1, min(clicks, 5))
            except (ValueError, TypeError):
                clicks = 3

            # Определяем координаты
            if raw_x and raw_y and (float(raw_x) != 0 or float(raw_y) != 0):
                real_x, real_y = to_screen_coords(raw_x, raw_y)
                if real_x is None:
                    # Если координаты кривые — скроллим в центре экрана
                    real_x, real_y = REAL_W // 2, REAL_H // 2
            else:
                # Координаты не указаны — центр экрана (самое безопасное)
                real_x, real_y = REAL_W // 2, REAL_H // 2
                log("Координаты не указаны, скроллю в центре экрана", "DEBUG")

            direction = action.replace("scroll_", "")
            success = scroll_at_point(real_x, real_y, clicks, direction)

            if success:
                return f"{action}({clicks}) at ({real_x},{real_y})"
            else:
                log(f"Скролл не удался", "ERROR")
                return None


        # ── ПРОКРУТКА НА ПРОЦЕНТ ЭКРАНА (НОВОЕ) ──
        elif action == "scroll_percent":
            # Получаем процент из полей
            raw_percent = action_data.get("percent", action_data.get("text", 70))
            try:
                percent = float(raw_percent) if raw_percent not in (None, "") else 50.0
                percent = max(1.0, min(percent, 100.0))  # от 1 до 100
            except (ValueError, TypeError):
                percent = 70.0

            # Направление
            direction = action_data.get("direction", "down").lower()
            if direction not in ("up", "down", "left", "right"):
                direction = "down"

            # Определяем вертикальная или горизонтальная прокрутка
            is_vertical = direction in ("up", "down")
            scroll_direction = "vertical" if is_vertical else "horizontal"

            # Вычисляем количество кликов
            clicks = calculate_clicks_from_percent(percent, scroll_direction)

            log(f"📜 Прокрутка на {percent}% экрана ({direction}) = {clicks} кликов", "DEBUG")

            # Координаты для прокрутки
            raw_x = action_data.get("x", 0)
            raw_y = action_data.get("y", 0)

            if raw_x and raw_y and (float(raw_x) != 0 or float(raw_y) != 0):
                real_x, real_y = to_screen_coords(raw_x, raw_y)
                if real_x is None:
                    real_x, real_y = REAL_W // 2, REAL_H // 2
            else:
                real_x, real_y = REAL_W // 2, REAL_H // 2

            # Выполняем прокрутку
            success = scroll_at_point(real_x, real_y, clicks, direction)

            if success:
                return f"scroll_percent({percent}% {direction})"
            else:
                log("Прокрутка не удалась", "ERROR")
                return None

        # ── ОЖИДАНИЕ ──
        elif action == "wait":
            # Безопасный парсинг длительности
            raw_duration = action_data.get("duration", action_data.get("text", ""))

            duration = 2.0  # значение по умолчанию
            if raw_duration not in (None, ""):
                try:
                    duration = float(raw_duration)
                    # Ограничиваем разумными пределами
                    duration = max(0.1, min(duration, 30.0))
                except (ValueError, TypeError):
                    log(f"Не удалось распарсить duration='{raw_duration}', использую 2с", "WARN")

            log(f"⏳ {duration}с")
            time.sleep(duration)
            return f"wait({duration}s)"

        # ── ЗАВЕРШЕНИЕ ──
        elif action == "finish":
            reason = action_data.get("reason", "Готово")
            log(f"🏁 {reason}", "SUCCESS")
            return "FINISH"

        else:
            log(f"Неизвестное действие: {action}", "WARN")
            return None

    except KeyboardInterrupt:
        raise
    except Exception as e:
        log(f"Ошибка: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return None


# ───────────────────────────────────────────────────────
#                    ГЛАВНЫЙ ЦИКЛ
# ───────────────────────────────────────────────────────

def run_agent(task):
    global action_history, running, step_counter, total_cost, conversation_history

    action_history = []
    step_counter = 0
    conversation_history = []
    start_cost = total_cost

    log(f"🚀 Задача: '{task}'")
    log(f"Модель: {MODEL_NAME}")
    log(f"Reasoning: {'ON' if ENABLE_REASONING else 'OFF'}")
    print("─" * 60)

    for step in range(1, MAX_STEPS + 1):
        if not running:
            break

        step_counter = step
        print()
        log(f"═══ Шаг {step}/{MAX_STEPS} ═══")

        img_b64, full_screenshot, model_screenshot, scale_x, scale_y = take_screenshot()
        model_w, model_h = model_screenshot.size

        log(f"Скриншот: {model_w}x{model_h}, масштаб: x{scale_x:.2f} y{scale_y:.2f}", "DEBUG")

        if DEBUG:
            save_debug_screenshot(full_screenshot.copy(), None, None, "", f"step{step}_before")

        recent_history = "; ".join(action_history[-5:]) if action_history else ""

        log("🧠 Анализирую экран с reasoning...")
        start_time = time.time()
        action_data = ask_agent(task, img_b64, step, recent_history, model_w, model_h)
        elapsed = time.time() - start_time
        log(f"⏱ {elapsed:.1f}с")

        if not action_data:
            log("Нет ответа. Повтор через 3с...", "WARN")
            time.sleep(3)
            continue

        action_type = action_data.get("action", "").lower()

        if action_type == "finish":
            execute_action(action_data, scale_x, scale_y, model_w, model_h, full_screenshot)
            print()
            log("✅ Задача завершена!", "SUCCESS")
            break

        result = execute_action(action_data, scale_x, scale_y, model_w, model_h, full_screenshot)

        if result == "FINISH":
            break

        if result:
            action_history.append(result)
        else:
            log("Действие не выполнено", "WARN")

        time.sleep(WAIT_AFTER)

        _, new_full, _, _, _ = take_screenshot()
        changed = screen_changed(new_full)
        if changed:
            log("📺 Экран изменился ✓")
        else:
            log("📺 Экран НЕ изменился ⚠", "WARN")

    else:
        log(f"⚠ Лимит {MAX_STEPS} шагов", "WARN")

    # Безопасное отпускание всех клавиш/кнопок после задачи
    try:
        for key in ["ctrl", "shift", "alt", "win", "command"]:
            try:
                pyautogui.keyUp(key)
            except Exception:
                pass
        for btn in ["left", "right", "middle"]:
            try:
                pyautogui.mouseUp(button=btn)
            except Exception:
                pass
    except Exception:
        pass

    print()
    print("═" * 60)
    log("📋 Итог:")
    log(f"   Задача: {task}")
    log(f"   Шагов: {len(action_history)}")
    log(f"   Стоимость сессии: ${total_cost - start_cost:.6f}")
    log(f"   Всего: ${total_cost:.6f}")

    if action_history:
        print()
        for i, h in enumerate(action_history, 1):
            print(f"   {i:2d}. {h}")

    print("═" * 60)

    if DEBUG:
        log(f"Скриншоты: ./{DEBUG_DIR}/", "DEBUG")

    save_log()


# ───────────────────────────────────────────────────────
#                      МЕНЮ
# ───────────────────────────────────────────────────────

def show_menu():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║   🪟 AI-Агент (расширенная версия)                 ║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║  1. Ввести задачу вручную                          ║")
    print("║  2. Пример: Открыть Калькулятор                    ║")
    print("║  3. Пример: Открыть Блокнот и написать текст       ║")
    print("║  4. Пример: Выделить текст мышью (drag)            ║")
    print("║  5. Пример: Выделить всё (Ctrl+A)                  ║")
    print("║  6. Пример: Скриншот области (Win+Shift+S)         ║")
    print("║  7. Пример: Открыть Диспетчер задач                ║")
    print("║  8. Пример: Свёрнуть все окна (Win+D)              ║")
    print("║  9. Настройки reasoning                            ║")
    print("║ 10. Настройки агента                               ║")
    print("║ 11. Выход                                          ║")
    print("╚══════════════════════════════════════════════════════╝")


def main():
    global ENABLE_REASONING, REASONING_EFFORT

    if not check_environment():
        input("\nEnter для выхода...")
        sys.exit(1)

    while True:
        show_menu()

        try:
            choice = input("\n  Выбор: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            task = input("  📝 Задача: ").strip()
            if task:
                run_agent(task)
        elif choice == "2":
            run_agent("Open Calculator")
        elif choice == "3":
            run_agent("Open Notepad, type 'Hello from AI Agent'")
        elif choice == "4":
            run_agent("Select the text on the screen by dragging the mouse over it from left to right")
        elif choice == "5":
            run_agent("Open Notepad, type some text, then select all with Ctrl+A")
        elif choice == "6":
            run_agent("Take a screenshot of a selected area using the Windows shortcut Win+Shift+S")
        elif choice == "7":
            run_agent("Open Task Manager using Ctrl+Shift+Escape")
        elif choice == "8":
            run_agent("Minimize all windows using Win+D")

        elif choice == "9":
            print(f"\n  Reasoning: {'ON' if ENABLE_REASONING else 'OFF'}")
            print(f"  Effort: {REASONING_EFFORT}")

            toggle = input("\n  Включить reasoning? (y/n) [y]: ").strip().lower()
            if toggle in ("n", "no"):
                ENABLE_REASONING = False
                log("Reasoning: OFF")
            else:
                ENABLE_REASONING = True
                log("Reasoning: ON")

                effort = input("  Effort (low/medium/high) [high]: ").strip().lower()
                if effort in ("low", "medium", "high"):
                    REASONING_EFFORT = effort
                log(f"Reasoning effort: {REASONING_EFFORT}")

        elif choice == "10":
            print(f"\n  Модель: {MODEL_NAME}")
            print(f"  Скриншот: {SCREEN_WIDTH}px")
            print(f"  Задержка: {CLICK_DELAY}с")
            print(f"  Макс. шагов: {MAX_STEPS}")

            w = input(f"\n  Ширина [{SCREEN_WIDTH}]: ").strip()
            if w.isdigit() and 400 <= int(w) <= 2560:
                globals()["SCREEN_WIDTH"] = int(w)

            d = input(f"  Задержка [{CLICK_DELAY}]: ").strip()
            if d.isdigit():
                globals()["CLICK_DELAY"] = int(d)

            m = input(f"  Модель [{MODEL_NAME}]: ").strip()
            if m:
                globals()["MODEL_NAME"] = m

        elif choice == "11":
            log("Выход")
            save_log()
            print(f"\n  💰 Всего: ${total_cost:.6f}")
            break

        else:
            log("Неверный выбор", "WARN")

        print()
        try:
            input("  Enter для продолжения...")
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Критическая ошибка: {e}", "ERROR")
        import traceback

        traceback.print_exc()
        save_log()
        input("\nEnter для выхода...")