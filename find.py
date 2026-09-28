import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")

print("🔍 Загружаю список всех моделей с OpenRouter...\n")

# Получаем полный список моделей
r = requests.get(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=30
)

if r.status_code != 200:
    print(f"❌ Ошибка API: {r.status_code}")
    print(r.text)
    exit(1)

models = r.json()["data"]
print(f"Всего моделей на OpenRouter: {len(models)}\n")

# Фильтруем модели с поддержкой изображений (мультимодальные)
vision_models = []
free_vision_models = []

for m in models:
    architecture = m.get("architecture", {})
    input_modalities = architecture.get("input_modalities", [])

    # Проверяем, поддерживает ли модель изображения на входе
    if "image" in input_modalities:
        pricing = m.get("pricing", {})
        prompt_price = float(pricing.get("prompt", 0))
        completion_price = float(pricing.get("completion", 0))
        is_free = prompt_price == 0 and completion_price == 0

        info = {
            "id": m["id"],
            "name": m.get("name", ""),
            "price_in": prompt_price,
            "price_out": completion_price,
            "context": m.get("context_length", 0)
        }

        vision_models.append(info)
        if is_free:
            free_vision_models.append(info)

# Выводим бесплатные
print("=" * 70)
print("🆓 БЕСПЛАТНЫЕ модели с поддержкой изображений:")
print("=" * 70)
if free_vision_models:
    for m in sorted(free_vision_models, key=lambda x: x["context"], reverse=True):
        print(f"  ✅ {m['id']}")
        print(f"     Контекст: {m['context']:,} токенов")
        print()
else:
    print("  (не найдено)")

# Выводим платные (отсортированные по цене)
print("=" * 70)
print("💰 САМЫЕ ДЕШЁВЫЕ платные модели с поддержкой изображений:")
print("=" * 70)
paid = [m for m in vision_models if m not in free_vision_models]
paid_sorted = sorted(paid, key=lambda x: x["price_in"] + x["price_out"])

for m in paid_sorted[:15]:
    price_per_1m = (m["price_in"] + m["price_out"]) * 1_000_000
    print(f"  💵 {m['id']}")
    print(f"     ~${price_per_1m:.2f} за 1M токенов | Контекст: {m['context']:,}")
    print()

# Тестируем топ-3 бесплатные
print("=" * 70)
print("🧪 ТЕСТИРОВАНИЕ доступных моделей:")
print("=" * 70)

test_list = [m["id"] for m in free_vision_models[:5]]
if not test_list:
    test_list = [m["id"] for m in paid_sorted[:5]]

working_models = []

for model_id in test_list:
    print(f"\n🔍 {model_id}")
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 10
            },
            timeout=30
        )

        if r.status_code == 200:
            print(f"   ✅ РАБОТАЕТ!")
            working_models.append(model_id)
        elif r.status_code == 429:
            print(f"   ⚠️  Rate limit")
        elif r.status_code == 402:
            print(f"   💰 Нужны кредиты")
        else:
            print(f"   ❌ Ошибка {r.status_code}: {r.text[:150]}")
    except Exception as e:
        print(f"   ❌ {e}")

# Итоговая рекомендация
print("\n" + "=" * 70)
print("📋 ИТОГОВАЯ РЕКОМЕНДАЦИЯ:")
print("=" * 70)
if working_models:
    print(f"\nИспользуйте эту модель в агенте:\n")
    print(f'    MODEL_NAME = "{working_models[0]}"')
    print(f"\nСкопируйте строку выше в ваш agent.py")
else:
    print("\n⚠️ Ни одна модель не прошла тест.")
    print("Проверьте баланс: https://openrouter.ai/settings/credits")