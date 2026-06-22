"""
skill_executor.py — Модуль запуска antigravity-cli скиллов.

Парсит текстовую/голосовую команду пользователя, находит подходящий скилл
и запускает его в отдельном окне CMD через subprocess.
"""

import subprocess
import os
import re
from dataclasses import dataclass, field
from typing import Optional

# ─── Конфигурация ──────────────────────────────────────────────────────
SKILLS_DIR = r"C:\Users\snek\.gemini\antigravity-cli\skills"
ANTIGRAVITY_CMD = "antigravity"  # должен быть в PATH


@dataclass
class SkillMapping:
    """Маппинг ключевых слов на имя скилла."""
    skill_name: str
    keywords: list[str] = field(default_factory=list)
    description: str = ""


# ─── Карта триггеров ───────────────────────────────────────────────────
SKILL_MAP: list[SkillMapping] = [
    SkillMapping(
        skill_name="code-reviewer",
        keywords=["ревью", "review", "проверь код", "code review", "посмотри код"],
        description="Ревью кода",
    ),
    SkillMapping(
        skill_name="cmd-focused-fix",
        keywords=["исправь", "fix", "починить", "починю", "баг", "bug", "ошибка", "focused fix", "focused-fix"],
        description="Глубокое исправление модуля",
    ),
    SkillMapping(
        skill_name="tech-debt-tracker",
        keywords=["долг", "debt", "tech debt", "технический долг", "рефакторинг", "refactor"],
        description="Проверка технического долга",
    ),
    SkillMapping(
        skill_name="cmd-code-to-prd",
        keywords=["прод", "prd", "production", "продакшн", "code to prd", "документация"],
        description="Генерация PRD из кода",
    ),
    SkillMapping(
        skill_name="karpathy-check",
        keywords=["карпати", "karpathy", "принципы", "чистота", "quality check"],
        description="Проверка по принципам Карпати",
    ),
    SkillMapping(
        skill_name="tdd",
        keywords=["тест", "test", "tdd", "тесты", "покрытие", "coverage"],
        description="TDD / генерация тестов",
    ),
    SkillMapping(
        skill_name="security-pen-testing",
        keywords=["безопасность", "security", "пентест", "уязвимость", "vulnerability"],
        description="Проверка безопасности",
    ),
    SkillMapping(
        skill_name="codebase-onboarding",
        keywords=["онбординг", "onboarding", "документация проекта", "архитектура", "architecture"],
        description="Онбординг по кодовой базе",
    ),
    SkillMapping(
        skill_name="marketing-mode",
        keywords=["маркетинг", "marketing", "продвижение", "реклама", "аудитория", "маркетинговый"],
        description="Маркетинговый режим (стратегия, рост)",
    ),
    SkillMapping(
        skill_name="seo-auditor",
        keywords=["seo", "сео", "поисковая", "оптимизация", "выдача", "ключевики"],
        description="SEO Аудит и оптимизация",
    ),
    SkillMapping(
        skill_name="marketing-ideas",
        keywords=["идеи", "idea", "придумай", "креатив", "генерация идей"],
        description="Идеи для маркетинга и продвижения",
    ),
    SkillMapping(
        skill_name="browser-automation",
        keywords=["браузер", "browser", "автоматизация", "scraping", "парсинг", "сайт"],
        description="Автоматизация браузера",
    ),
    SkillMapping(
        skill_name="campaign-analytics",
        keywords=["аналитика", "analytics", "метрики", "roi", "конверсия", "cpa", "воронка"],
        description="Аналитика кампаний",
    ),
    SkillMapping(
        skill_name="ui-designer",
        keywords=["дизайн", "ui", "ux", "макет", "интерфейс", "frontend design"],
        description="UI/UX Дизайн интерфейсов",
    ),
    SkillMapping(
        skill_name="copy-editing",
        keywords=["копирайтинг", "текст", "редактура", "статья", "пост", "copywriting"],
        description="Редактура маркетингового текста",
    ),
]


def find_skill(user_input: str) -> Optional[SkillMapping]:
    """
    Ищет подходящий скилл по ключевым словам в тексте пользователя.
    Возвращает первое совпадение или None.
    """
    text = user_input.lower().strip()
    for mapping in SKILL_MAP:
        for keyword in mapping.keywords:
            if keyword.lower() in text:
                return mapping
    return None


def list_available_skills() -> list[str]:
    """Возвращает список имён папок-скиллов из SKILLS_DIR."""
    if not os.path.isdir(SKILLS_DIR):
        return []
    return sorted(
        name for name in os.listdir(SKILLS_DIR)
        if os.path.isdir(os.path.join(SKILLS_DIR, name))
        and not name.startswith(".")
    )


def execute_skill(skill_name: str, extra_args: str = "") -> subprocess.Popen:
    """
    Запускает `antigravity run <skill_name>` в новом окне CMD.
    Возвращает Popen-объект для мониторинга.
    """
    cmd = f'{ANTIGRAVITY_CMD} run {skill_name}'
    if extra_args:
        cmd += f' {extra_args}'

    print(f"[SkillExecutor] Запуск: {cmd}")

    process = subprocess.Popen(
        cmd,
        shell=True,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=os.getcwd(),
    )
    return process


def execute_from_text(user_input: str) -> Optional[subprocess.Popen]:
    """
    Высокоуровневый метод: парсит текст → находит скилл → запускает.
    Возвращает Popen или None, если скилл не найден.
    """
    mapping = find_skill(user_input)
    if mapping is None:
        print(f"[SkillExecutor] Скилл не найден для: '{user_input}'")
        return None

    print(f"[SkillExecutor] Найден скилл: {mapping.skill_name} ({mapping.description})")
    return execute_skill(mapping.skill_name)


# ─── Прямой запуск для тестирования ────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        result = execute_from_text(query)
        if result is None:
            print("Совет: доступные скиллы:")
            for s in list_available_skills()[:20]:
                print(f"  - {s}")
    else:
        print("Использование: python skill_executor.py <текст запроса>")
        print(f"\nДоступные скиллы ({len(list_available_skills())}):")
        for s in list_available_skills()[:30]:
            print(f"  - {s}")
