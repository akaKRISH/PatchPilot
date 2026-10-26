"""Text redaction for sensitive credentials and tokens."""

import re

# Regular expressions for detecting sensitive tokens and secrets
SENSITIVE_PATTERNS = [
    (
        re.compile(
            r"(?i)(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----"),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"sk-[a-zA-Z0-9]{32,}"), "[REDACTED_API_KEY]"),
]


def redact_sensitive_text(text: str) -> str:
    """Scan and redact known credential and secret patterns from strings."""
    if not text:
        return text

    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized
