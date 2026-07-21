import pytest

from util.paragraph_merge import merge_split_paragraphs

pytestmark = pytest.mark.unit


def _item(text, page, category="text"):
    return {"text": text, "category": category, "bbox": {"x0": 0, "y0": 0, "x1": 10, "y1": 10}, "page": page}


def test_merges_hyphenated_word_split_across_page_break():
    items = [_item("this describes the informa-", 1), _item("tion theory basics.", 2)]

    result = merge_split_paragraphs(items)

    assert len(result) == 1
    assert result[0]["text"] == "this describes the information theory basics."


def test_merges_lowercase_continuation_with_space():
    items = [_item("as we saw in the previous section,", 1), _item("the result follows directly.", 2)]

    result = merge_split_paragraphs(items)

    assert len(result) == 1
    assert result[0]["text"] == "as we saw in the previous section, the result follows directly."


def test_does_not_merge_when_previous_ends_a_sentence():
    items = [_item("This is a complete sentence.", 1), _item("A new paragraph starts here.", 2)]

    result = merge_split_paragraphs(items)

    assert len(result) == 2


def test_does_not_merge_across_non_text_category():
    items = [_item("continues onto the next page-", 1), _item("(1.4)", 1, category="formula"), _item("word", 2)]

    result = merge_split_paragraphs(items)

    assert len(result) == 3


def test_merges_hyphenated_word_split_within_same_page():
    # PDF가 한 줄로 감싸면서 하이픈으로 쪼갠 단어는 페이지 경계가 아니어도 이어붙인다.
    items = [_item("this stays as-", 1), _item("sembled into one word", 1)]

    result = merge_split_paragraphs(items)

    assert len(result) == 1
    assert result[0]["text"] == "this stays assembled into one word"


def test_empty_and_single_item_are_noop():
    assert merge_split_paragraphs([]) == []

    single = [_item("only", 1)]
    assert merge_split_paragraphs(single) == single


def test_merging_same_page_lines_unions_bbox():
    # 여러 줄로 감싸진 문단은 bbox가 첫 줄 크기로 남으면 안 되고, 합쳐진 줄들의 영역을 다 덮어야 한다.
    first = _item("this stays as-", 1)
    first["bbox"] = {"x0": 10, "y0": 100, "x1": 200, "y1": 112}
    second = _item("sembled into one word", 1)
    second["bbox"] = {"x0": 10, "y0": 114, "x1": 150, "y1": 126}

    result = merge_split_paragraphs([first, second])

    assert len(result) == 1
    assert result[0]["bbox"] == {"x0": 10, "y0": 100, "x1": 200, "y1": 126}


def test_merging_across_page_keeps_previous_page_bbox():
    first = _item("this describes the informa-", 1)
    first["bbox"] = {"x0": 10, "y0": 700, "x1": 200, "y1": 712}
    second = _item("tion theory basics.", 2)
    second["bbox"] = {"x0": 10, "y0": 80, "x1": 150, "y1": 92}

    result = merge_split_paragraphs([first, second])

    assert len(result) == 1
    assert result[0]["bbox"] == first["bbox"]
