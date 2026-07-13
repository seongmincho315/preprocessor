# rule 기반 레이아웃 분석 모델
from typing import List, Tuple

# 본문 대비 이 배수 이상 크면 section_header로 취급하는 휴리스틱
HEADER_FONT_SIZE_RATIO = 1.2


class Layout:
    def __init__(self, config: dict = None):
        self.config = config or {}

    def __call__(self, lines: List[Tuple[str, Tuple[float, float, float, float], float]]) -> List[str]:
        """페이지의 (text, bbox, font_size) 줄 목록을 받아 줄마다 category를 반환한다."""
        body_size = self._most_common_font_size(lines)
        return [self._classify(font_size, body_size) for _, _, font_size in lines]

    @staticmethod
    def _classify(font_size: float, body_size: float) -> str:
        if body_size and font_size >= body_size * HEADER_FONT_SIZE_RATIO:
            return "section_header"
        return "text"

    @staticmethod
    def _most_common_font_size(lines) -> float:
        sizes = [size for _, _, size in lines if size]
        if not sizes:
            return 0
        return max(set(sizes), key=sizes.count)
