#!/usr/bin/env python3
"""
AI-Агент управления компьютером.
Основная логика: действия мыши/клавиатуры, главный цикл, меню.
"""

import pyautogui
import base64
from PIL import Image, ImageChops, ImageDraw
import io
import time
import sys
import os
import signal
import subprocess
import ctypes
import threading
from datetime import datetime

# Наши модули
import config
import model

# Попытка импорта pyperclip
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


# ── Инициализация PyAutoGUI ──
REAL_W, REAL_H = pyautogui.size()
pyautogui.FAILSAFE = config.FAILSAFE
pyautogui.PAUSE = 0.05


# ── Состояние модуля ──
previous_screenshot = None
action_history = []
log_lines = []
running = True
step_counter = 0


# ═══════════════════════════════════════════════════════
#                    ЛОГИРОВАНИЕ
# ═══════════════════════════════════════════════════════

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

    if config.SAVE_LOG:
        log_lines.append(line)


def save_log():
    if config.SAVE_LOG and log_lines:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"Сессия: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Модель: {config.MODEL_NAME}\n")
            f.write(f"Reasoning: {'ON' if config.ENABLE_REASONING else 'OFF'}\n")
            f.write(f"Стоимость: ${model.get_total_cost():.6f}\n")
            f.write(f"{'=' * 60}\n")
            f.write("\n".join(log_lines) + "\n\n")


def signal_handler(sig, frame):
    global running
    log("Остановлено пользователем", "WARN")
    # Отпускаем все зажатые клавиши при выходе
    release_all_modifiers()
    running = False
    save_log()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


# ═══════════════════════════════════════════════════════
#                    УТИЛИТЫ ВВОДА
# ═══════════════════════════════════════════════════════

def copy_to_clipboard(text):
    """Копирует текст в буфер обмена."""
    try:
        if HAS_PYPERCLIP:
            pyperclip.copy(text)
            return True
        if sys.platform == "win32":
            process = subprocess.Popen(
                ['clip'], stdin=subprocess.PIPE, shell=True
            )
            process.communicate(text.encode('utf-16-le'))
            return True
        else:
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))
            return True
    except Exception:
        return False


def release_all_modifiers():
    """Отпускает все зажатые модификаторы и кнопки мыши."""
    try:
        for key in ["shift", "ctrl", "alt", "win", "command"]:
            try:
                pyautogui.keyUp(key)
            except Exception:
                pass
        for btn in ["left", "right", "middle"]:
            try:
                pyautogui.mouseUp(button=btn)
            except Exception:
                pass
        time.sleep(0.1)
    except Exception:
        pass


def type_text_via_clipboard(text):
    """
    Вводит текст через буфер обмена.
    Работает с ЛЮБОЙ раскладкой и символами.
    """
    # Сохраняем старый буфер
    old_clipboard = ""
    if HAS_PYPERCLIP:
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = ""

    # Сбрасываем модификаторы
    release_all_modifiers()

    # Копируем новый текст
    if not copy_to_clipboard(text):
        log("Не удалось скопировать в буфер", "ERROR")
        return False

    time.sleep(0.15)

    # Вставляем
    paste_key = 'command' if sys.platform == "darwin" else 'ctrl'
    pyautogui.hotkey(paste_key, 'v')
    time.sleep(0.2)

    # Отпускаем модификаторы
    release_all_modifiers()

    # Восстанавливаем старый буфер через 1 сек
    if old_clipboard and HAS_PYPERCLIP:
        def restore():
            time.sleep(1.0)
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass
        threading.Thread(target=restore, daemon=True).start()

    return True


def save_debug_screenshot(screenshot, x=None, y=None, action="", label=""):
    """Сохраняет скриншот с маркером клика."""
    if not config.DEBUG:
        return
    os.makedirs(config.DEBUG_DIR, exist_ok=True)

    draw = ImageDraw.Draw(screenshot)
    if x is not None and y is not None:
        r = 15
        draw.ellipse([x - r, y - r, x + r, y + r], outline="red", width=3)
        draw.line([x - r - 5, y, x + r + 5, y], fill="red", width=2)
        draw.line([x, y - r - 5, x, y + r + 5], fill="red", width=2)
        text = f"{action} ({x},{y})"
        draw.text((x + 20, y - 10), text, fill="red")

    filename = f"{step_counter:03d}_{label}.png"
    filepath = os.path.join(config.DEBUG_DIR, filename)
    screenshot.save(filepath)


