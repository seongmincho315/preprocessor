"""아이템 하나당 청크 하나(병합/분할 없음)인 청커. ``chunker.type: hierarchical_chunker``\ 로 선택된다."""

from typing import List, Optional


class Chunker:
    """docling의 HierarchicalChunker처럼 병합/분할 없이 아이템 하나당 청크 하나를 만든다.
    직전 section_header를 heading으로 붙여 문맥만 유지한다."""

    def __init__(self, chunk_size: int = 0, chunk_overlap: int = 100):
        """
        Args:
            chunk_size: 병합/분할을 하지 않아 실제로는 쓰이지 않는다. 다른
                ``Chunker`` 구현체와 생성자 시그니처를 맞추기 위해서만 받는다.
            chunk_overlap: ``chunk_size``\ 와 마찬가지로 쓰이지 않는다.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def __call__(self, items: List[dict]) -> List[dict]:
        """section_header가 아닌 아이템마다 청크 하나씩 만든다.

        Args:
            items: 로더가 반환한 ``{text, category, bbox, page}`` 아이템 목록.

        Returns:
            ``{text, i_page, e_page}`` 청크 목록. 병합이 없으므로 ``i_page ==
            e_page ==`` 원본 아이템의 페이지다.
        """
        chunks = []
        heading: Optional[str] = None
        for item in items:
            if item.get("category") == "section_header":
                heading = item["text"]
                continue
            text = item.get("text")
            if not text:
                continue
            chunks.append(
                {
                    "text": ", ".join(t for t in (heading, text) if t),
                    "i_page": item["page"],
                    "e_page": item["page"],
                }
            )
        return chunks
