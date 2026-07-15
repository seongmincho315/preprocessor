"""dots_mocr 계열 4가지 layout 전략의 __call__ 계약을 네트워크 없이 검증한다.

실제 HTTP 호출(DotsMocrClient._post)은 여기서 다루지 않는다 - 각 클래스에 가짜
클라이언트(FakeClient)를 주입해, "region을 받아 카테고리/텍스트를 어떻게 조립하는지"만
검증한다. HTTP 왕복/JSON 파싱 자체는 test_dots_mocr_client.py에서 다룬다.
"""

import pytest

from util.dots_mocr_all_layout import DotsMocrAllLayout
from util.dots_mocr_auto_layout import DotsMocrAutoLayout
from util.dots_mocr_grounding_layout import DotsMocrGroundingLayout
from util.dots_mocr_layout import DotsMocrLayout

pytestmark = pytest.mark.unit


def _make(cls):
    """생성자의 네트워크 검증(url 필수)을 건너뛰고 가짜 _client를 주입할 빈 인스턴스를 만든다."""
    return cls.__new__(cls)


class FakeDetectClient:
    """detect_raw_regions/rescale_regions만 쓰는 전략(dots_mocr, dots_mocr_all)용 스텁."""

    def __init__(self, regions):
        self.regions = regions

    def detect_raw_regions(self, image, prompt=None):
        return self.regions

    def rescale_regions(self, regions, image):
        return regions  # 테스트에서는 스케일 보정 자체를 검증하지 않음(client 테스트에서 다룸)


class TestDotsMocrLayout:
    def test_empty_lines_returns_empty(self):
        layout = _make(DotsMocrLayout)
        assert layout([], image=b"x") == []

    def test_no_image_defaults_to_text(self):
        layout = _make(DotsMocrLayout)
        lines = [("a", (0, 0, 1, 1), 10.0), ("b", (0, 0, 1, 1), 10.0)]
        assert layout(lines, image=None) == ["text", "text"]

    def test_matches_lines_to_detected_regions(self):
        layout = _make(DotsMocrLayout)
        layout._client = FakeDetectClient(
            [{"label": "Section-header", "text": None, "l": 0, "t": 0, "r": 100, "b": 20}]
        )
        lines = [
            ("heading", (10, 5, 90, 15), 14.0),  # region 안
            ("body", (10, 50, 90, 60), 10.0),  # region 밖
        ]
        assert layout(lines, image=b"x") == ["section_header", "text"]


class TestDotsMocrAllLayout:
    def test_no_image_returns_empty(self):
        layout = _make(DotsMocrAllLayout)
        assert layout([], image=None) == []

    def test_builds_items_from_region_text(self):
        layout = _make(DotsMocrAllLayout)
        layout._client = FakeDetectClient(
            [
                {"label": "Title", "text": "  My Title  ", "l": 0, "t": 0, "r": 10, "b": 10},
                {"label": "Picture", "text": None, "l": 0, "t": 20, "r": 10, "b": 30},
                {"label": "Text", "text": "   ", "l": 0, "t": 40, "r": 10, "b": 50},
            ]
        )
        items = layout([], image=b"x")
        assert items == [
            {"text": "My Title", "category": "title", "bbox": {"x0": 0, "y0": 0, "x1": 10, "y1": 10}}
        ]


class FakeGroundingClient(FakeDetectClient):
    def __init__(self, regions, grounded_text_by_label):
        super().__init__(regions)
        self.grounded_text_by_label = grounded_text_by_label
        self.calls = []

    def call(self, image, prompt=None):
        self.calls.append(prompt)
        assert "Bounding Box" in prompt
        # 마지막으로 detect_raw_regions가 돌려준 region 중 프롬프트에 좌표가 들어간 걸 못 찾을
        # 이유가 없으므로, 테스트에서는 region 순서대로 소비한다.
        return self.grounded_text_by_label.pop(0)


class TestDotsMocrGroundingLayout:
    def test_no_image_returns_empty(self):
        layout = _make(DotsMocrGroundingLayout)
        assert layout([], image=None) == []

    def test_skips_picture_and_empty_text_regions(self):
        layout = _make(DotsMocrGroundingLayout)
        layout._client = FakeGroundingClient(
            regions=[
                {"label": "Title", "text": None, "l": 0, "t": 0, "r": 10, "b": 10},
                {"label": "Picture", "text": None, "l": 0, "t": 20, "r": 10, "b": 30},
                {"label": "Text", "text": None, "l": 0, "t": 40, "r": 10, "b": 50},
            ],
            grounded_text_by_label=["Grounded Title", "   "],
        )
        items = layout([], image=b"x")
        assert items == [
            {"text": "Grounded Title", "category": "title", "bbox": {"x0": 0, "y0": 0, "x1": 10, "y1": 10}}
        ]
        assert len(layout._client.calls) == 2  # Picture는 grounding 호출 자체를 스킵


class TestDotsMocrAutoLayout:
    def test_empty_lines_returns_empty(self):
        layout = _make(DotsMocrAutoLayout)
        assert layout([], image=b"x") == []

    def test_no_image_returns_lines_as_is_with_text_category(self):
        layout = _make(DotsMocrAutoLayout)
        lines = [("clean", (0, 0, 1, 1), 10.0)]
        assert layout(lines, image=None) == [
            {"text": "clean", "category": "text", "bbox": {"x0": 0, "y0": 0, "x1": 1, "y1": 1}}
        ]

    def test_keeps_clean_text_and_regrounds_corrupted_glyphs(self):
        layout = _make(DotsMocrAutoLayout)

        class FakeAutoClient:
            def detect_raw_regions(self, image, prompt=None):
                return [{"label": "Text", "text": None, "l": 0, "t": 0, "r": 1000, "b": 100}]

            def rescale_regions(self, regions, image):
                return regions

            def call(self, image, prompt=None):
                assert "Bounding Box" in prompt
                return "regrounded"

        layout._client = FakeAutoClient()
        lines = [
            ("clean text", (10, 10, 90, 30), 10.0),
            ("� broken", (10, 40, 90, 60), 10.0),
        ]
        items = layout(lines, image=b"x")
        assert items[0]["text"] == "clean text"
        assert items[1]["text"] == "regrounded"

    def test_corrupted_line_outside_any_region_keeps_original_text(self):
        layout = _make(DotsMocrAutoLayout)

        class FakeNoRegionClient:
            def detect_raw_regions(self, image, prompt=None):
                return [{"label": "Text", "text": None, "l": 0, "t": 0, "r": 10, "b": 10}]

            def rescale_regions(self, regions, image):
                return regions

            def call(self, image, prompt=None):
                raise AssertionError("region이 없으면 grounding을 호출하면 안 된다")

        layout._client = FakeNoRegionClient()
        lines = [("� broken", (5000, 5000, 5010, 5010), 10.0)]
        items = layout(lines, image=b"x")
        assert items[0]["text"] == "� broken"
