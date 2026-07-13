from typing import List, Optional


class Chunker:
    """docling의 HierarchicalChunker처럼 병합/분할 없이 아이템 하나당 청크 하나를 만든다.
    직전 section_header를 heading으로 붙여 문맥만 유지한다."""

    def __init__(self, chunk_size: int = 0, chunk_overlap: int = 100):
        # 병합/분할을 하지 않아 쓰이진 않지만, 다른 Chunker와 생성자 시그니처를 맞춰둔다.
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def __call__(self, items: List[dict]) -> List[str]:
        chunks = []
        heading: Optional[str] = None
        for item in items:
            if item.get("category") == "section_header":
                heading = item["text"]
                continue
            text = item.get("text")
            if not text:
                continue
            chunks.append(", ".join(t for t in (heading, text) if t))
        return chunks
