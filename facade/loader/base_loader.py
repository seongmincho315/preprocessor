from abc import ABC, abstractmethod
from typing import Iterable, List, Tuple

from util.layout import Layout


class BaseLoader(ABC):
    """
    1. Layout 분석
        - 카테고리
        - bbox
    2. 텍스트 추출
    """

    def __init__(self, layout_config: dict = None):
        # layout model 받기 (원격 서빙 준비되면 type/url/api_key로 호출하게 될 자리)
        super().__init__()
        self.layout_config = layout_config or {}
        self.layout = self.get_layout()

    def __call__(self, file_path: str, *args, **kwds) -> List[dict]:
        items = []
        for page_no, lines in enumerate(self._extract_pages(file_path), start=1):
            categories = self.layout(lines)
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

    def get_layout(self) -> Layout:
        # TODO: layout_config["type"]이 detr/dots_mocr 등이면 그에 맞는 Layout 구현으로 분기
        return Layout(self.layout_config)

    @abstractmethod
    def _extract_pages(self, file_path: str) -> Iterable[List[Tuple[str, Tuple[float, float, float, float], float]]]:
        """페이지 단위로 (text, bbox, font_size) 줄 목록을 순서대로 반환한다."""
        raise NotImplementedError
