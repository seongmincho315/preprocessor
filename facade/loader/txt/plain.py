"""빈 줄 기준 문단 분리만 하는 평문 텍스트 로더. ``ext.txt`` 가 ``plain`` 일 때 쓰인다.

구조가 전혀 없는 포맷이라 모든 문단이 category="text"다 - 그래도 PassthroughLayout을
그대로 재사용해, 이 프로젝트의 모든 구조 네이티브 로더가 "category는 _extract_pages가
직접 정한다"는 계약 하나로 통일되게 한다.
"""

import re

from loader.base_loader import BaseLoader
from util.passthrough_layout import PassthroughLayout

DUMMY_BBOX = (0.0, 0.0, 0.0, 0.0)
_BLANK_LINE_RE = re.compile(r"\n\s*\n+")


class Loader(BaseLoader):
    """빈 줄로 구분된 문단마다 하나씩, 전부 category="text"인 아이템으로 담는다."""

    def get_layout(self):
        return PassthroughLayout(self.layout_config)

    def get_ocr(self):
        return None

    def _extract_pages(self, file_path: str):
        """문서 전체를 페이지 1개로 취급해 (줄 목록, None) 쌍 하나만 낸다.

        Args:
            file_path: 읽을 txt 파일 경로.

        Yields:
            ``(lines, None)`` 튜플 하나.
        """
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        paragraphs = _BLANK_LINE_RE.split(content.strip())
        lines = [(p.strip(), DUMMY_BBOX, "text") for p in paragraphs if p.strip()]
        yield lines, None, None
