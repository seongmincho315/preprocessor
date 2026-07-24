"""확장자별 로더가 공통으로 상속하는 베이스 클래스.

레이아웃 분석(카테고리 부여)과 OCR 전략을 config로 선택해 구성하고, 페이지 단위
텍스트 추출(``_extract_pages``, 서브클래스가 구현)을 조합해 최종 아이템 목록을
만드는 절차를 정의한다.
"""

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional, Tuple

from util.header_footer import strip_repeated_headers_footers
from util.paragraph_merge import merge_split_paragraphs
from util.reading_order import reorder_by_category
from util.rule_layout import Layout
from util.util import has_glyph_corruption, normalize_typography

OCR_MODES = ("auto", "force", "disable")
"""ocr.mode로 쓸 수 있는 값. auto: 텍스트가 없거나 글리프가 깨진 페이지만 OCR,
force: 모든 페이지를 무조건 OCR, disable: OCR을 아예 쓰지 않음."""


class BaseLoader(ABC):
    """파일을 읽어 ``{text, category, bbox, page}`` 아이템 목록으로 변환하는 로더의 베이스 클래스.

    서브클래스는 :meth:`_extract_pages` 만 구현하면 되고, 레이아웃 분석/OCR 적용/
    아이템 조립은 이 클래스가 공통으로 처리한다.

    Attributes:
        layout_config (dict): ``layout.type``, ``image_dpi`` 등 레이아웃 전략 설정.
        ocr_config (dict): ``ocr.type``, ``ocr.mode`` 등 OCR 전략 설정.
        image_dpi (int): 페이지를 이미지로 렌더링할 때 쓰는 DPI.
        ocr_mode (str): :data:`OCR_MODES` 중 하나. 잘못된 값이면 ``"auto"`` 로 대체.
        layout: :meth:`get_layout` 으로 생성된 레이아웃 분석 전략 인스턴스.
        ocr: :meth:`get_ocr` 로 생성된 OCR 전략 인스턴스(``None`` 이면 OCR 미사용).
    """

    def __init__(self, layout_config: dict = None, ocr_config: dict = None):
        """레이아웃/OCR 설정을 받아 전략 인스턴스를 구성한다.

        Args:
            layout_config: 레이아웃 전략 설정 dict (예: ``resource/detr.yaml`` 내용).
            ocr_config: OCR 전략 설정 dict (예: ``resource/paddle.yaml`` 내용).
        """
        super().__init__()
        self.layout_config = layout_config or {}
        self.ocr_config = ocr_config or {}
        self.image_dpi = self.layout_config.get("image_dpi", 150)
        ocr_mode = self.ocr_config.get("mode", "auto")
        self.ocr_mode = ocr_mode if ocr_mode in OCR_MODES else "auto"
        self.layout = self.get_layout()
        self.ocr = self.get_ocr()

    @property
    def needs_image(self) -> bool:
        """레이아웃 분석이나 OCR 중 하나라도 페이지 이미지가 필요하면 ``True``."""
        return getattr(self.layout, "NEEDS_IMAGE", False) or self.ocr is not None

    def __call__(self, file_path: str, *args, **kwds) -> List[dict]:
        """파일 하나를 읽어 아이템 목록으로 반환한다.

        페이지마다 텍스트 줄을 추출하고, :meth:`_needs_ocr` 판단에 따라 OCR로
        대체한 뒤, 레이아웃 전략을 호출해 카테고리를 매긴다. 다단(2단/3단)
        레이아웃이면, 카테고리 중 본문 흐름(text/section_header 등)에 속하는
        줄만 실제로 읽는 순서로 재정렬한다(:func:`~util.reading_order.reorder_by_category`).
        formula/table/page_header 등은 재정렬하지 않고 원래 순서를 그대로 두는데,
        PyMuPDF가 수식 한 줄을 여러 조각으로 쪼개서 주는 경우가 많아 카테고리 없이
        기하학적으로만 재정렬하면 오히려 순서가 깨지기 때문이다. 각 줄의 텍스트는
        타이포그래피 정규화를 거친다(:func:`~util.util.normalize_typography`).
        마지막으로 여러 페이지에 반복되는 머리말/꼬리말을 제거하고
        (:func:`~util.header_footer.strip_repeated_headers_footers`), 페이지 경계든
        같은 페이지 안이든 줄바꿈으로 잘린 문단을 이어붙인다
        (:func:`~util.paragraph_merge.merge_split_paragraphs`).
        레이아웃 전략은 두 계약 중 하나를 따른다:

        - 기본(``rule``/``detr``/``dots_mocr`` 등): ``lines`` 와 같은 길이의 카테고리
          문자열 목록을 반환하고, 이 메서드가 ``lines`` 와 zip해 아이템을 조립한다.
        - ``PRODUCES_ITEMS = True`` 인 전략(예: ``dots_mocr_all``/``dots_mocr_grounding``/
          ``dots_mocr_auto``): ``{"text","category","bbox"}`` 아이템 목록을 직접 반환하고,
          이 메서드는 그걸 그대로 쓴다(자체적으로 텍스트를 추출/오버라이드하는 전략이라
          ``lines`` 와의 위치 매칭이 성립하지 않기 때문).

        ``NEEDS_WORDS = True`` 인 전략(``DetrLayout`` - table_structure 켜졌을 때)에는
        ``_extract_pages`` 가 낸 원본 PDF 단어 단위 ``words`` 도 같이 넘긴다(tableformer의
        cell 매칭 정확도용 - 줄 단위보다 훨씬 정밀하다). 이 페이지가 OCR로 대체됐으면
        (PDF 텍스트 레이어 대신 스캔 이미지에서 다시 읽은 것이라) 원본 단어 bbox가 더 이상
        유효하지 않으므로 ``words`` 를 넘기지 않는다.

        Args:
            file_path: 읽을 파일 경로.

        Returns:
            ``{text, category, bbox, page}`` 형태의 아이템 목록.
        """
        items = []
        for page_no, (lines, image, words) in enumerate(self._extract_pages(file_path), start=1):
            if image is not None and self.ocr is not None and self._needs_ocr(lines):
                lines = self.ocr(image, dpi=self.image_dpi)
                words = None  # PDF 텍스트 레이어 대신 OCR 결과를 쓰므로 원본 단어 bbox는 더 이상 유효하지 않다.
            if words is not None and getattr(self.layout, "NEEDS_WORDS", False):
                result = self.layout(lines, image=image, words=words)
            else:
                result = self.layout(lines, image=image)
            if getattr(self.layout, "PRODUCES_ITEMS", False):
                for item in result:
                    items.append({**item, "text": normalize_typography(item.get("text", "")), "page": page_no})
            else:
                lines, result = reorder_by_category(lines, result)
                for (text, bbox, font_size), category in zip(lines, result):
                    items.append(
                        {
                            "text": normalize_typography(text),
                            "category": category,
                            "bbox": {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]},
                            "page": page_no,
                        }
                    )
        items = strip_repeated_headers_footers(items)
        return merge_split_paragraphs(items)

    def _needs_ocr(self, lines: List[Tuple[str, Tuple[float, float, float, float], float]]) -> bool:
        """ocr.mode(auto|force|disable)에 따라 이 페이지를 OCR로 다시 뽑아야 하는지 판단한다.
        auto: 텍스트 레이어가 없거나(스캔 페이지), 있어도 글리프가 깨져 있으면 OCR로 대체."""
        if self.ocr_mode == "disable":
            return False
        if self.ocr_mode == "force":
            return True
        return not lines or has_glyph_corruption(lines)

    def get_layout(self):
        layout_type = self.layout_config.get("type", "rule")
        if layout_type == "detr":
            from util.detr_layout import DetrLayout

            return DetrLayout(self.layout_config)
        if layout_type == "dots_mocr":
            from util.dots_mocr_layout import DotsMocrLayout

            return DotsMocrLayout(self.layout_config)
        if layout_type == "dots_mocr_all":
            from util.dots_mocr_all_layout import DotsMocrAllLayout

            return DotsMocrAllLayout(self.layout_config)
        if layout_type == "dots_mocr_grounding":
            from util.dots_mocr_grounding_layout import DotsMocrGroundingLayout

            return DotsMocrGroundingLayout(self.layout_config)
        if layout_type == "dots_mocr_auto":
            from util.dots_mocr_auto_layout import DotsMocrAutoLayout

            return DotsMocrAutoLayout(self.layout_config)
        return Layout(self.layout_config)

    def get_ocr(self):
        if self.ocr_mode == "disable":
            return None
        ocr_type = self.ocr_config.get("type")
        if ocr_type == "paddle":
            from util.paddle_ocr import PaddleOcr

            return PaddleOcr(self.ocr_config)
        return None

    @abstractmethod
    def _extract_pages(self, file_path: str) -> Iterable[
        Tuple[
            List[Tuple[str, Tuple[float, float, float, float], float]],
            Optional[bytes],
            Optional[List[Tuple[str, Tuple[float, float, float, float]]]],
        ]
    ]:
        """페이지 단위로 ((text, bbox, font_size) 줄 목록, 페이지 이미지 PNG bytes|None,
        (text, bbox) 단어 목록|None)을 순서대로 반환한다. 세 번째 요소(``words``)는 원본 PDF의
        실제 단어 단위 bbox로, 이를 낼 수 있는 로더(``loader.pdf.pymupdf`` - hwp/hwpx/pptx/ppt
        등 PDF로 변환 후 이 로더에 위임하는 컨버터도 상속으로 자동 포함)만 채우고, 나머지는
        ``None``."""
        raise NotImplementedError
