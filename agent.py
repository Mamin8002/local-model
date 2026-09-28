#!/usr/bin/env python3
"""
AI-Агент через OpenRouter API
Модель: qwen/qwen3.8-27b (Vision + Reasoning)
"""

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

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
HTTP_REFERRER = "http://localhost:8080"
APP_TITLE = "AI-Agent-Qwen3.8"

# ── Модель Qwen3.8 27B с Vision + Reasoning ──
MODEL_NAME = "stealth/space-bunny-alpha"

# ── Reasoning настройки ──
ENABLE_REASONING = True
REASONING_EFFORT = "high"  # "low", "medium", "high"

# ── Агент ──
SCREEN_WIDTH = 1280
CLICK_DELAY = 2
MAX_STEPS = 1000
WAIT_AFTER = 1.5
MAX_RETRIES = 2
TIMEOUT = 90
MAX_HISTORY = 100  # Сколько предыдущих шагов хранить в контексте

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

# ═══════════════════════════════════════════════════════
#   История для reasoning continuity (сохраняем между шагами)
# ═══════════════════════════════════════════════════════
conversation_history = []


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
    print("║   🪟 AI-Агент: Qwen3.8-27B Vision + Reasoning     ║")
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

    # Тест модели с изображением
    log("Проверяю Vision + Reasoning...")
    try:
        test_payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What color is this text: RED?"}
                    ]
                }
            ],
            "max_tokens": 50
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
            data = r.json()
            if "reasoning_details" in data["choices"][0]["message"]:
                log(f"Reasoning поддерживается ✓", "SUCCESS")
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
    log(f"Reasoning: {'ON (effort={REASONING_EFFORT})' if ENABLE_REASONING else 'OFF'}")
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
#      ПРОМПТЫ ДЛЯ QWEN3.8 (VISION + REASONING)
# ───────────────────────────────────────────────────────

def build_system_prompt():
    return """You are an expert desktop computer control agent with advanced vision and reasoning capabilities. You can see screenshots and must complete tasks step by step with pixel-perfect precision.

Your capabilities:
- Analyze screenshots with high accuracy
- Reason about UI elements and their locations
- Plan multi-step actions
- Track progress through conversation history

Available actions:
- click(x, y): Left-click at pixel coordinates
- right_click(x, y): Right-click
- double_click(x, y): Double-click
- type_text(text): Type into focused field
- press_key(key): Press single key (enter, escape, tab, backspace, delete, space, up, down, left, right, home, end, f1-f12)
- hotkey(keys): Key combination (ctrl+c, ctrl+v, ctrl+z, ctrl+a, alt+tab, win+d, alt+f4, ctrl+shift+escape)
- scroll_down / scroll_up: Scroll page
- wait: Wait for updates
- finish(reason): Task complete

CRITICAL RULES:
1. Look at the screenshot VERY carefully - identify exact pixel positions
2. Coordinates MUST be within screenshot dimensions
3. Aim for EXACT CENTER of target elements (buttons, icons, fields)
4. Output only ONE action per response
5. Use reasoning to plan your next step
6. On Windows use ctrl (not cmd), win for Windows key
7. If stuck or task impossible, use finish with explanation
8. Be extremely precise - pixels matter!"""


def build_user_prompt(task, step, img_w, img_h, action_history_text):
    return f"""Current screenshot: {img_w} x {img_h} pixels

TASK: {task}
STEP: {step} of {MAX_STEPS}
PREVIOUS ACTIONS: {action_history_text if action_history_text else "none"}

Think step by step using your reasoning capabilities:
1. What do you see in the screenshot?
2. What is the current state of the task?
3. What specific element do you need to interact with?
4. What are its EXACT pixel coordinates?
5. What is the best next action?

Respond ONLY with valid JSON:
{{
  "thought": "Step-by-step reasoning about what I see and what to do next",
  "action": "click",
  "x": 500,
  "y": 300,
  "text": ""
}}

For type_text: {{"thought":"...", "action":"type_text", "x":0, "y":0, "text":"hello"}}
For press_key: {{"thought":"...", "action":"press_key", "x":0, "y":0, "text":"enter"}}
For hotkey: {{"thought":"...", "action":"hotkey", "x":0, "y":0, "text":"ctrl+c"}}
For finish: {{"thought":"Task complete because...", "action":"finish", "x":0, "y":0, "text":"", "reason":"done"}}

JSON only, no markdown."""


