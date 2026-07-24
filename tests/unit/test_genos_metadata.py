import json
import re

import pytest

from metadata.genos import GenosMetadata

pytestmark = pytest.mark.unit

REG_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$")

CHUNKS = [
    {"text": "hello world", "i_page": 1, "e_page": 1},
    {"text": "second chunk page1", "i_page": 1, "e_page": 1},
    {"text": "third chunk page2\nline2", "i_page": 2, "e_page": 3},
]

EXPECTED_KEYS = {
    "text", "n_chars", "n_words", "n_lines", "i_page", "e_page", "n_page",
    "i_chunk_on_page", "n_chunk_of_page", "i_chunk_on_doc", "n_chunk_of_doc", "reg_date",
    "chunk_bboxes",
}


def test_empty_chunks_returns_empty_list():
    assert GenosMetadata()([]) == []


def test_field_names_match_genos_weaviate_schema():
    meta = GenosMetadata()(CHUNKS)
    assert set(meta[0].keys()) == EXPECTED_KEYS


def test_doc_level_fields():
    meta = GenosMetadata()(CHUNKS)
    assert all(entry["n_chunk_of_doc"] == 3 for entry in meta)
    assert all(entry["n_page"] == 3 for entry in meta)  # max(e_page) across chunks
    assert [entry["i_chunk_on_doc"] for entry in meta] == [0, 1, 2]


def test_per_page_chunk_counters():
    meta = GenosMetadata()(CHUNKS)
    # 청크 0,1은 같은 페이지(1)에서 옴 -> n_chunk_of_page=2, i_chunk_on_page 0,1로 증가
    assert meta[0]["i_chunk_on_page"] == 0 and meta[0]["n_chunk_of_page"] == 2
    assert meta[1]["i_chunk_on_page"] == 1 and meta[1]["n_chunk_of_page"] == 2
    # 청크 2는 혼자 페이지 2에서 시작 -> n_chunk_of_page=1
    assert meta[2]["i_chunk_on_page"] == 0 and meta[2]["n_chunk_of_page"] == 1


def test_text_stats_computed_from_chunk_text():
    meta = GenosMetadata()(CHUNKS)
    assert meta[2]["n_chars"] == len(CHUNKS[2]["text"])
    assert meta[2]["n_words"] == 4
    assert meta[2]["n_lines"] == 2


def test_reg_date_matches_genos_iso8601_format():
    meta = GenosMetadata()(CHUNKS)
    assert REG_DATE_RE.match(meta[0]["reg_date"])


def test_chunk_bboxes_none_without_file_path():
    chunks = [{**CHUNKS[0], "bboxes": [{"page": 1, "bbox": {"x0": 10, "y0": 10, "x1": 50, "y1": 20}, "category": "text"}]}]
    meta = GenosMetadata()(chunks)
    assert meta[0]["chunk_bboxes"] is None


def test_build_chunk_bboxes_normalizes_against_page_size():
    bboxes = [{"page": 1, "bbox": {"x0": 61.2, "y0": 79.2, "x1": 550.8, "y1": 158.4}, "category": "text"}]
    page_sizes = {1: (612.0, 792.0)}
    result = json.loads(GenosMetadata._build_chunk_bboxes(bboxes, page_sizes))
    assert len(result) == 1
    assert result[0]["page"] == 1
    assert result[0]["type"] == "text"
    assert result[0]["bbox"]["coord_origin"] == "TOPLEFT"
    assert result[0]["bbox"]["l"] == pytest.approx(0.1)
    assert result[0]["bbox"]["t"] == pytest.approx(0.1)
    assert result[0]["bbox"]["r"] == pytest.approx(0.9)
    assert result[0]["bbox"]["b"] == pytest.approx(0.2)


def test_build_chunk_bboxes_skips_entries_missing_page_size():
    bboxes = [{"page": 1, "bbox": {"x0": 0, "y0": 0, "x1": 10, "y1": 10}, "category": "text"}]
    assert GenosMetadata._build_chunk_bboxes(bboxes, {}) is None


def test_build_chunk_bboxes_none_when_chunk_has_no_bboxes():
    assert GenosMetadata._build_chunk_bboxes(None, {1: (612.0, 792.0)}) is None
    assert GenosMetadata._build_chunk_bboxes([], {1: (612.0, 792.0)}) is None
