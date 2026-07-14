from abc import ABC, abstractmethod
from typing import Iterable, List, Optional, Tuple

from util.rule_layout import Layout
from util.util import has_glyph_corruption

OCR_MODES = ("auto", "force", "disable")


class BaseLoader(ABC):
    """
    1. Layout 분석
        - 카테고리
        - bbox
    2. 텍스트 추출
    """

    def __init__(self, layout_config: dict = None, ocr_config: dict = None):
        # layout/ocr model 받기 (원격 서빙 type/url/api_key로 호출)
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
        return getattr(self.layout, "NEEDS_IMAGE", False) or self.ocr is not None

    def __call__(self, file_path: str, *args, **kwds) -> List[dict]:
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
