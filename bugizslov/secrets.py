import re


_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:password|passwd|пароль)\s*[:=]\s*\S+"),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{25,}\b"),  # Telegram bot token
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\b(?:api[_ -]?key|access[_ -]?token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}"),
)


def contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)
