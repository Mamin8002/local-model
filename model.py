"""
Работа с языковой моделью через OpenRouter API.
Содержит промпты, запросы и управление историей диалога.
"""

import requests
import json
import time
import config

# ── Состояние модуля ──
_conversation_history = []
_total_cost = 0.0


# ═══════════════════════════════════════════════════════
#                    ПРОМПТЫ
# ═══════════════════════════════════════════════════════

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
- mouse_down(x, y, button="left"): Press and HOLD mouse button at coordinates
- mouse_up(x, y, button="left"): Release mouse button at coordinates
- type_text(text): Type into focused field
- press_key(key): Press any single key
- hotkey(keys): Press key combination (e.g., ctrl+shift+alt+f12)
- key_down(key): Press and HOLD a key
- key_up(key): Release a held key
- scroll_down / scroll_up / scroll_left / scroll_right: Scroll
- wait: Wait for updates
- finish(reason): Task complete

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
1. (x, y) is where you CLICK AND HOLD (start point)
2. (to_x, to_y) is where you RELEASE (destination)
3. Use duration 0.3-1.0 for smooth movement
4. Use button="left" for most operations, "right" for right-drag

KEY COMBINATION RULES:
- Use "+" to combine keys: ctrl+shift+a, win+shift+s
- Maximum 5 keys in one combination

CRITICAL:
1. Coordinates MUST be within screenshot dimensions
2. Aim for EXACT CENTER of target elements
3. Output only ONE action per response
4. On Windows use ctrl (not cmd), win for Windows key
5. Be precise - pixels matter!"""


def build_user_prompt(task, step, img_w, img_h, action_history_text, max_steps):
    return f"""Current screenshot: {img_w} x {img_h} pixels

TASK: {task}
STEP: {step} of {max_steps}
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
{{"thought":"...", "action":"hotkey", "x":0, "y":0, "text":"ctrl+shift+alt+f12"}}
{{"thought":"...", "action":"key_down", "x":0, "y":0, "text":"shift"}}
{{"thought":"...", "action":"key_up", "x":0, "y":0, "text":"shift"}}
{{"thought":"...", "action":"scroll_down", "x":0, "y":0, "text":""}}
{{"thought":"Task complete", "action":"finish", "x":0, "y":0, "text":"", "reason":"done"}}

Note: For drag/mouse_down/mouse_up, the 'text' field holds the button name: "left", "right", or "middle".
For press_key/hotkey/key_down/key_up, the 'text' field holds the key name(s).

