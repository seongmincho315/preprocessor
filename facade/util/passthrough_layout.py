"""``_extract_pages`` 자체가 이미 category를 정해 넣는 로더(docx/csv/xlsx/md/txt)를
위한 layout 전략. table/list_item/code처럼 font-ratio 휴리스틱(:mod:`util.rule_layout`)
이 표현할 수 없는 카테고리를, 세 번째 튜플 자리에 float font_size 대신 category
문자열을 직접 채워 넣는 방식으로 우회한다.
"""

from typing import List, Tuple


class PassthroughLayout:
    """세 번째 튜플 값을 이미 결정된 category로 보고 그대로 반환한다."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: 이 전략에서는 쓰이지 않지만, 다른 레이아웃 전략과 생성자
                시그니처를 맞추기 위해 받는다.
        """
        self.config = config or {}

    def __call__(self, lines: List[Tuple[str, Tuple[float, float, float, float], str]], image: bytes = None) -> List[str]:
        """``lines`` 의 세 번째 자리(category 문자열)를 그대로 뽑아 반환한다.

        Args:
            lines: ``(text, bbox, category)`` 튜플 목록.
            image: 이 전략에서는 쓰이지 않는다.

        Returns:
            ``lines`` 와 같은 길이의 category 문자열 목록.
        """
        return [category for _, _, category in lines]
