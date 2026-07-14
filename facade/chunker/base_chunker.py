"""청킹 전략이 공통으로 상속하는 베이스 클래스.

smart_chunker/hierarchical_chunker/hybrid_chunker가 저마다 따로 구현하던
"heading+본문 합치기"와 "문자 수 기준 슬라이딩 윈도우 분할"을 여기로 모았다.
서브클래스는 :meth:`__call__` 만 구현하면 되고, ``chunk_size``/``chunk_overlap``
저장과 :meth:`_render`/:meth:`_split_text` 는 필요할 때 그대로 쓰면 된다.
"""

from abc import ABC, abstractmethod
from typing import List, Optional


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
    def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """text를 chunk_size 문자 단위로, chunk_overlap만큼 겹치게 슬라이딩 윈도우 분할한다.

        Args:
            text: 분할할 텍스트.
            chunk_size: 조각 하나의 최대 문자 수.
            chunk_overlap: 인접 조각끼리 겹치는 문자 수.

        Returns:
            분할된 텍스트 조각 목록. ``text`` 가 비어 있으면 빈 리스트.
        """
        pieces = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            pieces.append(text[start:end])
            start = end - chunk_overlap if end < len(text) else end
        return pieces

    @abstractmethod
    def __call__(self, items: List[dict]) -> List[dict]:
        """로더가 반환한 ``{text, category, bbox, page}`` 아이템 목록을
        ``{text, i_page, e_page}`` 청크 목록으로 변환한다."""
        raise NotImplementedError
