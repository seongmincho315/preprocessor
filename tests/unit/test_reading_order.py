import pytest

from util.reading_order import reorder_by_category, sort_reading_order

pytestmark = pytest.mark.unit


def _line(text, x0, y0, x1, y1):
    return (text, (x0, y0, x1, y1), 10.0)


def test_single_column_keeps_original_order():
    lines = [_line("first", 0, 0, 100, 10), _line("second", 0, 12, 100, 22), _line("third", 0, 24, 100, 34)]

    result = sort_reading_order(lines)

    assert [text for text, _, _ in result] == ["first", "second", "third"]


def test_two_columns_read_left_column_fully_before_right_column():
    # 왼쪽 칼럼(x: 0~100)과 오른쪽 칼럼(x: 110~210)이 나란히 있는 2단 레이아웃.
    lines = [
        _line("title", 0, 0, 210, 10),  # 전체 폭 제목 - 두 칼럼 모두의 조상
        _line("right1", 110, 12, 210, 22),
        _line("right2", 110, 24, 210, 34),
        _line("left1", 0, 12, 100, 22),
        _line("left2", 0, 24, 100, 34),
    ]

    result = sort_reading_order(lines)

    assert [text for text, _, _ in result] == ["title", "left1", "left2", "right1", "right2"]


def test_full_width_footer_waits_for_both_columns():
    lines = [
        _line("left1", 0, 0, 100, 10),
        _line("left2", 0, 12, 100, 22),
        _line("right1", 110, 0, 210, 10),
        _line("right2", 110, 12, 210, 22),
        _line("footer", 0, 24, 210, 34),  # 두 칼럼이 다 끝난 뒤에만 와야 한다
    ]

    result = sort_reading_order(lines)

    assert [text for text, _, _ in result] == ["left1", "left2", "right1", "right2", "footer"]


def test_empty_and_single_line_are_noop():
    assert sort_reading_order([]) == []

    single = [_line("only", 0, 0, 10, 10)]
    assert sort_reading_order(single) == single


def test_reorder_by_category_leaves_formula_fragments_untouched():
    # PyMuPDF가 "E f(X) = ∫ f(x) dpX(x) . (1.4)" 한 줄을 여러 조각으로 쪼개서 주는
    # 실제 상황 재현: 적분 기호("Z")는 키가 커서 위/아래로 걸치고, 수식 번호는
    # 오른쪽 멀리 떨어져 있다 - 기하학적으로만 보면 서로 다른 칼럼처럼 보인다.
    lines = [
        _line("on X:", 0, 0, 30, 10),
        _line("E f(X) =", 40, 5, 80, 15),
        _line("Z", 85, 0, 90, 20),  # 적분 기호 - formula
        _line("f(x) dpX(x) .", 95, 8, 150, 18),  # formula
        _line("(1.4)", 200, 8, 220, 18),  # 수식 번호 - formula
        _line("Sometimes we may write", 0, 25, 100, 35),
    ]
    categories = ["text", "formula", "formula", "formula", "formula", "text"]

    result_lines, result_categories = reorder_by_category(lines, categories)

    texts = [text for text, _, _ in result_lines]
    assert texts == ["on X:", "E f(X) =", "Z", "f(x) dpX(x) .", "(1.4)", "Sometimes we may write"]
    assert result_categories == categories


def test_reorder_by_category_reorders_only_flow_lines_across_columns():
    lines = [
        _line("title", 0, 0, 210, 10),
        _line("right1", 110, 12, 210, 22),
        _line("left1", 0, 12, 100, 22),
        _line("chart", 0, 24, 210, 40),  # 재정렬 대상이 아닌 카테고리
    ]
    categories = ["title", "text", "text", "chart"]

    result_lines, result_categories = reorder_by_category(lines, categories)

    # chart는 원래(재정렬 전) 순서에서 바로 앞이던 left1을 따라간다 - left1이
    # right1보다 먼저 오도록 재정렬됐으므로, chart도 그 새 위치 바로 뒤에 붙는다.
    texts = [text for text, _, _ in result_lines]
    assert texts == ["title", "left1", "chart", "right1"]
    assert result_categories == ["title", "text", "chart", "text"]


def test_reorder_by_category_keeps_leading_pinned_lines_first():
    lines = [_line("page_header", 0, 0, 200, 8), _line("b", 0, 20, 100, 30), _line("a", 0, 10, 100, 19)]
    categories = ["page_header", "text", "text"]

    result_lines, _ = reorder_by_category(lines, categories)

    assert [text for text, _, _ in result_lines] == ["page_header", "a", "b"]


def test_reorder_by_category_noop_with_fewer_than_two_flow_lines():
    lines = [_line("only text", 0, 0, 100, 10), _line("formula", 0, 20, 100, 30)]
    categories = ["text", "formula"]

    result_lines, result_categories = reorder_by_category(lines, categories)

    assert result_lines == lines
    assert result_categories == categories
