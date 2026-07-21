"""DetrLayout이 이식한 docling LayoutPostprocessor 로직(confidence 필터/label remap/전체
페이지 picture 제거/겹침 제거/최적 겹침 기반 줄 매칭)을 네트워크 없이 검증한다.

실제 HTTP 호출(``DetrLayout._detect``)은 여기서 다루지 않는다 - `_detect`를 스텁으로
교체해 "region을 받아 카테고리를 어떻게 조립하는지"만 검증한다.
"""

import pytest

from util.detr_layout import DetrLayout

pytestmark = pytest.mark.unit


def _make(regions):
    """네트워크 검증(url 필수)을 건너뛰고, ``_detect`` 를 고정 region으로 스텁한 인스턴스를 만든다.

    ``image_dpi=72`` 로 둬 스케일(``image_dpi/72``)이 1.0이 되게 하고, region의 l/t/r/b를
    그대로 PDF 포인트 좌표로 취급할 수 있게 한다.
    """
    layout = DetrLayout.__new__(DetrLayout)
    layout.image_dpi = 72
    layout.timeout = 60
    layout._detect = lambda image: regions
    return layout


def _region(label, l, t, r, b, confidence=0.9):
    return {"label": label, "confidence": confidence, "l": l, "t": t, "r": r, "b": b}


class TestDetrLayout:
    def test_empty_lines_returns_empty(self):
        layout = _make([])
        assert layout([], image=b"x") == []

    def test_no_image_defaults_to_text(self):
        layout = _make([])
        lines = [("a", (0, 0, 1, 1), 10.0), ("b", (0, 0, 1, 1), 10.0)]
        assert layout(lines, image=None) == ["text", "text"]

    def test_matches_line_to_best_overlapping_region(self):
        """중심점 포함이 아니라, 줄 면적 대비 겹침 비율이 가장 큰 region이 이긴다."""
        layout = _make(
            [
                _region("Text", 0, 0, 10, 5),  # line과 겹침 비율 50/100=0.5
                _region("Table", 0, 0, 4, 10),  # line과 겹침 비율 40/100=0.4
            ]
        )
        lines = [("body", (0, 0, 10, 10), 10.0)]
        assert layout(lines, image=b"x") == ["text"]

    def test_low_overlap_falls_back_to_text(self):
        """겹침 비율이 min_overlap(0.2) 밑이면 매칭하지 않는다."""
        layout = _make([_region("Table", 0, 0, 2, 2)])  # line과 겹침 4/100=0.04
        lines = [("body", (0, 0, 10, 10), 10.0)]
        assert layout(lines, image=b"x") == ["text"]

    def test_low_confidence_region_is_dropped(self):
        """카테고리별 CONFIDENCE_THRESHOLDS 미만이면 region 자체를 버린다(table 기준 0.5)."""
        layout = _make([_region("Table", 0, 0, 10, 10, confidence=0.3)])
        lines = [("body", (0, 0, 10, 10), 10.0)]
        assert layout(lines, image=b"x") == ["text"]

    def test_title_remapped_to_section_header(self):
        layout = _make([_region("Title", 0, 0, 10, 10, confidence=0.9)])
        lines = [("heading", (0, 0, 10, 10), 14.0)]
        assert layout(lines, image=b"x") == ["section_header"]

    def test_list_item_preferred_over_similar_area_text(self):
        """겹치는 list_item/text 중 area가 비슷하면(20% 이내) confidence와 무관하게
        list_item이 이긴다(docling의 LIST_ITEM vs TEXT 규칙)."""
        layout = _make(
            [
                _region("List-item", 0, 0, 100, 20, confidence=0.5),
                _region("Text", 0, 0, 100, 18, confidence=0.9),
            ]
        )
        lines = [("- item", (0, 0, 100, 18), 10.0)]
        assert layout(lines, image=b"x") == ["list_item"]

    def test_full_page_picture_false_positive_is_dropped(self, monkeypatch):
        """페이지 면적의 90% 이상을 덮는 picture 감지는 거짓 양성으로 보고 제거한다."""
        monkeypatch.setattr("util.detr_layout.png_size", lambda image: (100, 100))
        layout = _make([_region("Picture", 0, 0, 100, 100, confidence=0.9)])
        lines = [("body", (10, 10, 20, 20), 10.0)]
        assert layout(lines, image=b"x") == ["text"]

    def test_non_full_page_picture_is_kept(self, monkeypatch):
        monkeypatch.setattr("util.detr_layout.png_size", lambda image: (100, 100))
        layout = _make([_region("Picture", 0, 0, 50, 50, confidence=0.9)])
        lines = [("fig", (10, 10, 20, 20), 10.0)]
        assert layout(lines, image=b"x") == ["picture"]
