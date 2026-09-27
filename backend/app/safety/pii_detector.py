"""Detect personal / financial identifiers in user input.

Runs before anything else. When PII is found the question is not embedded,
not sent to Ollama, and never logged.
"""

from __future__ import annotations

import re

PII_REFUSAL = (
    "Please don't share personal or financial account information here. "
    "This assistant only provides general mutual-fund facts."
)

_PATTERNS: dict[str, re.Pattern[str]] = {
    # Indian PAN: 5 letters, 4 digits, 1 letter.
    "PAN": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.I),
    # Aadhaar: 12 digits, optionally grouped 4-4-4 (first digit 2-9).
    "AADHAAR": re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "EMAIL": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    # Indian mobile numbers, with optional +91 / 0 prefix.
    "PHONE": re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"),
    # OTP / PIN / password disclosures ("my otp is 123456", "password: hunter2").
    "OTP": re.compile(r"\b(otp|one[\s-]?time[\s-]?password|m?pin)\b\W{0,5}(is\W{0,3})?\d{4,8}\b", re.I),
    "PASSWORD": re.compile(r"\b(password|passcode|pwd)\b\s*(is|:|=)\s*\S+", re.I),
    # Folio numbers ("folio 1234567", "folio no: 12345/67").
    "FOLIO": re.compile(r"\bfolio\b\s*(no\.?|number|num|#)?\s*[:\-]?\s*\d[\d/]{3,}", re.I),
    # Bank account numbers when labelled, or any long bare digit run.
    "BANK_ACCOUNT": re.compile(
        r"\b(a/?c|account|acct)\s*(no\.?|number|num|#)?\s*[:\-]?\s*\d{6,18}\b"
        r"|(?<![\d.,])\d{9,18}(?![\d.,%])",
        re.I,
    ),
    "IFSC": re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
    "CARD": re.compile(r"\b(?:\d{4}[\s-]){3}\d{4}\b"),
}


def detect_pii(text: str) -> list[str]:
    """Return the list of PII types found (empty list when clean)."""
    return [name for name, pattern in _PATTERNS.items() if pattern.search(text)]


def contains_pii(text: str) -> bool:
    return bool(detect_pii(text))
