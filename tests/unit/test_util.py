from pathlib import Path

import fitz
import pytest

from util.util import file_split, get_ext, has_glyph_corruption, is_glyph_corrupted

pytestmark = pytest.mark.unit

REPLACEMENT_CHAR = "�"  # U+FFFD, 매핑 실패 시 나오는 대체 문자
PUA_CHAR = ""  # Private Use Area 시작 코드포인트


def _make_pdf(path: Path, num_pages: int) -> None:
    doc = fitz.open()
    for _ in range(num_pages):
        doc.new_page()
    doc.save(str(path))
    doc.close()


class TestGetExt:
    def test_pdf(self, tmp_path):
        path = tmp_path / "sample.pdf"
        _make_pdf(path, 1)
        assert get_ext(str(path)) == "pdf"

    def test_unknown_format_raises(self, tmp_path):
        path = tmp_path / "garbage.bin"
        path.write_bytes(b"not a real document")
        with pytest.raises(ValueError):
            get_ext(str(path))


class TestFileSplit:
    def test_below_threshold_returns_original_path(self, tmp_path):
        path = tmp_path / "small.pdf"
        _make_pdf(path, 3)

        result = file_split(str(path), max_page_split=50, base_dir=tmp_path)

        assert result == [str(path)]

    def test_above_threshold_splits_into_multiple_files(self, tmp_path):
        path = tmp_path / "big.pdf"
        _make_pdf(path, 5)

        result = file_split(str(path), max_page_split=2, base_dir=tmp_path)

        assert len(result) == 3  # ceil(5 / 2)
        for split_path in result:
            assert Path(split_path).exists()

    def test_non_pdf_passes_through_unchanged(self, tmp_path):
        path = tmp_path / "sample.html"
        path.write_text("<html><body><p>hi</p></body></html>", encoding="utf-8")

        result = file_split(str(path), max_page_split=1, base_dir=tmp_path)

        assert result == [str(path)]


class TestHasGlyphCorruption:
    CLEAN = [("hello world", (0, 0, 1, 1), 10.0), ("another normal line", (0, 0, 1, 1), 10.0)]

    def test_clean_text_not_flagged(self):
        assert has_glyph_corruption(self.CLEAN) is False

    def test_exactly_at_threshold_not_flagged(self):
        # 기본 threshold=3: 정확히 3개는 넘지 않으므로(strictly greater) 아직 미탐지
        lines = [(REPLACEMENT_CHAR * 3 + " ok", (0, 0, 1, 1), 10.0)]
        assert has_glyph_corruption(lines) is False

    def test_over_threshold_flagged(self):
        lines = [(REPLACEMENT_CHAR * 4 + " ok", (0, 0, 1, 1), 10.0)]
        assert has_glyph_corruption(lines) is True

    def test_private_use_area_chars_flagged(self):
        lines = [(PUA_CHAR * 4 + " broken", (0, 0, 1, 1), 10.0)]
        assert has_glyph_corruption(lines) is True

    def test_empty_lines_not_flagged(self):
        assert has_glyph_corruption([]) is False


class TestIsGlyphCorrupted:
    def test_clean_text_not_flagged(self):
        assert is_glyph_corrupted("hello world") is False

    def test_single_bad_char_flagged_at_default_threshold(self):
        # has_glyph_corruption과 달리 줄 단위 threshold 기본값은 1(>=)이라 하나만 있어도 감지된다.
        assert is_glyph_corrupted(REPLACEMENT_CHAR + " ok") is True

    def test_private_use_area_char_flagged(self):
        assert is_glyph_corrupted(PUA_CHAR + " ok") is True

    def test_empty_text_not_flagged(self):
        assert is_glyph_corrupted("") is False

    def test_custom_threshold_respected(self):
        assert is_glyph_corrupted(REPLACEMENT_CHAR * 2, threshold=3) is False
        assert is_glyph_corrupted(REPLACEMENT_CHAR * 3, threshold=3) is True