JSON only, no markdown."""


# ═══════════════════════════════════════════════════════
#                    УПРАВЛЕНИЕ СОСТОЯНИЕМ
# ═══════════════════════════════════════════════════════

def reset_conversation():
    """Сбрасывает историю разговора для новой задачи."""
    global _conversation_history
    _conversation_history = []


def get_total_cost():
    """Возвращает общую стоимость всех запросов."""
    return _total_cost


def add_cost(amount):
    """Добавляет сумму к общей стоимости."""
    global _total_cost
    _total_cost += amount


def test_connection(log_func):
    """Проверяет соединение с API."""
    try:
        test_payload = {
            "model": config.MODEL_NAME,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "Hi"}]}
            ],
            "max_tokens": 5
        }
        if config.ENABLE_REASONING:
            test_payload["reasoning"] = {"enabled": True}

        r = requests.post(
            config.OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": config.HTTP_REFERRER,
                "X-Title": config.APP_TITLE
            },
            json=test_payload,
            timeout=30
        )

        if r.status_code == 200:
            log_func("API работает ✓", "SUCCESS")
            return True
        elif r.status_code == 401:
            log_func("Неверный API ключ!", "ERROR")
            return False
        elif r.status_code == 402:
            log_func("Недостаточно кредитов", "ERROR")
            return False
        elif r.status_code == 404:
            log_func(f"Модель {config.MODEL_NAME} не найдена", "ERROR")
            return False
        else:
            log_func(f"Ошибка API: {r.status_code} - {r.text[:200]}", "WARN")
            return False
    except Exception as e:
        log_func(f"Не удалось подключиться: {e}", "ERROR")
        return False


# ═══════════════════════════════════════════════════════
#                    ОСНОВНОЙ ЗАПРОС
# ═══════════════════════════════════════════════════════

def ask_agent(task, image_b64, step, action_history_text, img_w, img_h, log_func):
    """
    Отправляет запрос к модели через OpenRouter.

    Args:
        task: задача пользователя
        image_b64: скриншот в base64
        step: номер текущего шага
        action_history_text: история предыдущих действий
        img_w, img_h: размеры скриншота
        log_func: функция логирования

    Returns:
        dict с полями action, x, y, text и т.д., или None при ошибке
    """
    global _conversation_history

    # Инициализация разговора при первом шаге
    if step == 1 or not _conversation_history:
        _conversation_history = [
            {"role": "system", "content": build_system_prompt()}
        ]

    # Сообщение пользователя со скриншотом
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
            },
            {
                "type": "text",
                "text": build_user_prompt(
                    task, step, img_w, img_h,
                    action_history_text, config.MAX_STEPS
                )
            }
        ]
    }

    _conversation_history.append(user_message)

    # Ограничиваем размер истории
    max_size = 2 + config.MAX_HISTORY * 2
    if len(_conversation_history) > max_size:
        _conversation_history = (
                [_conversation_history[0]] +
                _conversation_history[-(config.MAX_HISTORY * 2):]
        )

    payload = {
        "model": config.MODEL_NAME,
        "messages": _conversation_history,
        "max_tokens": 2048,
        "temperature": 0.1
    }

    if config.ENABLE_REASONING:
        payload["reasoning"] = {
            "enabled": True,
            "effort": config.REASONING_EFFORT
        }

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.HTTP_REFERRER,
        "X-Title": config.APP_TITLE
    }

    for attempt in range(config.MAX_RETRIES + 1):
        try:
            log_func(f"Запрос к API (попытка {attempt + 1})...", "API")
            response = requests.post(
                config.OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=config.TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()

                # Стоимость
                usage = data.get("usage", {})
                if "cost" in usage:
                    cost = usage["cost"]
                    add_cost(cost)
                    log_func(
                        f"Токены: {usage.get('prompt_tokens', 0)} in / "
                        f"{usage.get('completion_tokens', 0)} out | ${cost:.6f}",
                        "API"
                    )

                # Извлекаем ответ
                choice = data["choices"][0]
                message = choice["message"]
                content = message.get("content", "").strip()

                # Reasoning
                reasoning_details = message.get("reasoning_details")
                reasoning = message.get("reasoning")

                if reasoning_details:
                    if isinstance(reasoning_details, list):
                        for r in reasoning_details:
                            if isinstance(r, dict):
                                text = r.get("text", r.get("content", ""))
                                if text:
                                    log_func(f"💭 {text[:300]}", "REASONING")
                    elif isinstance(reasoning_details, str):
                        log_func(f"💭 {reasoning_details[:300]}", "REASONING")
                elif reasoning and isinstance(reasoning, str):
                    log_func(f"💭 {reasoning[:300]}", "REASONING")

                # Сохраняем в историю (с reasoning_details!)
                assistant_message = {"role": "assistant", "content": content}
                if reasoning_details:
                    assistant_message["reasoning_details"] = reasoning_details
                elif reasoning:
                    assistant_message["reasoning"] = reasoning

                _conversation_history.append(assistant_message)

                # Извлекаем JSON из content
                start = content.find('{')
                end = content.rfind('}') + 1

                if start != -1 and end != -1:
                    json_str = content[start:end]
                    try:
                        result = json.loads(json_str)
                        thought = result.get("thought", "")
                        if thought:
                            log_func(f"💭 Thought: {thought[:300]}", "REASONING")
                        return result
                    except json.JSONDecodeError as e:
                        log_func(f"JSON parse error: {e}", "WARN")
                        log_func(f"Raw: {json_str[:200]}", "DEBUG")
                else:
                    log_func("JSON не найден", "WARN")
                    log_func(f"Content: {content[:300]}", "DEBUG")

            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait_time = int(retry_after)
                else:
                    wait_time = min(30 * (2 ** attempt), 120)
                log_func(f"⚠ Rate limit! Жду {wait_time}с...", "WARN")
                for i in range(wait_time, 0, -1):
                    print(f"    ⏳ {i}с... ", end="\r")
                    time.sleep(1)
                print()
                continue

            elif response.status_code == 400:
                error_text = response.text[:300]
                log_func(f"Bad request: {error_text}", "ERROR")
                if "reasoning" in error_text.lower():
                    log_func("Повторяю без reasoning...", "WARN")
                    payload.pop("reasoning", None)
                    continue
                return None

            elif response.status_code == 402:
                log_func("Недостаточно кредитов", "ERROR")
                return None
            else:
                log_func(
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    "ERROR"
                )

        except requests.exceptions.Timeout:
            log_func(f"Timeout (попытка {attempt + 1})", "WARN")
        except requests.exceptions.ConnectionError:
            log_func("Потеряна связь", "ERROR")
            return None
        except Exception as e:
            log_func(f"Ошибка: {e}", "WARN")

        if attempt < config.MAX_RETRIES:
            time.sleep(2)

    return None