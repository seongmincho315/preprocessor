"""DetrLayout이 이식한 docling LayoutPostprocessor 로직(confidence 필터/label remap/전체
페이지 picture 제거/겹침 제거/최적 겹침 기반 줄 매칭)을 네트워크 없이 검증한다.

실제 HTTP 호출(``DetrLayout._detect``)은 여기서 다루지 않는다 - `_detect`를 스텁으로
교체해 "region을 받아 카테고리를 어떻게 조립하는지"만 검증한다.
"""

import pytest

from util.detr_layout import DetrLayout
from util.tableformer_client import TableFormer

pytestmark = pytest.mark.unit


def _make(regions):
    """네트워크 검증(url 필수)을 건너뛰고, ``_detect`` 를 고정 region으로 스텁한 인스턴스를 만든다.

    ``image_dpi=72`` 로 둬 스케일(``image_dpi/72``)이 1.0이 되게 하고, region의 l/t/r/b를
    그대로 PDF 포인트 좌표로 취급할 수 있게 한다.
    """
    layout = DetrLayout.__new__(DetrLayout)
    layout.image_dpi = 72
    layout.timeout = 60
    layout.tableformer = None
    layout.PRODUCES_ITEMS = False
    layout._detect = lambda image: regions
    return layout


def _make_with_tableformer(regions, structures):
    """``table_structure`` 가 켜진 인스턴스를 만든다 - tableformer 호출은 고정 응답으로 스텁한다."""
    layout = _make(regions)
    layout.tableformer = type(
        "FakeTableFormer",
        (),
        {"structure": staticmethod(lambda image, table_bboxes, tokens: structures)},
    )()
    layout.PRODUCES_ITEMS = True
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


