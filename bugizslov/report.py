from collections.abc import Mapping
from html import escape


FIELDS = {
    "title": "Заголовок",
    "page": "Сайт и страница",
    "environment": "Окружение",
    "preconditions": "Предусловия",
    "steps": "Шаги воспроизведения",
    "expected_result": "Ожидаемый результат",
    "actual_result": "Фактический результат",
    "reproducibility": "Повторяемость",
}

ICONS = {
    "page": "🔗",
    "environment": "🖥",
    "preconditions": "🔎",
    "steps": "🧭",
    "expected_result": "🎯",
    "actual_result": "⚠️",
    "reproducibility": "🔁",
}


def report_title(fields: Mapping[str, object]) -> str:
    title = fields.get("title")
    if isinstance(title, str) and title.strip() and title.strip().lower() not in {"не указано", "unknown", "null"}:
        return title.strip().rstrip(".")

    actual = fields.get("actual_result")
    if isinstance(actual, str):
        if "segmentation fault" in actual.lower():
            return "Программа завершается с segmentation fault"
        if actual.strip() and actual.strip().lower() not in {"не указано", "unknown", "null"}:
            compact = " ".join(actual.split()).rstrip(".")
            return f"Сбой при выполнении: {compact[:100]}".rstrip()
    return "Не указано"


def _value(fields: Mapping[str, object], key: str) -> str:
    value = fields.get(key)
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        if key == "steps":
            return "\n".join(f"{i}. {item}" for i, item in enumerate(parts, 1))
        return "; ".join(parts)
    if value is None:
        return "Не указано"
    text = "\n".join(line.rstrip() for line in str(value).splitlines()).strip()
    if not text or text.lower() in {"не указано", "unknown", "null"}:
        return "Не указано"
    if key == "steps" and "\n" in text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(
            line if line[:1].isdigit() and ("." in line[:4] or ")" in line[:4]) else f"{i}. {line}"
            for i, line in enumerate(lines, 1)
        )
    return text


def render_report(fields: Mapping[str, object]) -> str:
    title = report_title(fields)
    lines = [f"# 🐞 {title}", "", "Черновик для проверки автором.", "", "---", ""]
    for key, label in FIELDS.items():
        if key == "title":
            continue
        value = _value(fields, key)
        icon = ICONS.get(key, "📌")
        lines.extend((f"### {icon} {label}", "", value, ""))
    return "\n".join(lines).rstrip() + "\n"


def _escaped_limited(text: str, limit: int) -> tuple[str, bool]:
    chunks: list[str] = []
    size = 0
    truncated = False
    for char in text:
        encoded = escape(char)
        if size + len(encoded) > limit:
            truncated = True
            break
        chunks.append(encoded)
        size += len(encoded)
    return "".join(chunks), truncated


def render_report_html(fields: Mapping[str, object], value_limit: int = 400) -> str:
    """Readable Telegram rendering; the downloadable Markdown remains complete."""
    title, title_truncated = _escaped_limited(report_title(fields), 500)
    had_truncation = title_truncated
    sections = [
        "<b>🐞 БАГ-РЕПОРТ</b>",
        f"<b>{title}</b>",
        "<i>Черновик — проверьте факты перед отправкой.</i>",
    ]
    for key, label in FIELDS.items():
        if key == "title":
            continue
        value = _value(fields, key)
        safe_value, truncated = _escaped_limited(value, value_limit)
        had_truncation = had_truncation or truncated
        # Telegram's HTML parser does not support <br>; literal newlines are supported.
        if value == "Не указано":
            safe_value = f"<i>{safe_value}</i>"
        sections.append(f"<b>{ICONS.get(key, '📌')} {escape(label)}</b>\n{safe_value}")
    if had_truncation:
        sections.append("<i>Длинные поля сокращены в сообщении. Полный текст доступен в файле .md.</i>")
    return "\n\n".join(sections)
