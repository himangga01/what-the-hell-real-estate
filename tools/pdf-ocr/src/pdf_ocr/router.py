from __future__ import annotations

import unicodedata
from enum import Enum


class PageRoute(str, Enum):
    EMBEDDED_TEXT = "EMBEDDED_TEXT"
    RAPIDOCR = "RAPIDOCR"
    RAPIDOCR_TABLEFORMER = "RAPIDOCR_TABLEFORMER"


def embedded_text_quality(text: str) -> tuple[int, float]:
    non_whitespace = [character for character in text if not character.isspace()]
    if not non_whitespace:
        return 0, 0.0

    invalid_count = sum(
        character == "\ufffd" or unicodedata.category(character) in {"Cc", "Cs"}
        for character in non_whitespace
    )
    return len(non_whitespace), invalid_count / len(non_whitespace)


def select_page_route(
    text: str,
    *,
    has_table: bool,
    has_complex_layout: bool,
) -> PageRoute:
    if has_table:
        return PageRoute.RAPIDOCR_TABLEFORMER
    if has_complex_layout:
        return PageRoute.RAPIDOCR

    non_whitespace_chars, invalid_character_ratio = embedded_text_quality(text)
    if non_whitespace_chars < 30 or invalid_character_ratio > 0.05:
        return PageRoute.RAPIDOCR
    return PageRoute.EMBEDDED_TEXT
