from collections.abc import Mapping


FIELDS = {
    "title": "Заголовок",
    "environment": "Окружение",
    "preconditions": "Предусловия",
    "steps": "Шаги воспроизведения",
    "expected_result": "Ожидаемый результат",
    "actual_result": "Фактический результат",
    "reproducibility": "Повторяемость",
}


def render_report(fields: Mapping[str, object]) -> str:
    lines = ["# Баг-репорт", ""]
    for key, label in FIELDS.items():
        value = fields.get(key)
        if isinstance(value, list):
            value = "\n".join(f"{i}. {item}" for i, item in enumerate(value, 1))
        text = str(value).strip() if value not in (None, "", []) else "не указано"
        lines.extend((f"## {label}", text, ""))
    return "\n".join(lines).rstrip() + "\n"