class TestDetrLayoutTableStructure:
    """table_structure(tableformer)가 켜졌을 때의 PRODUCES_ITEMS 경로."""

    def test_no_table_region_returns_one_item_per_line(self):
        """table region이 없으면 tableformer는 호출되지 않고, 줄마다 아이템 하나씩 낸다."""
        layout = _make_with_tableformer([_region("Title", 0, 0, 10, 10, confidence=0.9)], structures=[])
        lines = [("heading", (0, 0, 10, 10), 14.0)]
        assert layout(lines, image=b"x") == [
            {"text": "heading", "category": "section_header", "bbox": {"x0": 0, "y0": 0, "x1": 10, "y1": 10}}
        ]

    def test_table_lines_merge_into_one_html_item(self):
        """table region에 속한 여러 줄은 tableformer 결과로 HTML 표 아이템 하나로 합쳐진다."""
        table_region = _region("Table", 0, 0, 100, 20, confidence=0.9)
        structure = {
            "num_rows": 1,
            "num_cols": 2,
            "otsl_seq": [],
            "cells": [
                {
                    "start_row_offset_idx": 0,
                    "start_col_offset_idx": 0,
                    "column_header": True,
                    "text_cell_bboxes": [{"t": 0, "l": 0, "token": "A"}],
                },
                {
                    "start_row_offset_idx": 0,
                    "start_col_offset_idx": 1,
                    "column_header": True,
                    "text_cell_bboxes": [{"t": 0, "l": 50, "token": "B"}],
                },
            ],
        }
        layout = _make_with_tableformer([table_region], structures=[structure])
        lines = [("A", (0, 0, 50, 20), 10.0), ("B", (50, 0, 100, 20), 10.0)]

        items = layout(lines, image=b"x")

        assert len(items) == 1
        assert items[0]["category"] == "table"
        assert items[0]["text"] == "<table><tr><th>A</th><th>B</th></tr></table>"
        assert items[0]["bbox"] == {"x0": 0, "y0": 0, "x1": 100, "y1": 20}

    def test_mixed_table_and_text_lines(self):
        """table 줄과 일반 줄이 섞여 있으면, table만 HTML 표 아이템 하나로 합쳐지고
        나머지는 기존처럼 줄마다 아이템 하나씩 유지된다."""
        table_region = _region("Table", 0, 20, 100, 40, confidence=0.9)
        structure = {
            "num_rows": 1,
            "num_cols": 1,
            "cells": [
                {
                    "start_row_offset_idx": 0,
                    "start_col_offset_idx": 0,
                    "text_cell_bboxes": [{"t": 20, "l": 0, "token": "cell"}],
                }
            ],
        }
        layout = _make_with_tableformer([table_region], structures=[structure])
        lines = [("heading", (0, 0, 100, 10), 14.0), ("cell", (0, 20, 100, 40), 10.0)]

        items = layout(lines, image=b"x")

        assert items[0] == {"text": "heading", "category": "text", "bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 10}}
        assert items[1]["category"] == "table"
        assert items[1]["text"] == "<table><tr><td>cell</td></tr></table>"

    def test_sends_word_level_tokens_to_tableformer(self):
        """tableformer.structure()에 줄 전체가 아니라 단어 단위로 쪼갠 토큰이 전달돼야 한다
        (셀 매칭 정확도를 위해 - 줄 전체를 토큰 하나로 주면 매칭이 어긋난다)."""
        table_region = _region("Table", 0, 0, 100, 10, confidence=0.9)
        captured = {}

        def fake_structure(image, table_bboxes, tokens):
            captured["tokens"] = tokens
            return [{"num_rows": 1, "num_cols": 1, "cells": []}]

        layout = _make([table_region])
        layout.tableformer = type("FakeTableFormer", (), {"structure": staticmethod(fake_structure)})()
        layout.PRODUCES_ITEMS = True
        lines = [("hello world", (0, 0, 100, 10), 10.0)]

        layout(lines, image=b"x")

        assert [t["text"] for t in captured["tokens"]] == ["hello", "world"]
        # 두 단어 다 원본 줄 bbox 폭(0~100) 안에 있어야 함(부동소수점 오차 허용).
        assert all(-1e-6 <= t["bbox"][0] < t["bbox"][2] <= 100 + 1e-6 for t in captured["tokens"])
        # 왼→오 순서 유지(hello가 world보다 왼쪽).
        assert captured["tokens"][0]["bbox"][0] < captured["tokens"][1]["bbox"][0]


class TestTableFormerToMarkdown:
    def test_empty_structure_returns_empty_string(self):
        assert TableFormer.to_markdown({"num_rows": 0, "num_cols": 0, "cells": []}) == ""

    def test_renders_grid_with_header_separator(self):
        structure = {
            "num_rows": 2,
            "num_cols": 2,
            "cells": [
                {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "column_header": True, "text_cell_bboxes": [{"token": "h1"}]},
                {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "column_header": True, "text_cell_bboxes": [{"token": "h2"}]},
                {"start_row_offset_idx": 1, "start_col_offset_idx": 0, "text_cell_bboxes": [{"token": "v1"}]},
                {"start_row_offset_idx": 1, "start_col_offset_idx": 1, "text_cell_bboxes": [{"token": "v2"}]},
            ],
        }
        assert TableFormer.to_markdown(structure) == "| h1 | h2 |\n| --- | --- |\n| v1 | v2 |"

    def test_multiple_tokens_in_one_cell_join_in_reading_order(self):
        structure = {
            "num_rows": 1,
            "num_cols": 1,
            "cells": [
                {
                    "start_row_offset_idx": 0,
                    "start_col_offset_idx": 0,
                    "text_cell_bboxes": [{"t": 0, "l": 10, "token": "world"}, {"t": 0, "l": 0, "token": "hello"}],
                }
            ],
        }
        assert TableFormer.to_markdown(structure) == "| hello world |"


class TestTableFormerToHtml:
    def test_empty_structure_returns_empty_string(self):
        assert TableFormer.to_html({"num_rows": 0, "num_cols": 0, "cells": []}) == ""

    def test_renders_header_row_as_th(self):
        structure = {
            "num_rows": 2,
            "num_cols": 2,
            "cells": [
                {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "column_header": True, "text_cell_bboxes": [{"token": "h1"}]},
                {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "column_header": True, "text_cell_bboxes": [{"token": "h2"}]},
                {"start_row_offset_idx": 1, "start_col_offset_idx": 0, "text_cell_bboxes": [{"token": "v1"}]},
                {"start_row_offset_idx": 1, "start_col_offset_idx": 1, "text_cell_bboxes": [{"token": "v2"}]},
            ],
        }
        assert TableFormer.to_html(structure) == (
            "<table><tr><th>h1</th><th>h2</th></tr><tr><td>v1</td><td>v2</td></tr></table>"
        )

    def test_merged_cell_preserves_rowspan_and_colspan(self):
        """markdown과 달리, 병합 셀의 rowspan/colspan을 실제로 보존하고 덮이는 칸은 <td>를 안 낸다."""
        structure = {
            "num_rows": 2,
            "num_cols": 3,
            "cells": [
                # (0,0)이 2행 1열 병합 -> (1,0)은 덮여서 <td>가 안 나와야 함
                {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "row_span": 2, "text_cell_bboxes": [{"token": "merged"}]},
                # (0,1)이 1행 2열 병합 -> (0,2)는 덮여서 <td>가 안 나와야 함
                {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "col_span": 2, "text_cell_bboxes": [{"token": "wide"}]},
                {"start_row_offset_idx": 1, "start_col_offset_idx": 1, "text_cell_bboxes": [{"token": "b1"}]},
                {"start_row_offset_idx": 1, "start_col_offset_idx": 2, "text_cell_bboxes": [{"token": "b2"}]},
            ],
        }
        assert TableFormer.to_html(structure) == (
            '<table><tr><td rowspan="2">merged</td><td colspan="2">wide</td></tr>'
            "<tr><td>b1</td><td>b2</td></tr></table>"
        )

    def test_escapes_html_special_characters(self):
        structure = {
            "num_rows": 1,
            "num_cols": 1,
            "cells": [
                {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text_cell_bboxes": [{"token": "<a> & \"b\""}]},
            ],
        }
        assert TableFormer.to_html(structure) == "<table><tr><td>&lt;a&gt; &amp; &quot;b&quot;</td></tr></table>"


