import pytest

from chunker.hierarchical_chunker import Chunker as HierarchicalChunker
from chunker.hybrid_chunker import Chunker as HybridChunker
from chunker.smart_chunker import Chunker as SmartChunker

pytestmark = pytest.mark.unit

ITEMS = [
    {"text": "Intro", "category": "section_header", "page": 1},
    {"text": "para one on page 1", "category": "text", "page": 1},
    {"text": "para two on page 2", "category": "text", "page": 2},
    {"text": "Chapter 2", "category": "section_header", "page": 3},
    {"text": "para three on page 3", "category": "text", "page": 3},
]


class TestHierarchicalChunker:
    def test_one_chunk_per_item_with_page_carried_through(self):
        chunks = HierarchicalChunker()(ITEMS)

        assert chunks == [
            {"text": "Intro, para one on page 1", "i_page": 1, "e_page": 1},
            {"text": "Intro, para two on page 2", "i_page": 2, "e_page": 2},
            {"text": "Chapter 2, para three on page 3", "i_page": 3, "e_page": 3},
        ]


class TestSmartChunker:
    def test_whole_section_spans_heading_and_body_pages(self):
        chunks = SmartChunker(chunk_size=0)(ITEMS)

        assert len(chunks) == 2
        assert chunks[0]["i_page"] == 1 and chunks[0]["e_page"] == 2
        assert chunks[1]["i_page"] == 3 and chunks[1]["e_page"] == 3

    def test_split_pieces_inherit_section_page_range(self):
        chunks = SmartChunker(chunk_size=10, chunk_overlap=2)(ITEMS)

        assert len(chunks) > 2
        section1 = [c for c in chunks if c["e_page"] == 2]
        section2 = [c for c in chunks if c["i_page"] == 3]
        assert section1 and all(c["i_page"] == 1 for c in section1)
        assert section2 and all(c["e_page"] == 3 for c in section2)

    def test_bboxes_carry_category(self):
        items = [
            {"text": "Intro", "category": "section_header", "page": 1, "bbox": {"x0": 0, "y0": 0, "x1": 10, "y1": 10}},
            {"text": "body text", "category": "text", "page": 1, "bbox": {"x0": 0, "y0": 20, "x1": 10, "y1": 30}},
        ]
        chunks = SmartChunker(chunk_size=0)(items)

        assert len(chunks) == 1
        categories = {b["category"] for b in chunks[0]["bboxes"]}
        assert categories == {"section_header", "text"}

    def test_split_pieces_only_carry_bboxes_of_items_actually_in_that_piece(self):
        # 섹션을 여러 조각으로 쪼갤 때, 각 조각은 자기 텍스트 범위에 들어있는
        # 아이템의 bbox만 가져야 한다(전체 섹션 bbox를 통째로 물려받으면 안 됨).
        items = [
            {"text": "Heading", "category": "section_header", "page": 1, "bbox": {"x0": 0, "y0": 0, "x1": 5, "y1": 5}},
            {"text": "aaaaaaaaaa", "category": "text", "page": 1, "bbox": {"x0": 0, "y0": 10, "x1": 5, "y1": 15}},
            {"text": "bbbbbbbbbb", "category": "text", "page": 1, "bbox": {"x0": 0, "y0": 20, "x1": 5, "y1": 25}},
        ]
        chunks = SmartChunker(chunk_size=10, chunk_overlap=0)(items)

        assert len(chunks) > 1
        first_body_bboxes = [b for b in chunks[0]["bboxes"] if b["category"] == "text"]
        last_body_bboxes = [b for b in chunks[-1]["bboxes"] if b["category"] == "text"]
        # 첫 조각은 "a" 줄의 bbox만, 마지막 조각은 "b" 줄의 bbox만 가져야지, 둘 다 갖고
        # 있으면(=섹션 전체를 물려받으면) 회귀다.
        assert first_body_bboxes != last_body_bboxes

    def test_heading_only_section_is_not_dropped(self):
        items = [{"text": "Lone heading", "category": "section_header", "page": 1}]
        chunks = SmartChunker(chunk_size=10, chunk_overlap=2)(items)

        assert len(chunks) == 1
        assert chunks[0]["text"] == "Lone heading"


class TestHybridChunker:
    def test_merge_peers_merges_page_ranges(self):
        chunks = HybridChunker(chunk_size=1000, chunk_overlap=2)(ITEMS)

        intro_chunks = [c for c in chunks if c["text"].startswith("Intro")]
        assert len(intro_chunks) == 1
        assert intro_chunks[0]["i_page"] == 1
        assert intro_chunks[0]["e_page"] == 2

        chapter_chunks = [c for c in chunks if c["text"].startswith("Chapter 2")]
        assert len(chapter_chunks) == 1
        assert chapter_chunks[0]["i_page"] == 3
        assert chapter_chunks[0]["e_page"] == 3

    def test_no_merge_without_chunk_size(self):
        chunks = HybridChunker(chunk_size=0)(ITEMS)

        assert len(chunks) == 3  # 병합 없이 아이템당 하나(heading 제외)
