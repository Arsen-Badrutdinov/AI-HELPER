"""
anti_nda.py — Фильтр конфиденциальных данных.

Удаляет из текста: IP-адреса, токены, пароли, секреты,
ключи API, email, номера карт, и другие чувствительные данные
перед отправкой на внешний AI API.
"""

import re
from typing import List, Tuple

# ─── Паттерны для очистки ──────────────────────────────────────────────
REDACT_PATTERNS: List[Tuple[str, str]] = [
    # IPv4 адреса
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[REDACTED_IP]'),

    # IPv6 адреса (сокращённая форма)
    (r'\b[0-9a-fA-F]{1,4}(:[0-9a-fA-F]{1,4}){7}\b', '[REDACTED_IPv6]'),

    # Email адреса
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]'),

    # API ключи / токены (длинные hex/base64 строки)
    (r'\b[A-Za-z0-9_\-]{32,}\b', '[REDACTED_TOKEN]'),

    # Bearer токены
    (r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [REDACTED_TOKEN]'),

    # Пароли в строках (password = "...", pwd: "...", etc.)
    (r'(?i)(password|passwd|pwd|secret|token|api_key|apikey|api-key|access_key|secret_key)'
     r'\s*[=:]\s*["\']?[^\s"\']+["\']?',
     r'\1 = [REDACTED]'),

    # AWS ключи
    (r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]'),

    # Номера кредитных карт (базовый Luhn-like паттерн)
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[REDACTED_CARD]'),

    # SSH приватные ключи
    (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\sKEY-----.*?-----END\s+(?:RSA\s+)?PRIVATE\sKEY-----',
     '[REDACTED_SSH_KEY]'),

    # Строки подключения к БД
    (r'(?i)(mongodb|postgres|mysql|redis|amqp)://[^\s"\']+', '[REDACTED_CONNECTION_STRING]'),

    # .env переменные с секретами
    (r'(?i)^(DB_PASSWORD|SECRET_KEY|JWT_SECRET|ENCRYPTION_KEY|PRIVATE_KEY)\s*=\s*.+$',
     r'\1=[REDACTED]'),
]


def redact_text(text: str) -> str:
    """
    Применяет все паттерны очистки к тексту.
    Возвращает очищенную строку.
    """
    result = text
    for pattern, replacement in REDACT_PATTERNS:
        try:
            result = re.sub(pattern, replacement, result, flags=re.MULTILINE | re.DOTALL)
        except re.error:
            continue
    return result


def is_sensitive(text: str) -> bool:
    """Проверяет, содержит ли текст потенциально конфиденциальные данные."""
    for pattern, _ in REDACT_PATTERNS:
        try:
            if re.search(pattern, text):
                return True
        except re.error:
            continue
    return False


def redact_count(text: str) -> int:
    """Считает количество найденных конфиденциальных фрагментов."""
    count = 0
    for pattern, _ in REDACT_PATTERNS:
        try:
            count += len(re.findall(pattern, text))
        except re.error:
            continue
    return count


# ─── Тест ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_text = """
    server_ip = 192.168.1.100
    api_key = "sk-abc123xyz456def789ghi012jkl345mno"
    password = "SuperSecret123!"
    db_url = postgres://admin:pass@192.168.1.50:5432/mydb
    email: john.doe@company.com
    Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxx.yyy
    AKIAIOSFODNN7EXAMPLE
    
    def calculate_sum(a, b):
        return a + b  # Это безопасный код
    """

    print("=== ОРИГИНАЛ ===")
    print(test_text)
    print(f"\n=== НАЙДЕНО СЕКРЕТОВ: {redact_count(test_text)} ===")
    print("\n=== ОЧИЩЕНО ===")
    print(redact_text(test_text))
