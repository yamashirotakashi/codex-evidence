from __future__ import annotations

import re

_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]+|[A-Za-z0-9_]*TOKEN[A-Za-z0-9_]*\s*[:=]\s*\S+)",
    re.IGNORECASE,
)


def redact_text(text: str) -> str:
    return _SECRET_PATTERN.sub("[REDACTED_SECRET]", text)


def redact_payload(value: object) -> object:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {str(key): redact_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    return value
