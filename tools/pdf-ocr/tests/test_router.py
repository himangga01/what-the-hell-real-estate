from pdf_ocr.router import PageRoute, select_page_route


def test_table_always_uses_rapidocr_tableformer() -> None:
    text = "서울특별시 고시 제2026-1호 " * 4

    assert select_page_route(
        text,
        has_table=True,
        has_complex_layout=False,
    ) is PageRoute.RAPIDOCR_TABLEFORMER


def test_table_still_wins_when_layout_is_also_complex() -> None:
    text = "서울특별시 고시 제2026-1호 " * 4

    assert select_page_route(
        text,
        has_table=True,
        has_complex_layout=True,
    ) is PageRoute.RAPIDOCR_TABLEFORMER


def test_clean_simple_text_keeps_embedded_text() -> None:
    text = "서울특별시 고시 제2026-1호 " * 4

    assert select_page_route(
        text,
        has_table=False,
        has_complex_layout=False,
    ) is PageRoute.EMBEDDED_TEXT


def test_complex_non_table_page_uses_rapidocr() -> None:
    text = "서울특별시 고시 제2026-1호 " * 4

    assert select_page_route(
        text,
        has_table=False,
        has_complex_layout=True,
    ) is PageRoute.RAPIDOCR


def test_low_text_page_uses_rapidocr() -> None:
    assert select_page_route(
        "고시",
        has_table=False,
        has_complex_layout=False,
    ) is PageRoute.RAPIDOCR


def test_invalid_character_ratio_uses_rapidocr() -> None:
    text = ("서울특별시 고시 제2026-1호 " * 3) + ("\ufffd" * 10)

    assert select_page_route(
        text,
        has_table=False,
        has_complex_layout=False,
    ) is PageRoute.RAPIDOCR
