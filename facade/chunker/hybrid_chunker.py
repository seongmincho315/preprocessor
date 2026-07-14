"""헤딩 단위 병합(merge_peers) + 분할 청커. ``chunker.type: hybrid_chunker`` 로 선택된다."""

from typing import List, Optional, Tuple


class Chunker:
    """docling의 HybridChunker처럼, HierarchicalChunker 결과(아이템당 청크 1개)를
    같은 heading을 공유하는 것끼리 chunk_size 안에서 합치고(merge_peers),
    그래도 넘치는 청크는 겹치게 분할한다. chunk_size가 0/None이면 병합 없이 그대로 반환한다."""

    def __init__(self, chunk_size: int = 0, chunk_overlap: int = 100):
        """
        Args:
            chunk_size: 청크 하나의 최대 문자 수. 0/None이면 병합/분할 없이
                아이템당 청크 하나를 그대로 반환한다.
            chunk_overlap: 분할 시 인접 조각끼리 겹치는 문자 수.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def __call__(self, items: List[dict]) -> List[dict]:
        """아이템을 헤딩 단위로 병합하고, 넘치면 분할해 청크 목록으로 반환한다.

        Args:
            items: 로더가 반환한 ``{text, category, bbox, page}`` 아이템 목록.

        Returns:
            ``{text, i_page, e_page}`` 청크 목록.
        """
        base = self._hierarchical(items)
        if not self.chunk_size:
            return [
                {"text": self._render(heading, text), "i_page": i_page, "e_page": e_page}
                for heading, text, i_page, e_page in base
            ]

        merged = self._merge_peers(base, self.chunk_size)

        chunks = []
        for heading, text, i_page, e_page in merged:
            rendered = self._render(heading, text)
            if len(rendered) <= self.chunk_size:
                chunks.append({"text": rendered, "i_page": i_page, "e_page": e_page})
            else:
                chunks.extend(self._split(heading, text, i_page, e_page, self.chunk_size, self.chunk_overlap))
        return chunks

    @staticmethod
    def _hierarchical(items: List[dict]) -> List[Tuple[Optional[str], str, int, int]]:
        """아이템 하나당 (현재 heading, 텍스트, i_page, e_page) 튜플 하나. 병합/분할 없음.

        Args:
            items: 원본 아이템 목록.

        Returns:
            ``(heading, text, i_page, e_page)`` 튜플 목록.
        """
        result = []
        heading: Optional[str] = None
        for item in items:
            if item.get("category") == "section_header":
                heading = item["text"]
                continue
            if item.get("text"):
                result.append((heading, item["text"], item["page"], item["page"]))
        return result

    @staticmethod
    def _merge_peers(
        chunks: List[Tuple[Optional[str], str, int, int]], chunk_size: int
    ) -> List[Tuple[Optional[str], str, int, int]]:
        """같은 heading을 공유하는 인접 청크를 chunk_size 안에서 합친다(페이지 범위도 함께 병합).

        Args:
            chunks: :meth:`_hierarchical` 이 반환한 튜플 목록.
            chunk_size: 병합 후 텍스트가 넘지 말아야 할 최대 문자 수.

        Returns:
            병합된 ``(heading, text, i_page, e_page)`` 튜플 목록.
        """
        merged: List[Tuple[Optional[str], str, int, int]] = []
        for heading, text, i_page, e_page in chunks:
            if merged and merged[-1][0] == heading and len(merged[-1][1]) + 1 + len(text) <= chunk_size:
                prev_heading, prev_text, prev_i_page, prev_e_page = merged[-1]
                merged[-1] = (
                    prev_heading,
                    prev_text + "\n" + text,
                    min(prev_i_page, i_page),
                    max(prev_e_page, e_page),
                )
            else:
                merged.append((heading, text, i_page, e_page))
        return merged

    @staticmethod
    def _render(heading: Optional[str], text: str) -> str:
        """heading과 본문 텍스트를 ``", "`` 로 합친다(heading 없으면 본문만)."""
        return ", ".join(t for t in (heading, text) if t)

    @classmethod
    def _split(
        cls, heading: Optional[str], text: str, i_page: int, e_page: int, chunk_size: int, chunk_overlap: int
    ) -> List[dict]:
        """chunk_size로 쪼갠 조각들도 정확한 글자 단위 페이지 추적 대신 병합 전 페이지
        범위를 그대로 물려받는다(근사치).

        Args:
            heading: 병합된 청크의 heading(없으면 ``None``).
            text: 분할할 본문 텍스트.
            i_page: 분할 전 병합된 청크의 시작 페이지.
            e_page: 분할 전 병합된 청크의 끝 페이지.
            chunk_size: 조각 하나의 최대 문자 수.
            chunk_overlap: 인접 조각끼리 겹치는 문자 수.

        Returns:
            ``{text, i_page, e_page}`` 청크 목록. 모든 조각이 같은 페이지
            범위(``i_page``, ``e_page``)를 공유한다.
        """
        pieces = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            pieces.append(text[start:end])
            start = end - chunk_overlap if end < len(text) else end
        return [{"text": cls._render(heading, piece), "i_page": i_page, "e_page": e_page} for piece in pieces]
