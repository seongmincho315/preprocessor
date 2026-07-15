import pytest

from util.dots_mocr_client import (
    DotsMocrClient,
    _png_size,
    _smart_resize,
    grounding_prompt,
    match_region,
    match_region_index,
    parse_layout_json,
    to_category,
)

pytestmark = pytest.mark.unit


class TestParseLayoutJson:
    def test_plain_json_array(self):
        content = '[{"bbox": [1, 2, 3, 4], "category": "Title", "text": "hi"}]'
        assert parse_layout_json(content) == [
            {"label": "Title", "text": "hi", "l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0}
        ]

    def test_strips_code_fence(self):
        content = '```json\n[{"bbox": [1, 2, 3, 4], "category": "Text"}]\n```'
        regions = parse_layout_json(content)
        assert regions == [{"label": "Text", "text": None, "l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0}]

    def test_recovers_truncated_array(self):
        # 두 번째 원소가 토큰 한도로 중간에 잘린 경우: 완전한 첫 원소만 복구된다.
        content = (
            '[{"bbox": [1, 2, 3, 4], "category": "Text", "text": "a"}, '
            '{"bbox": [5, 6, 7, 8], "category": "Title", "text": "trunc'
        )
        assert parse_layout_json(content) == [
            {"label": "Text", "text": "a", "l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0}
        ]

    def test_garbage_returns_empty_list(self):
        assert parse_layout_json("no json here at all") == []

    def test_skips_elements_missing_bbox_or_category(self):
        content = '[{"bbox": [1, 2, 3, 4]}, {"category": "Text"}, {"bbox": [1,2,3], "category": "Text"}]'
        assert parse_layout_json(content) == []


class TestToCategory:
    @pytest.mark.parametrize(
        "label, expected",
        [
            ("Section-header", "section_header"),
            ("Page-footer", "page_footer"),
            ("List-item", "list_item"),
            ("Text", "text"),
            ("Some Unknown Label", "text"),
        ],
    )
    def test_normalizes(self, label, expected):
        assert to_category(label) == expected


class TestMatchRegion:
    REGIONS = [
        {"label": "Text", "l": 0, "t": 0, "r": 100, "b": 100},
        {"label": "Title", "l": 10, "t": 10, "r": 50, "b": 50},  # 더 작은, 겹치는 region
    ]

    def test_picks_smallest_containing_region(self):
        match = match_region((20, 20, 30, 30), self.REGIONS)
        assert match["label"] == "Title"

    def test_index_matches_dict_result(self):
        idx = match_region_index((20, 20, 30, 30), self.REGIONS)
        assert idx == 1

    def test_no_match_returns_none(self):
        assert match_region((500, 500, 510, 510), self.REGIONS) is None
        assert match_region_index((500, 500, 510, 510), self.REGIONS) is None


def test_grounding_prompt_appends_rounded_bbox():
    prompt = grounding_prompt((10.4, 10.6, 99.5, 49.5))
    assert prompt.endswith("[10, 11, 100, 50]")
    assert "Bounding Box" in prompt


class TestSmartResize:
    def test_within_pixel_budget_rounds_to_factor(self):
        h, w = _smart_resize(height=1754, width=1240, factor=28)
        assert h % 28 == 0 and w % 28 == 0

    def test_invalid_size_raises(self):
        with pytest.raises(ValueError):
            _smart_resize(height=0, width=100)

    def test_extreme_aspect_ratio_raises(self):
        with pytest.raises(ValueError):
            _smart_resize(height=1, width=1000)


class TestPngSize:
    def test_reads_ihdr_dimensions(self):
        import struct
        import zlib

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", 123, 456, 8, 2, 0, 0, 0)
        png = sig + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")
        assert _png_size(png) == (123, 456)

    def test_non_png_returns_none(self):
        assert _png_size(b"not a png") is None


class TestDotsMocrClient:
    def test_missing_url_raises(self):
        with pytest.raises(ValueError):
            DotsMocrClient({}, "default prompt")

    def test_defaults_applied(self):
        client = DotsMocrClient({"url": "http://localhost:1"}, "default prompt")
        assert client.prompt == "default prompt"
        assert client.max_completion_tokens == 16384
        assert client.temperature == 0.1
        assert client.top_p == 0.9
        assert client.repetition_penalty == 1.15
        assert client.image_token_prefix == ""

    def test_explicit_config_overrides_defaults(self):
        client = DotsMocrClient(
            {"url": "http://localhost:1", "prompt": "custom", "max_tokens": 999, "repetition_penalty": None},
            "default prompt",
        )
        assert client.prompt == "custom"
        assert client.max_completion_tokens == 999
        assert client.repetition_penalty is None

    def test_rescale_regions_empty_input(self):
        client = DotsMocrClient({"url": "http://localhost:1"}, "default prompt")
        assert client.rescale_regions([], b"irrelevant") == []
