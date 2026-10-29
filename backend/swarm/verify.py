"""Checks that a quote really appears in its source, so nothing a model invents is shown as someone's words."""

import re
import unicodedata

MIN_WORDS = 5

# Curly quotes become straight ones; dashes, ellipses and hyphens become spaces.
_PLAIN = str.maketrans(
    {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x2013: " ", 0x2014: " ", 0x2026: " ", "-": " "}
)


def normalize(text: str) -> str:
    """Case, spacing, curly quotes, dashes and look-alike characters vary between a paper and a model's copy of it,
    so they're ignored. Typeset papers use ligatures like "\ufb01" for "fi", which NFKC turns back into letters."""
    text = unicodedata.normalize("NFKC", text).lower().translate(_PLAIN)
    return re.sub(r"\s+", " ", text).strip(" .\"'")


def found_in(quote: str, source: str) -> bool:
    q = normalize(quote)
    return len(q.split()) >= MIN_WORDS and q in normalize(source)
