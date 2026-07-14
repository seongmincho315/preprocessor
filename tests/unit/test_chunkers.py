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