class TestLineToWordTokens:
    def test_empty_line_returns_no_tokens(self):
        tokens, next_id = DetrLayout._line_to_word_tokens("   ", (0, 0, 100, 10), next_id=0)
        assert tokens == []
        assert next_id == 0

    def test_splits_on_whitespace_left_to_right(self):
        tokens, next_id = DetrLayout._line_to_word_tokens("hello world", (0, 0, 100, 10), next_id=0)
        assert [t["text"] for t in tokens] == ["hello", "world"]
        assert next_id == 2
        # "hello"(5자)가 "world"(5자)보다 앞서고, 둘 다 줄 bbox(0~100) 안에 있어야 함.
        hello, world = tokens
        assert hello["bbox"][0] == 0
        assert hello["bbox"][2] < world["bbox"][0]
        assert world["bbox"][2] == pytest.approx(100)
        # y좌표는 줄 bbox의 y0/y1을 그대로 물려받는다.
        assert hello["bbox"][1] == 0 and hello["bbox"][3] == 10

    def test_longer_word_gets_proportionally_wider_bbox(self):
        tokens, _ = DetrLayout._line_to_word_tokens("a bb", (0, 0, 30, 10), next_id=0)
        a_width = tokens[0]["bbox"][2] - tokens[0]["bbox"][0]
        bb_width = tokens[1]["bbox"][2] - tokens[1]["bbox"][0]
        assert bb_width == pytest.approx(2 * a_width)

    def test_next_id_continues_across_calls(self):
        tokens1, next_id = DetrLayout._line_to_word_tokens("a b", (0, 0, 10, 10), next_id=5)
        assert [t["id"] for t in tokens1] == [5, 6]
        tokens2, next_id = DetrLayout._line_to_word_tokens("c", (0, 0, 10, 10), next_id=next_id)
        assert [t["id"] for t in tokens2] == [7]
        assert next_id == 8
