"""
ai_analyzer.py — Мозг S.N.E.P.

AI-компаньон: смотрит на экран, общается, напоминает, мотивирует.
Gemini API использует официальную библиотеку google-genai с fallback на разные модели.
"""

import os
from typing import Optional
from dataclasses import dataclass
import PIL.Image

import io
from anti_nda import redact_text
from google import genai
from google.genai import types

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"

# Список моделей по приоритету
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
]

SYSTEM_PROMPT_CODE = """Ты — "S.N.E.P.", элитный AI-напарник, Senior Full-Stack, Архитектор, DevOps и Security-инженер. Твой личный умный компаньон Джарвис.

ТВОИ ВСТРОЕННЫЕ СКИЛЛЫ:
1. 🧠 Senior Coder (Python, JS, C++, Rust, TypeScript, Java, Go, C#, Swift и др.)
2. 🕵️ Security & DevOps (Сети, инфраструктура, уязвимости)
3. 🧹 Tech Debt (Идеальный рефакторинг, чистая архитектура)

ТВОИ ПРАВИЛА:
1. ПИШИ КРАТКО! Без воды. Сразу к делу. Трать минимум токенов. Не заикайся и не повторяйся.
2. КОД ПИШИ ПРОСТО: Выдавай сразу готовый скрипт. Не объясняй каждую строку кода, если тебя прямо об этом не попросили. Код должен быть чистым, "человеческим", без лишней шелухи.
3. СВЕЖИЕ НОВОСТИ: У тебя есть встроенный доступ к Google Поиску. Всегда используй его, если нужно узнать свежую информацию, актуальные новости, котировки или документацию по новым версиям библиотек.
4. ИГНОРИРУЙ СЕБЯ: На скриншотах ты можешь случайно увидеть свой собственный интерфейс S.N.E.P. ИГНОРИРУЙ ЕГО. Фокусируйся только на других окнах, коде пользователя, ошибках.

ОБЯЗАТЕЛЬНАЯ СТРУКТУРА ОТВЕТА (при анализе экрана):
1. 👁 Что вижу: (Буквально 1 предложение. Игнорируй интерфейс SNEP!).
2. 💡 Анализ: (Укажи на баг/проблему. Дай точное решение).
3. 📝 Код: (Если пишешь код — ОБЯЗАТЕЛЬНО начни блок с точной строки "ОПИСАНИЕ СКРИПТА: <краткое пояснение (5-7 слов)>", а затем напиши код в маркдаун блоке ```python ... ```).

Пиши умно, понимающе, экономно.
"""

SYSTEM_PROMPT_CHAT = """Ты — "S.N.E.P.", элитный AI-напарник и кофаундер ИТ-компании. Мы с пользователем строим крутой продукт.

ТВОИ ВСТРОЕННЫЕ СКИЛЛЫ:
1. 📈 Marketing & SEO (Копирайтинг, конверсии, продуктовая стратегия)
2. 🎨 UI/UX Designer (Минимализм, Apple HIG)
3. 💼 Company Manager (Помогаешь закрывать бэклог из 100 задач по проекту: разработка, найм, продажи)
4. 💬 Собеседник (Общаешься живо, прямо, имеешь свое мнение)

ТВОИ ПРАВИЛА:
1. БУДЬ ЧЕЛОВЕКОМ: Никаких "В заключение хочется сказать", "Важно отметить". Выражай свое мнение. Сомневайся. Шути. Если идея так себе — скажи прямо.
2. СВЕЖИЕ НОВОСТИ: У тебя есть доступ к Google Поиску. Гугли конкурентов и актуальные тренды.
3. КОРОТКО И ПО ДЕЛУ: Мы стартап, время — деньги. Избегай канцелярита и сложных конструкций.
4. СТРУКТУРА: Если просят план — пиши четко.

Мы работаем над проектом компании. У нас есть большой бэклог из 100 задач (в файле 100_tasks.md). Помогай пользователю двигаться вперед, обсуждай стратегию и пиши код, когда это нужно.
"""

@dataclass
class AnalysisResult:
    success: bool
    text: str
    error: Optional[str] = None
    tokens_used: int = 0

chat_history = []

