from typing import List, Optional, Tuple


class Chunker:
    """docling의 HybridChunker처럼, HierarchicalChunker 결과(아이템당 청크 1개)를
    같은 heading을 공유하는 것끼리 chunk_size 안에서 합치고(merge_peers),
    그래도 넘치는 청크는 겹치게 분할한다. chunk_size가 0/None이면 병합 없이 그대로 반환한다."""

    def __init__(self, chunk_size: int = 0, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def __call__(self, items: List[dict]) -> List[str]:
        base = self._hierarchical(items)
        if not self.chunk_size:
            return [self._render(heading, text) for heading, text in base]

        merged = self._merge_peers(base, self.chunk_size)

        chunks = []
        for heading, text in merged:
            rendered = self._render(heading, text)
            if len(rendered) <= self.chunk_size:
                chunks.append(rendered)
            else:
                chunks.extend(self._split(heading, text, self.chunk_size, self.chunk_overlap))
        return chunks

    @staticmethod
    def _hierarchical(items: List[dict]) -> List[Tuple[Optional[str], str]]:
        """아이템 하나당 (현재 heading, 텍스트) 튜플 하나. 병합/분할 없음."""
        result = []
        heading: Optional[str] = None
        for item in items:
            if item.get("category") == "section_header":
                heading = item["text"]
                continue
            if item.get("text"):
                result.append((heading, item["text"]))
        return result

    @staticmethod
    def _merge_peers(chunks: List[Tuple[Optional[str], str]], chunk_size: int) -> List[Tuple[Optional[str], str]]:
        """같은 heading을 공유하는 인접 청크를 chunk_size 안에서 합친다."""
        merged: List[Tuple[Optional[str], str]] = []
        for heading, text in chunks:
            if merged and merged[-1][0] == heading and len(merged[-1][1]) + 1 + len(text) <= chunk_size:
                prev_heading, prev_text = merged[-1]
                merged[-1] = (prev_heading, prev_text + "\n" + text)
            else:
                merged.append((heading, text))
        return merged

    @staticmethod
    def _render(heading: Optional[str], text: str) -> str:
        return ", ".join(t for t in (heading, text) if t)

    @classmethod
    def _split(cls, heading: Optional[str], text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        pieces = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            pieces.append(text[start:end])
            start = end - chunk_overlap if end < len(text) else end
        return [cls._render(heading, piece) for piece in pieces]
