"""Redact recognizable credentials before chat/search results reach an agent.

This is pattern-based display protection, not a guarantee that arbitrary text
contains no secrets. Raw local databases and explicit exports are unchanged.
"""
import re

REDACTED = "[REDACTED]"
_LABEL = r"(?:[a-zA-Z][a-zA-Z0-9]*[_-])*(?:api[ _-]?key|(?:access|refresh|auth)[ _-]?token|token|password|passwd|pwd|(?:client[ _-]?)?secret|密码|口令|密钥)"
_ASSIGNMENT = re.compile(
    rf"(?P<prefix>(?<![a-zA-Z0-9_]){_LABEL}[\"']?\s*[:：=]\s*)"
    r"(?P<value>\"(?:\\.|[^\"\\\r\n])*\"|'(?:\\.|[^'\\\r\n])*'|`[^`\r\n]*`|[^\s&,;，；<>\"']+)",
    re.IGNORECASE,
)
_AUTH = re.compile(r"\b(?P<scheme>Bearer|Basic)[ \t]+[a-zA-Z0-9._~+/=-]{12,}", re.IGNORECASE)
_URL_PASSWORD = re.compile(r"(?P<prefix>\b[a-z][a-z0-9+.-]*://[^\s/@:]+:)[^@\s/]+(?=@)", re.IGNORECASE)
_API_KEY = re.compile(r"(?<![a-zA-Z0-9_-])sk-[a-zA-Z0-9_-]{12,}")
_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9]+ )?PRIVATE KEY-----"
)


def _assignment(match):
    value = match.group("value")
    if value in ("\"\"", "''", "``"):
        return match.group(0)
    if value[0] in "\"'`" and value[-1] == value[0]:
        return match.group("prefix") + value[0] + REDACTED + value[-1]
    return match.group("prefix") + REDACTED


def redact_text(text):
    text = _PRIVATE_KEY.sub(REDACTED, text)
    text = _ASSIGNMENT.sub(_assignment, text)
    text = _URL_PASSWORD.sub(lambda m: m.group("prefix") + REDACTED, text)
    text = _AUTH.sub(lambda m: m.group("scheme") + " " + REDACTED, text)
    return _API_KEY.sub(REDACTED, text)
