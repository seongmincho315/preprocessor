import pytest

from loader.pdf.pymupdf import Loader

pytestmark = pytest.mark.unit


def _span(text, size, x0, x1, y0=0.0, y1=10.0):
    return {"text": text, "size": size, "bbox": (x0, y0, x1, y1)}


def test_join_spans_inserts_space_across_wide_gap():
    # 볼드 span("world")과 일반 span("hello ")이 폰트 크기 대비 넓게 떨어져 있으면
    # 원본에 있었을 공백을 복원해야 한다.
    spans = [_span("hello", 10.0, x0=0, x1=30), _span("world", 10.0, x0=33, x1=63)]

    assert Loader._join_spans(spans) == "hello world"


def test_join_spans_does_not_double_space_when_gap_already_has_space():
    spans = [_span("hello ", 10.0, x0=0, x1=32), _span("world", 10.0, x0=33, x1=63)]

    assert Loader._join_spans(spans) == "hello world"


def test_join_spans_keeps_kerned_spans_together_without_extra_space():
    # 커닝 등으로 span 사이 간격이 좁으면(폰트 크기 대비) 같은 단어의 일부로 본다.
    spans = [_span("wor", 10.0, x0=0, x1=15), _span("ld", 10.0, x0=15.5, x1=25)]

    assert Loader._join_spans(spans) == "world"


def test_dominant_font_size_ignores_short_leading_span():
    # 각주 번호처럼 글자 수가 적은 span이 줄 맨 앞에 와도, 본문 span의 크기를
    # 그 줄의 대표 폰트 크기로 써야 한다.
    spans = [_span("12", 6.0, x0=0, x1=5), _span("본문 내용입니다", 10.0, x0=6, x1=80)]

    assert Loader._dominant_font_size(spans) == 10.0


def test_extract_lines_uses_dominant_size_and_restores_spacing(tmp_path):
    fitz = pytest.importorskip("fitz")

    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # 각주 번호(작은 폰트) 뒤에 본문(큰 폰트)이 이어지는 한 줄을 만든다.
    page.insert_text((72, 72), "12", fontsize=6)
    page.insert_text((80, 72), "hello world", fontsize=14)
    doc.save(str(pdf_path))
    doc.close()

    opened = fitz.open(str(pdf_path))
    try:
        lines = Loader._extract_lines(opened[0])
    finally:
        opened.close()

    assert len(lines) == 1
    text, _, font_size = lines[0]
    assert "hello world" in text
    assert font_size == 14.0


def test_extract_words_gives_real_per_word_bboxes_not_whole_line(tmp_path):
    """tableformer의 cell 매칭용 - 줄 전체가 아니라 PDF 원본 단어 단위 bbox를 내야 한다."""
    fitz = pytest.importorskip("fitz")

    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello world", fontsize=14)
    doc.save(str(pdf_path))
    doc.close()

    opened = fitz.open(str(pdf_path))
    try:
        words = Loader._extract_words(opened[0])
    finally:
        opened.close()

    assert [w[0] for w in words] == ["hello", "world"]
    hello_bbox, world_bbox = words[0][1], words[1][1]
    # 서로 다른(진짜 PDF에서 온) bbox이고, "hello"가 "world"보다 왼쪽에 있어야 한다.
    assert hello_bbox != world_bbox
    assert hello_bbox[2] < world_bbox[0]
