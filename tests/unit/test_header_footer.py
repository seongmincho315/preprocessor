import pytest

from util.header_footer import strip_repeated_headers_footers

pytestmark = pytest.mark.unit


def _item(text, page, y0, y1, x0=0.0, x1=100.0):
    return {"text": text, "category": "text", "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1}, "page": page}


def _page(page_no, header_text, body_texts, footer_text):
    items = [_item(header_text, page_no, y0=0, y1=8)]
    y = 20
    for body in body_texts:
        items.append(_item(body, page_no, y0=y, y1=y + 10))
        y += 12
    items.append(_item(footer_text, page_no, y0=290, y1=298))
    return items


def test_strips_header_and_footer_repeated_across_pages():
    items = []
    for page_no in range(1, 6):
        items += _page(page_no, "My Document Title", [f"body text on page {page_no}"], "Confidential")

    result = strip_repeated_headers_footers(items)

    assert [it["text"] for it in result] == [f"body text on page {p}" for p in range(1, 6)]


def test_page_numbers_are_recognized_despite_changing_digits():
    items = []
    for page_no in range(1, 6):
        items += _page(page_no, "Report", [f"body text on page {page_no}"], f"Page {page_no} of 5")

    result = strip_repeated_headers_footers(items)

    assert "Report" not in [it["text"] for it in result]
    assert not any(it["text"].startswith("Page ") for it in result)
    assert len(result) == 5


def test_body_text_that_happens_to_repeat_is_kept_if_not_in_edge_band():
    items = []
    for page_no in range(1, 6):
        items += _page(page_no, "Title", ["see appendix for details"], "Footer")

    result = strip_repeated_headers_footers(items)

    # 본문 밴드에 있는 반복 문장은 안 지운다.
    assert [it["text"] for it in result] == ["see appendix for details"] * 5


def test_too_few_pages_returns_input_unchanged():
    items = _page(1, "Title", ["body"], "Footer") + _page(2, "Title", ["body"], "Footer")

    result = strip_repeated_headers_footers(items)

    assert result == items


def test_non_repeated_top_line_is_kept():
    items = []
    for page_no in range(1, 6):
        items += _page(page_no, f"Chapter {page_no}", [f"body text on page {page_no}"], "Footer")

    result = strip_repeated_headers_footers(items)

    texts = [it["text"] for it in result]
    assert all(f"Chapter {p}" in texts for p in range(1, 6))
