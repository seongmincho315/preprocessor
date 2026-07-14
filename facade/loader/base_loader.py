"""확장자별 로더가 공통으로 상속하는 베이스 클래스.

레이아웃 분석(카테고리 부여)과 OCR 전략을 config로 선택해 구성하고, 페이지 단위
텍스트 추출(``_extract_pages``, 서브클래스가 구현)을 조합해 최종 아이템 목록을
만드는 절차를 정의한다.
"""

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional, Tuple

from util.rule_layout import Layout
from util.util import has_glyph_corruption

OCR_MODES = ("auto", "force", "disable")
"""ocr.mode로 쓸 수 있는 값. auto: 텍스트가 없거나 글리프가 깨진 페이지만 OCR,
force: 모든 페이지를 무조건 OCR, disable: OCR을 아예 쓰지 않음."""


class BaseLoader(ABC):
    """파일을 읽어 ``{text, category, bbox, page}`` 아이템 목록으로 변환하는 로더의 베이스 클래스.

    서브클래스는 :meth:`_extract_pages`\ 만 구현하면 되고, 레이아웃 분석/OCR 적용/
    아이템 조립은 이 클래스가 공통으로 처리한다.

    Attributes:
        layout_config (dict): ``layout.type``, ``image_dpi`` 등 레이아웃 전략 설정.
        ocr_config (dict): ``ocr.type``, ``ocr.mode`` 등 OCR 전략 설정.
        image_dpi (int): 페이지를 이미지로 렌더링할 때 쓰는 DPI.
        ocr_mode (str): :data:`OCR_MODES` 중 하나. 잘못된 값이면 ``"auto"``\ 로 대체.
        layout: :meth:`get_layout`\ 으로 생성된 레이아웃 분석 전략 인스턴스.
        ocr: :meth:`get_ocr`\ 로 생성된 OCR 전략 인스턴스(``None``\ 이면 OCR 미사용).
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
        대체한 뒤, 레이아웃 전략으로 줄마다 카테고리를 매긴다.

        Args:
            file_path: 읽을 파일 경로.

        Returns:
            ``{text, category, bbox, page}`` 형태의 아이템 목록.
        """
        items = []
        for page_no, (lines, image) in enumerate(self._extract_pages(file_path), start=1):
            if image is not None and self.ocr is not None and self._needs_ocr(lines):
                lines = self.ocr(image, dpi=self.image_dpi)
            categories = self.layout(lines, image=image)
            for (text, bbox, font_size), category in zip(lines, categories):
                items.append(
                    {
                        "text": text,
                        "category": category,
                        "bbox": {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]},
                        "page": page_no,
                    }
                )
        return items

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
        # TODO: dots_mocr이면 그에 맞는 Layout 구현으로 분기
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
    def _extract_pages(
        self, file_path: str
    ) -> Iterable[Tuple[List[Tuple[str, Tuple[float, float, float, float], float]], Optional[bytes]]]:
        """페이지 단위로 ((text, bbox, font_size) 줄 목록, 페이지 이미지 PNG bytes|None)을 순서대로 반환한다."""
        raise NotImplementedError
