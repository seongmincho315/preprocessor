"""외부 서빙(detr 등) 없이 폰트 크기만으로 카테고리를 추정하는 rule 기반 레이아웃 전략.
``layout.type: rule``(기본값)일 때 쓰인다. 원격 모델 서버가 없어도 동작하지만,
``section_header``/``text`` 두 카테고리만 구분한다."""

from typing import List, Tuple

# 본문 대비 이 배수 이상 크면 section_header로 취급하는 휴리스틱
HEADER_FONT_SIZE_RATIO = 1.2


class Layout:
    """페이지에서 가장 흔한 폰트 크기를 본문(body) 크기로 보고, 그보다
    :data:`HEADER_FONT_SIZE_RATIO` 배 이상 큰 줄을 ``section_header``\ 로 분류한다."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: 이 전략에서는 쓰이지 않지만, 다른 레이아웃 전략과 생성자
                시그니처를 맞추기 위해 받는다.
        """
        self.config = config or {}

    def __call__(
        self, lines: List[Tuple[str, Tuple[float, float, float, float], float]], image: bytes = None
    ) -> List[str]:
        """페이지의 (text, bbox, font_size) 줄 목록을 받아 줄마다 category를 반환한다.

        Args:
            lines: ``(text, bbox, font_size)`` 튜플 목록.
            image: 이 전략에서는 쓰이지 않는다(``NEEDS_IMAGE``\ 가 없어 항상 ``None``).

        Returns:
            ``lines``\ 와 같은 길이의 카테고리 문자열 목록(``"section_header"`` 또는 ``"text"``).
        """
        body_size = self._most_common_font_size(lines)
        return [self._classify(font_size, body_size) for _, _, font_size in lines]

    @staticmethod
    def _classify(font_size: float, body_size: float) -> str:
        """폰트 크기가 본문 대비 :data:`HEADER_FONT_SIZE_RATIO` 배 이상이면 헤더로 분류한다."""
        if body_size and font_size >= body_size * HEADER_FONT_SIZE_RATIO:
            return "section_header"
        return "text"

    @staticmethod
    def _most_common_font_size(lines) -> float:
        """페이지의 줄들 중 가장 자주 나온 폰트 크기를 본문 크기로 추정한다.

        Args:
            lines: ``(text, bbox, font_size)`` 튜플 목록.

        Returns:
            최빈 폰트 크기. 줄이 없거나 크기 정보가 없으면 ``0``.
        """
        sizes = [size for _, _, size in lines if size]
        if not sizes:
            return 0
        return max(set(sizes), key=sizes.count)
