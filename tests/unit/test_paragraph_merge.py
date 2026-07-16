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