# ───────────────────────────────────────────────────────
#       ЗАПРОС К QWEN3.8 С REASONING CONTINUITY
# ───────────────────────────────────────────────────────

def ask_agent(task, image_b64, step, action_history_text, img_w, img_h):
    """
    Запрос к Qwen3.8 с сохранением reasoning_details между шагами
    для непрерывности мышления модели.
    """
    global conversation_history

    # Инициализируем разговор при первом шаге новой задачи
    if step == 1 or not conversation_history:
        conversation_history = [
            {
                "role": "system",
                "content": build_system_prompt()
            }
        ]

    # Формируем сообщение пользователя со скриншотом
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"
                }
            },
            {
                "type": "text",
                "text": build_user_prompt(task, step, img_w, img_h, action_history_text)
            }
        ]
    }

    # Добавляем в историю
    conversation_history.append(user_message)

    # Ограничиваем размер истории (сохраняем system + последние N сообщений)
    if len(conversation_history) > 2 + MAX_HISTORY * 2:
        conversation_history = [conversation_history[0]] + conversation_history[-(MAX_HISTORY * 2):]

    payload = {
        "model": MODEL_NAME,
        "messages": conversation_history,
        "max_tokens": 2048,
        "temperature": 0.1
    }

    # Включаем reasoning для Qwen3.8
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

                # Считаем стоимость
                usage = data.get("usage", {})
                if "cost" in usage:
                    cost = usage["cost"]
                    global total_cost
                    total_cost += cost
                    log(f"Токены: {usage.get('prompt_tokens', 0)} in / {usage.get('completion_tokens', 0)} out | ${cost:.6f}",
                        "API")

                # Извлекаем ответ модели
                choice = data["choices"][0]
                message = choice["message"]
                content = message.get("content", "").strip()

                # Извлекаем reasoning_details для сохранения
                reasoning_details = message.get("reasoning_details")
                reasoning = message.get("reasoning")

                # Логируем процесс рассуждения
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

                # Сохраняем ответ модели в историю (С reasoning_details!)
                assistant_message = {
                    "role": "assistant",
                    "content": content
                }
                # Передаём reasoning_details БЕЗ ИЗМЕНЕНИЙ для continuity
                if reasoning_details:
                    assistant_message["reasoning_details"] = reasoning_details
                elif reasoning:
                    assistant_message["reasoning"] = reasoning

                conversation_history.append(assistant_message)

                # Извлекаем JSON из content
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
                log("Rate limit. Жду 5с...", "WARN")
                time.sleep(5)
                continue
            elif response.status_code == 400:
                error_text = response.text[:300]
                log(f"Bad request: {error_text}", "ERROR")
                # Если ошибка связана с reasoning, пробуем без него
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

    # Нормализованные (0-1000)?
    if 0 <= x <= 1000 and 0 <= y <= 1000 and (x > img_w or y > img_h):
        nx = x / 1000.0 * img_w
        ny = y / 1000.0 * img_h
        log(f"Нормализовано (0-1000): ({nx:.0f},{ny:.0f})", "DEBUG")
        return int(nx), int(ny), "нормализовано"

    # Проценты (0-1)?
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

    try:
        # ── КЛИКИ ──
        if action in ("click", "right_click", "double_click", "left_click"):
            raw_x = action_data.get("x", 0)
            raw_y = action_data.get("y", 0)

            vx, vy, status = verify_coordinates(raw_x, raw_y, img_w, img_h)
            if vx is None:
                log(f"Некорректные координаты: {raw_x}, {raw_y}", "ERROR")
                return None

            if status != "OK":
                log(f"Скорректированы: {status}", "WARN")

            real_x = int(vx * scale_x)
            real_y = int(vy * scale_y)
            real_x = max(0, min(real_x, REAL_W - 1))
            real_y = max(0, min(real_y, REAL_H - 1))

            log(f"🎯 ({vx},{vy}) → ({real_x},{real_y})")

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

        # ── ТЕКСТ ──
        elif action == "type_text":
            text = action_data.get("text", "")
            if not text:
                return None
            log(f"⌨ '{text}'")
            time.sleep(0.3)

            has_non_ascii = any(ord(c) > 127 for c in text)
            if has_non_ascii:
                if copy_to_clipboard(text):
                    time.sleep(0.2)
                    hotkey = 'command' if sys.platform == "darwin" else 'ctrl'
                    pyautogui.hotkey(hotkey, 'v')
                    time.sleep(0.2)
                else:
                    log("Ошибка буфера", "ERROR")
                    return None
            else:
                pyautogui.write(text, interval=0.03)

            return f"type('{text}')"

        # ── КЛАВИША ──
        elif action == "press_key":
            key = action_data.get("text", action_data.get("key", ""))
            if not key:
                return None
            key = key.lower().strip()
            key_map = {
                "enter": "enter", "return": "enter", "esc": "escape",
                "tab": "tab", "backspace": "backspace",
                "delete": "delete", "del": "delete", "space": "space",
                "up": "up", "down": "down", "left": "left", "right": "right",
                "home": "home", "end": "end",
                "pageup": "pageup", "pagedown": "pagedown",
            }
            key = key_map.get(key, key)
            log(f"⌨ {key}")
            pyautogui.press(key)
            return f"press({key})"

        # ── ГОРЯЧИЕ КЛАВИШИ ──
        elif action == "hotkey":
            keys_str = action_data.get("text", action_data.get("keys", ""))
            if not keys_str:
                return None
            keys_str = keys_str.lower()
            if sys.platform == "darwin":
                keys_str = keys_str.replace("ctrl", "command").replace("win", "command")
            else:
                keys_str = keys_str.replace("command", "ctrl").replace("cmd", "ctrl")
                keys_str = keys_str.replace("super", "win").replace("option", "alt")

            log(f"⌨ {keys_str}")
            key_list = [k.strip() for k in keys_str.split("+")]
            pyautogui.hotkey(*key_list)
            return f"hotkey({keys_str})"

        # ── СКРОЛЛ ──
        elif action == "scroll_down":
            log("📜 ↓")
            pyautogui.scroll(-5)
            return "scroll_down"
        elif action == "scroll_up":
            log("📜 ↑")
            pyautogui.scroll(5)
            return "scroll_up"

        # ── ОЖИДАНИЕ ──
        elif action == "wait":
            log("⏳ 2с")
            time.sleep(2)
            return "wait"

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
        return None