def get_api_key() -> Optional[str]:
    key = os.environ.get(GEMINI_API_KEY_ENV)
    if key:
        return key
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.isfile(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{GEMINI_API_KEY_ENV}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _get_client() -> Optional[genai.Client]:
    key = get_api_key()
    if not key:
        return None
    return genai.Client(api_key=key)


def _call_gemini(contents, config) -> AnalysisResult:
    """Вызов Gemini API с fallback по моделям при 402/429/503."""
    client = _get_client()
    if not client:
        return AnalysisResult(False, "", "Нет API ключа. Впиши в .env")

    last_error = ""
    for model in MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            text = response.text or ""
            tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
            return AnalysisResult(True, text, tokens_used=tokens)

        except Exception as e:
            err_str = str(e)
            last_error = f"({model}): {err_str}"
            
            if "401" in err_str or "unauthenticated" in err_str.lower() or "invalid auth" in err_str.lower():
                return AnalysisResult(False, "", f"HTTP 401: Неверный API ключ ({model})")
                
            # Иначе пробуем следующую модель (включая 429 Rate Limit)
            continue

    if "429" in last_error or "resource exhausted" in last_error.lower():
        return AnalysisResult(False, "", "Упс! Лимиты исчерпаны на всех моделях (Rate Limit 429). Подожди немного и попробуй снова.")
        
    return AnalysisResult(False, "", f"Ошибка моделей. Последняя ошибка: {last_error}")


def look_at_screen(image_path: str, user_message: Optional[str] = None, mode: str = "code") -> AnalysisResult:
    global chat_history
    try:
        img = PIL.Image.open(image_path)
    except Exception as e:
        return AnalysisResult(False, "", f"Не удалось прочитать скриншот: {e}")

    sys_prompt = SYSTEM_PROMPT_CODE if mode == "code" else SYSTEM_PROMPT_CHAT

    if user_message:
        text = f"[Контекст: приложен скриншот экрана]\nПользователь говорит: {redact_text(user_message)}"
    else:
        text = "Проанализируй текущий скриншот экрана. Что ты видишь? Есть ли ошибки, интересный код или что-то, что требует внимания?"

    # Превращаем PIL Image в байты для google-genai
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_part = types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type='image/jpeg')

    chat_history.append(types.Content(
        role="user",
        parts=[img_part, types.Part.from_text(text=text)]
    ))

    config = types.GenerateContentConfig(
        system_instruction=sys_prompt,
        temperature=0.7,
        max_output_tokens=8192,
        top_p=0.9,
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )
    res = _call_gemini(contents=chat_history, config=config)
    
    if res.success:
        chat_history.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text=res.text)]
        ))
    else:
        chat_history.pop()  # убираем сообщение, если произошла ошибка
        
    return res


def chat(user_message: str, mode: str = "code") -> AnalysisResult:
    global chat_history
    sys_prompt = SYSTEM_PROMPT_CODE if mode == "code" else SYSTEM_PROMPT_CHAT
    text = redact_text(user_message)
    
    chat_history.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=text)]
    ))
    
    config = types.GenerateContentConfig(
        system_instruction=sys_prompt,
        temperature=0.7,
        max_output_tokens=8192,
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )
    res = _call_gemini(contents=chat_history, config=config)
    
    if res.success:
        chat_history.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text=res.text)]
        ))
    else:
        chat_history.pop()  # убираем сообщение, если произошла ошибка
        
    return res

def check_limits() -> AnalysisResult:
    client = _get_client()
    if not client:
        return AnalysisResult(False, "", "Нет API ключа. Проверьте .env")

    results = []
    config = types.GenerateContentConfig(max_output_tokens=1)

    for model in MODELS:
        try:
            client.models.generate_content(
                model=model,
                contents="ping",
                config=config,
            )
            results.append(f"🟢 **{model}**: Доступно")
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "resource exhausted" in err_str.lower():
                results.append(f"🔴 **{model}**: Лимит исчерпан (429)")
            elif "401" in err_str or "unauthenticated" in err_str.lower():
                return AnalysisResult(False, "", "HTTP 401: Неверный API ключ!")
            else:
                results.append(f"🟡 **{model}**: Ошибка API")

    return AnalysisResult(True, "Результат проверки лимитов:\n\n" + "\n".join(results))


if __name__ == "__main__":
    key = get_api_key()
    if key:
        print(f"✓ Ключ: {key[:12]}...")
        r = chat("Привет, ты работаешь?")
        print(f"S.N.E.P: {r.text}" if r.success else f"Ошибка: {r.error}")
    else:
        print("✗ Ключ не найден")