# ═══════════════════════════════════════════════════════
#                 ПРОВЕРКА ОКРУЖЕНИЯ
# ═══════════════════════════════════════════════════════

def check_environment():
    global REAL_W, REAL_H

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║   🪟 AI-Агент (расширенная версия)                 ║")
    print("║   • Drag & Drop   • Любые клавиши                  ║")
    print("║   • Комбинации    • Удержание                      ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    if not config.OPENROUTER_API_KEY:
        log("API ключ OpenRouter не найден!", "ERROR")
        log("Создайте .env: OPENROUTER_API_KEY=sk-or-v1-...", "ERROR")
        return False
    log(
        f"API ключ: {'*' * 10}...{config.OPENROUTER_API_KEY[-4:]}",
        "SUCCESS"
    )

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
    if not model.test_connection(log):
        return False

    try:
        pyautogui.position()
        pyautogui.screenshot()
        log("Мышь и скриншоты работают ✓", "SUCCESS")
    except Exception as e:
        log(f"Ошибка: {e}", "ERROR")
        return False

    if config.DEBUG:
        os.makedirs(config.DEBUG_DIR, exist_ok=True)

    print()
    log(f"Модель: {config.MODEL_NAME}")
    effort_str = (
        f"ON (effort={config.REASONING_EFFORT})"
        if config.ENABLE_REASONING else "OFF"
    )
    log(f"Reasoning: {effort_str}")
    log(f"Скриншот: {config.SCREEN_WIDTH}px")
    log(f"Максимум шагов: {config.MAX_STEPS}")
    print()
    return True


# ═══════════════════════════════════════════════════════
#                  РАБОТА С ЭКРАНОМ
# ═══════════════════════════════════════════════════════

def take_screenshot():
    full_screenshot = pyautogui.screenshot()
    full_w, full_h = full_screenshot.size

    if full_w > config.SCREEN_WIDTH:
        ratio = config.SCREEN_WIDTH / full_w
        new_h = int(full_h * ratio)
        model_screenshot = full_screenshot.resize(
            (config.SCREEN_WIDTH, new_h), Image.LANCZOS
        )
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


# ═══════════════════════════════════════════════════════
#            ВЕРИФИКАЦИЯ И ВЫПОЛНЕНИЕ ДЕЙСТВИЙ
# ═══════════════════════════════════════════════════════

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

    # Вне границ
    if x < 0 or x > img_w or y < 0 or y > img_h:
        log(f"Вне границ: ({x},{y}) при ({img_w}x{img_h})", "WARN")
        x = max(0, min(x, img_w - 1))
        y = max(0, min(y, img_h - 1))
        return int(x), int(y), "ограничено"

    return int(x), int(y), "OK"


def resolve_key(key_name):
    """Преобразует алиас клавиши в имя для pyautogui."""
    key_name = key_name.lower().strip()
    return config.KEY_ALIASES.get(key_name, key_name)


def to_screen_coords(x, y, scale_x, scale_y, img_w, img_h):
    """Переводит координаты модели в координаты экрана."""
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


def execute_action(action_data, scale_x, scale_y, img_w, img_h, full_screenshot):
    global running, step_counter

    if not action_data or not running:
        return None

    action = action_data.get("action", "").lower().strip()

    # Сбрасываем модификаторы перед действиями, которые этого требуют
    if action in ("type_text", "press_key", "hotkey",
                  "click", "double_click", "right_click"):
        release_all_modifiers()

    try:
        # ── КЛИКИ ──
        if action in ("click", "right_click", "double_click", "left_click"):
            raw_x = action_data.get("x", 0)
            raw_y = action_data.get("y", 0)

            real_x, real_y = to_screen_coords(
                raw_x, raw_y, scale_x, scale_y, img_w, img_h
            )
            if real_x is None:
                return None

            log(f"🎯 ({raw_x},{raw_y}) → ({real_x},{real_y})")

            if config.DEBUG:
                save_debug_screenshot(
                    full_screenshot.copy(), real_x, real_y,
                    action, f"step{step_counter}"
                )

            if config.CLICK_DELAY > 0:
                log(f"Клик через {config.CLICK_DELAY}с (Ctrl+C = отмена)")
                for i in range(config.CLICK_DELAY, 0, -1):
                    if not running:
                        return None
                    print(f"    {i}...", end="\r")
                    time.sleep(1)
                print("    " + " " * 20, end="\r")

            pyautogui.moveTo(real_x, real_y, duration=config.MOUSE_SPEED)
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
            button = action_data.get(
                "text", action_data.get("button", "left")
            ).lower()
            duration = float(action_data.get("duration", 0.5))

            if button not in ("left", "right", "middle"):
                button = "left"

            start_x, start_y = to_screen_coords(
                raw_x, raw_y, scale_x, scale_y, img_w, img_h
            )
            if start_x is None:
                return None

            end_x, end_y = to_screen_coords(
                raw_to_x, raw_to_y, scale_x, scale_y, img_w, img_h
            )
            if end_x is None:
                return None

            log(f"🎯 Drag: ({start_x},{start_y}) → ({end_x},{end_y}) [{button}]")

            if config.DEBUG:
                debug_img = full_screenshot.copy()
                draw = ImageDraw.Draw(debug_img)
                r = 15
                # Маркер старта (синий)
                draw.ellipse(
                    [start_x - r, start_y - r, start_x + r, start_y + r],
                    outline="blue", width=3
                )
                draw.text(
                    (start_x + 20, start_y - 10),
                    f"FROM ({start_x},{start_y})", fill="blue"
                )
                # Маркер конца (красный)
                draw.ellipse(
                    [end_x - r, end_y - r, end_x + r, end_y + r],
                    outline="red", width=3
                )
                draw.text(
                    (end_x + 20, end_y - 10),
                    f"TO ({end_x},{end_y})", fill="red"
                )
                # Линия
                draw.line(
                    [start_x, start_y, end_x, end_y],
                    fill="purple", width=2
                )

                os.makedirs(config.DEBUG_DIR, exist_ok=True)
                filename = f"{step_counter:03d}_drag.png"
                debug_img.save(os.path.join(config.DEBUG_DIR, filename))
                log("📷 Drag визуализация сохранена", "DEBUG")

            if config.CLICK_DELAY > 0:
                log(f"Drag через {config.CLICK_DELAY}с (Ctrl+C = отмена)")
                for i in range(config.CLICK_DELAY, 0, -1):
                    if not running:
                        return None
                    print(f"    {i}...", end="\r")
                    time.sleep(1)
                print("    " + " " * 20, end="\r")

            pyautogui.moveTo(start_x, start_y, duration=config.MOUSE_SPEED)
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
            button = action_data.get(
                "text", action_data.get("button", "left")
            ).lower()
            if button not in ("left", "right", "middle"):
                button = "left"

            real_x, real_y = to_screen_coords(
                raw_x, raw_y, scale_x, scale_y, img_w, img_h
            )
            if real_x is None:
                return None

            log(f"🎯 Mouse DOWN: ({real_x},{real_y}) [{button}]")

            pyautogui.moveTo(real_x, real_y, duration=config.MOUSE_SPEED)
            time.sleep(0.1)
            pyautogui.mouseDown(button=button)

            desc = f"mouse_down({real_x},{real_y},{button})"
            log(f"✓ {desc} (удерживаю)", "SUCCESS")
            return desc

        elif action == "mouse_up":
            raw_x = action_data.get("x", 0)
            raw_y = action_data.get("y", 0)
            button = action_data.get(
                "text", action_data.get("button", "left")
            ).lower()
            if button not in ("left", "right", "middle"):
                button = "left"

            real_x, real_y = to_screen_coords(
                raw_x, raw_y, scale_x, scale_y, img_w, img_h
            )
            if real_x is None:
                return None

            log(f"🎯 Mouse UP: ({real_x},{real_y}) [{button}]")

            pyautogui.moveTo(real_x, real_y, duration=config.MOUSE_SPEED)
            time.sleep(0.1)
            pyautogui.mouseUp(button=button)

            desc = f"mouse_up({real_x},{real_y},{button})"
            log(f"✓ {desc}", "SUCCESS")
            return desc

        # ── ТЕКСТ (через буфер обмена) ──
        elif action == "type_text":
            text = action_data.get("text", "")
            if not text:
                log("Пустой текст", "WARN")
                return None

            # Обработка escape-последовательностей
            text = text.replace("\\n", "\n").replace("\\t", "\t")
            text = text.replace("\\r", "").strip()

            log(f"⌨ Ввожу: '{text}'")
            time.sleep(0.2)

            if type_text_via_clipboard(text):
                short = text[:50] + ('...' if len(text) > 50 else '')
                log(f"✓ Введено: '{short}'", "SUCCESS")
                return f"type('{short}')"
            return None

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
                keys_str = keys_str.replace(
                    "ctrl", "command"
                ).replace("win", "command")
            else:
                keys_str = keys_str.replace(
                    "command", "ctrl"
                ).replace("cmd", "ctrl")
                keys_str = keys_str.replace(
                    "super", "win"
                ).replace("option", "alt")

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
        elif action == "scroll_down":
            log("📜 ↓")
            pyautogui.scroll(-5)
            return "scroll_down"

        elif action == "scroll_up":
            log("📜 ↑")
            pyautogui.scroll(5)
            return "scroll_up"

        elif action == "scroll_left":
            log("📜 ←")
            try:
                pyautogui.hscroll(-5)
            except AttributeError:
                pyautogui.scroll(-5)
            return "scroll_left"

        elif action == "scroll_right":
            log("📜 →")
            try:
                pyautogui.hscroll(5)
            except AttributeError:
                pyautogui.scroll(5)
            return "scroll_right"

        # ── ОЖИДАНИЕ ──
        elif action == "wait":
            duration = float(
                action_data.get(
                    "duration", action_data.get("text", 2)
                )
            )
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


# ═══════════════════════════════════════════════════════
#                    ГЛАВНЫЙ ЦИКЛ
# ═══════════════════════════════════════════════════════

def run_agent(task):
    global action_history, running, step_counter

    action_history = []
    step_counter = 0
    model.reset_conversation()
    start_cost = model.get_total_cost()

    log(f"🚀 Задача: '{task}'")
    log(f"Модель: {config.MODEL_NAME}")
    log(f"Reasoning: {'ON' if config.ENABLE_REASONING else 'OFF'}")
    print("─" * 60)

    for step in range(1, config.MAX_STEPS + 1):
        if not running:
            break

        step_counter = step
        print()
        log(f"═══ Шаг {step}/{config.MAX_STEPS} ═══")

        img_b64, full_screenshot, model_screenshot, scale_x, scale_y = \
            take_screenshot()
        model_w, model_h = model_screenshot.size

        log(
            f"Скриншот: {model_w}x{model_h}, "
            f"масштаб: x{scale_x:.2f} y{scale_y:.2f}",
            "DEBUG"
        )

        if config.DEBUG:
            save_debug_screenshot(
                full_screenshot.copy(), None, None, "",
                f"step{step}_before"
            )

        recent_history = (
            "; ".join(action_history[-5:]) if action_history else ""
        )

        log("🧠 Анализирую экран с reasoning...")
        start_time = time.time()
        action_data = model.ask_agent(
            task, img_b64, step, recent_history,
            model_w, model_h, log
        )
        elapsed = time.time() - start_time
        log(f"⏱ {elapsed:.1f}с")

        if not action_data:
            log("Нет ответа. Повтор через 3с...", "WARN")
            time.sleep(3)
            continue

        action_type = action_data.get("action", "").lower()

        if action_type == "finish":
            execute_action(
                action_data, scale_x, scale_y,
                model_w, model_h, full_screenshot
            )
            print()
            log("✅ Задача завершена!", "SUCCESS")
            break

        result = execute_action(
            action_data, scale_x, scale_y,
            model_w, model_h, full_screenshot
        )

        if result == "FINISH":
            break

        if result:
            action_history.append(result)
        else:
            log("Действие не выполнено", "WARN")

        time.sleep(config.WAIT_AFTER)

        _, new_full, _, _, _ = take_screenshot()
        changed = screen_changed(new_full)
        if changed:
            log("📺 Экран изменился ✓")
        else:
            log("📺 Экран НЕ изменился ⚠", "WARN")

    else:
        log(f"⚠ Лимит {config.MAX_STEPS} шагов", "WARN")

    # Безопасное отпускание всех клавиш/кнопок после задачи
    release_all_modifiers()

    print()
    print("═" * 60)
    log("📋 Итог:")
    log(f"   Задача: {task}")
    log(f"   Шагов: {len(action_history)}")
    session_cost = model.get_total_cost() - start_cost
    log(f"   Стоимость сессии: ${session_cost:.6f}")
    log(f"   Всего: ${model.get_total_cost():.6f}")

    if action_history:
        print()
        for i, h in enumerate(action_history, 1):
            print(f"   {i:2d}. {h}")

    print("═" * 60)

    if config.DEBUG:
        log(f"Скриншоты: ./{config.DEBUG_DIR}/", "DEBUG")

    save_log()


# ═══════════════════════════════════════════════════════
#                      МЕНЮ
# ═══════════════════════════════════════════════════════

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
            run_agent(
                "Select text on screen by dragging mouse over it "
                "from left to right"
            )
        elif choice == "5":
            run_agent(
                "Open Notepad, type some text, then select all with Ctrl+A"
            )
        elif choice == "6":
            run_agent(
                "Take a screenshot of a selected area using "
                "Win+Shift+S"
            )
        elif choice == "7":
            run_agent("Open Task Manager using Ctrl+Shift+Escape")
        elif choice == "8":
            run_agent("Minimize all windows using Win+D")

        elif choice == "9":
            print(
                f"\n  Reasoning: "
                f"{'ON' if config.ENABLE_REASONING else 'OFF'}"
            )
            print(f"  Effort: {config.REASONING_EFFORT}")

            toggle = input(
                "\n  Включить reasoning? (y/n) [y]: "
            ).strip().lower()
            if toggle in ("n", "no"):
                config.ENABLE_REASONING = False
                log("Reasoning: OFF")
            else:
                config.ENABLE_REASONING = True
                log("Reasoning: ON")

                effort = input(
                    "  Effort (low/medium/high) [high]: "
                ).strip().lower()
                if effort in ("low", "medium", "high"):
                    config.REASONING_EFFORT = effort
                log(f"Reasoning effort: {config.REASONING_EFFORT}")

        elif choice == "10":
            print(f"\n  Модель: {config.MODEL_NAME}")
            print(f"  Скриншот: {config.SCREEN_WIDTH}px")
            print(f"  Задержка: {config.CLICK_DELAY}с")
            print(f"  Макс. шагов: {config.MAX_STEPS}")

            w = input(f"\n  Ширина [{config.SCREEN_WIDTH}]: ").strip()
            if w.isdigit() and 400 <= int(w) <= 2560:
                config.SCREEN_WIDTH = int(w)

            d = input(f"  Задержка [{config.CLICK_DELAY}]: ").strip()
            if d.isdigit():
                config.CLICK_DELAY = int(d)

            m = input(f"  Модель [{config.MODEL_NAME}]: ").strip()
            if m:
                config.MODEL_NAME = m

        elif choice == "11":
            log("Выход")
            save_log()
            print(f"\n  💰 Всего: ${model.get_total_cost():.6f}")
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