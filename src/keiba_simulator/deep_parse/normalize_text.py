from __future__ import annotations

import re
import unicodedata

_CORRECTIONS = {
    "O": "0",
    "o": "0",
    "l": "1",
    "I": "1",
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = _fix_numeric_neighbors(normalized)
    return normalized


def _fix_numeric_neighbors(text: str) -> str:
    chars = list(text)
    for idx, char in enumerate(chars):
        if char not in _CORRECTIONS:
            continue
        prev_is_digit = idx > 0 and chars[idx - 1].isdigit()
        next_is_digit = idx + 1 < len(chars) and chars[idx + 1].isdigit()
        if prev_is_digit or next_is_digit:
            chars[idx] = _CORRECTIONS[char]
    return "".join(chars)