# ───────────────────────────────────────────────────────
#                    ГЛАВНЫЙ ЦИКЛ
# ───────────────────────────────────────────────────────

def run_agent(task):
    global action_history, running, step_counter, total_cost, conversation_history

    action_history = []
    step_counter = 0
    conversation_history = []  # Сбрасываем разговор для новой задачи
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
    print("║   🪟 AI-Агент: Qwen3.8-27B Vision + Reasoning    ║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║  1. Ввести задачу вручную                          ║")
    print("║  2. Пример: Открыть Калькулятор                    ║")
    print("║  3. Пример: Открыть Блокнот и написать текст       ║")
    print("║  4. Пример: Открыть Проводник                      ║")
    print("║  5. Пример: Открыть браузер                        ║")
    print("║  6. Пример: Свернуть все окна                      ║")
    print("║  7. Настройки reasoning                            ║")
    print("║  8. Настройки агента                               ║")
    print("║  9. Выход                                          ║")
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
            run_agent("Open Notepad, type 'Hello from AI Agent', save as test.txt")
        elif choice == "4":
            run_agent("Open File Explorer and go to Desktop")
        elif choice == "5":
            run_agent("Open Chrome and go to google.com")
        elif choice == "6":
            run_agent("Minimize all windows with Win+D")

        elif choice == "7":
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

        elif choice == "8":
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

        elif choice == "9":
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