"""청킹 전략이 공통으로 상속하는 베이스 클래스.

smart_chunker/hierarchical_chunker/hybrid_chunker가 저마다 따로 구현하던
"heading+본문 합치기"와 "문자 수 기준 슬라이딩 윈도우 분할"을 여기로 모았다.
서브클래스는 :meth:`__call__` 만 구현하면 되고, ``chunk_size``/``chunk_overlap``
저장과 :meth:`_render`/:meth:`_split_text` 는 필요할 때 그대로 쓰면 된다.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class BaseChunker(ABC):
    """아이템 목록을 청크 목록으로 묶는 청킹 전략의 베이스 클래스.

    Attributes:
        chunk_size (int): 청크 하나의 최대 문자 수. 0/None이면 서브클래스가
            병합/분할을 하지 않는다는 의미로 쓴다.
        chunk_overlap (int): 분할 시 인접 조각끼리 겹치는 문자 수.
    """

    def __init__(self, chunk_size: int = 0, chunk_overlap: int = 100):
        """
        Args:
            chunk_size: 청크 하나의 최대 문자 수.
            chunk_overlap: 분할 시 인접 조각끼리 겹치는 문자 수.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def _render(heading: Optional[str], text: str) -> str:
        """heading과 본문 텍스트를 ``", "`` 로 합친다(heading 없으면 본문만)."""
        return ", ".join(t for t in (heading, text) if t)

    @staticmethod
    def _split_ranges(length: int, chunk_size: int, chunk_overlap: int) -> List[Tuple[int, int]]:
        """``[0, length)`` 를 chunk_size 문자 단위로, chunk_overlap만큼 겹치게 슬라이딩 윈도우 분할한
        ``(start, end)`` 범위 목록을 반환한다. ``_split_text`` 가 문자열 대신 범위가 필요할 때
        (예: 원본 아이템의 bbox를 조각별로 다시 스코프해야 할 때) 쓴다."""
        ranges = []
        start = 0
        while start < length:
            end = start + chunk_size
            ranges.append((start, min(end, length)))
            start = end - chunk_overlap if end < length else end
        return ranges

    @classmethod
    def _split_text(cls, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """text를 chunk_size 문자 단위로, chunk_overlap만큼 겹치게 슬라이딩 윈도우 분할한다.

        Args:
            text: 분할할 텍스트.
            chunk_size: 조각 하나의 최대 문자 수.
            chunk_overlap: 인접 조각끼리 겹치는 문자 수.

        Returns:
            분할된 텍스트 조각 목록. ``text`` 가 비어 있으면 빈 리스트.
        """
        return [text[start:end] for start, end in cls._split_ranges(len(text), chunk_size, chunk_overlap)]

    @abstractmethod
    def __call__(self, items: List[dict]) -> List[dict]:
        """로더가 반환한 ``{text, category, bbox, page}`` 아이템 목록을
        ``{text, i_page, e_page}`` 청크 목록으로 변환한다. ``bboxes``
        (구성 아이템의 ``{page, bbox}`` 목록)는 지원하는 청커만 덧붙인다."""
        raise NotImplementedError
