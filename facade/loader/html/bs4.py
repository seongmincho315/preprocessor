"""BeautifulSoup4 기반 HTML 파서. ``ext.html`` 이 ``bs4`` 일 때 쓰인다.

HTML은 페이지/이미지 개념이 없는 텍스트 네이티브 포맷이라, detr/dots_mocr 같은
이미지 기반 레이아웃 전략이나 OCR이 애초에 적용될 수 없다. 그래서
``layout``/``ocr`` 설정과 무관하게 레이아웃은 항상 폰트 크기 휴리스틱
(:class:`util.rule_layout.Layout`)으로, OCR은 항상 미사용으로 고정한다.
"""

from typing import Iterable, List, Optional, Tuple

from bs4 import BeautifulSoup

from loader.base_loader import BaseLoader
from util.rule_layout import Layout

BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "blockquote", "pre")
"""줄 단위로 뽑아낼 block-level 태그. script/style 등은 포함하지 않는다."""

HEADING_FONT_SIZES = {"h1": 24.0, "h2": 20.0, "h3": 18.0, "h4": 16.0, "h5": 14.0, "h6": 13.0}
"""헤딩 태그별로 부여하는 가상 폰트 크기. rule_layout의 '본문 대비 배수' 휴리스틱이
h1~h6을 본문보다 크게 인식하도록, 실제 CSS와 무관하게 이 값을 그대로 쓴다."""

BODY_FONT_SIZE = 12.0
"""h1~h6이 아닌 태그(p, li, td 등)에 부여하는 가상 폰트 크기."""


class Loader(BaseLoader):
    """HTML을 block 태그 단위로 줄을 뽑아, 문서 전체를 페이지 1개로 취급한다.

    태그에 좌표가 없으므로 bbox는 쓰이지 않는 더미 값(``(0, 0, 0, 0)``)을 채우고,
    태그 종류(h1~h6 vs 나머지)로 :data:`HEADING_FONT_SIZES`/:data:`BODY_FONT_SIZE`
    를 매겨 rule 레이아웃이 ``section_header``/``text`` 를 구분하게 한다.
    """

    def get_layout(self):
        return Layout(self.layout_config)

    def get_ocr(self):
        return None

    def _extract_pages(
        self, file_path: str
    ) -> Iterable[Tuple[List[Tuple[str, Tuple[float, float, float, float], float]], Optional[bytes]]]:
        """HTML 파일 전체를 페이지 1개로 취급해 (줄 목록, None) 쌍 하나만 낸다.

        Args:
            file_path: 읽을 HTML 파일 경로.

        Yields:
            ``(lines, None)`` 튜플 하나. ``lines`` 는 :meth:`_extract_lines` 의 결과.
        """
        with open(file_path, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
        yield self._extract_lines(soup), None, None

    @staticmethod
    def _extract_lines(soup: BeautifulSoup) -> List[Tuple[str, Tuple[float, float, float, float], float]]:
        """문서 순서대로 block 태그를 훑어 (text, bbox, font_size) 목록으로 반환한다.

        Args:
            soup: 파싱된 HTML 문서.

        Returns:
            ``(text, (0, 0, 0, 0), font_size)`` 튜플 목록. 빈 텍스트인 태그는 건너뛴다.
        """
        lines = []
        for tag in soup.find_all(BLOCK_TAGS):
            text = tag.get_text(strip=True)
            if not text:
                continue
            font_size = HEADING_FONT_SIZES.get(tag.name, BODY_FONT_SIZE)
            lines.append((text, (0.0, 0.0, 0.0, 0.0), font_size))
        return lines
