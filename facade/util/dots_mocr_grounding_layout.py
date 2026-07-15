"""dots.ocr/dots.mocr `prompt_layout_only_en` + `prompt_grounding_ocr` 기반 layout 전략.

먼저 bbox/category만 감지(:mod:`util.dots_mocr_layout` 과 동일한 첫 단계)한 뒤, 감지된
region마다 별도로 `prompt_grounding_ocr` 를 호출해 그 bbox 안의 텍스트만 뽑는다. 공식
레포(`dots_ocr/parser.py`의 `get_prompt`)를 따라 이미지를 자르지 않고 원본 페이지 이미지
그대로 재사용하면서, bbox 좌표를 프롬프트 텍스트에 문자열로 첨부하는 grounding 방식을 쓴다
(이미지를 실제로 잘라서 보내는 방식은 공식적으로 검증된 경로가 아니고, Pillow 의존성도
추가로 필요해 채택하지 않았다).

:mod:`util.dots_mocr_all_layout` (``dots_mocr_all``)과 마찬가지로 로더가 뽑은 ``lines`` 는
버리고 이 전략이 페이지의 텍스트 아이템을 직접 만든다(``PRODUCES_ITEMS``). 텍스트 생성이
한 번에 전체 페이지가 아니라 region 하나 분량이라 degeneration(토큰 상한까지 폭주) 위험이
훨씬 낮지만, 페이지당 HTTP 호출이 "감지 1회 + region 개수만큼"으로 늘어난다.
"""

from typing import List, Optional, Tuple

from util.dots_mocr_client import LAYOUT_ONLY_PROMPT, DotsMocrClient, grounding_prompt, to_category

DEFAULT_PROMPT = LAYOUT_ONLY_PROMPT
"""감지(1차 호출)에 쓰는 프롬프트. region별 텍스트 추출(2차 호출)은 항상
:func:`util.dots_mocr_client.grounding_prompt` 로 만든 `prompt_grounding_ocr` 를 쓴다."""


class DotsMocrGroundingLayout:
    """dots.ocr/dots.mocr로 레이아웃을 감지한 뒤, region마다 grounding OCR을 호출해 텍스트를 뽑는다.

    설정 옵션은 :class:`util.dots_mocr_client.DotsMocrClient` 참고.
    """

    NEEDS_IMAGE = True
    """항상 ``True`` — 이 전략은 페이지 이미지가 반드시 필요하다."""

    PRODUCES_ITEMS = True
    """``True`` — :meth:`__call__` 이 카테고리 목록이 아니라 ``{"text","category","bbox"}``
    아이템 목록을 직접 반환한다."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: :class:`~util.dots_mocr_client.DotsMocrClient` 에 그대로 전달되는 설정 dict
                (예: ``resource/dots_mocr_grounding.yaml`` 내용).

        Raises:
            ValueError: ``config`` 에 ``url`` 이 없을 때.
        """
        self._client = DotsMocrClient(config or {}, DEFAULT_PROMPT)

    def __call__(
        self,
        lines: List[Tuple[str, Tuple[float, float, float, float], float]],
        image: Optional[bytes] = None,
    ) -> List[dict]:
        """페이지 이미지에서 region을 감지하고, region마다 grounding OCR로 텍스트를 뽑는다.

        Args:
            lines: 사용하지 않음(``PRODUCES_ITEMS`` 계약상 시그니처만 맞춘다).
            image: 페이지 이미지(PNG bytes). ``None`` 이면 빈 목록.

        Returns:
            ``{"text", "category", "bbox"}`` 형태의 아이템 목록(``bbox`` 는
            ``{"x0","y0","x1","y1"}`` dict, 72dpi PDF 포인트 좌표).
        """
        if image is None:
            return []

        # raw_regions: 모델이 실제로 본 리사이즈 좌표계(grounding 프롬프트에 그대로 씀).
        # page_regions: 같은 순서로 72dpi 포인트 좌표로 보정한 값(최종 출력 bbox용).
        raw_regions = self._client.detect_raw_regions(image)
        page_regions = self._client.rescale_regions(raw_regions, image)

        items = []
        for raw_region, page_region in zip(raw_regions, page_regions):
            category = to_category(raw_region["label"])
            if category == "picture":
                continue

            bbox = (raw_region["l"], raw_region["t"], raw_region["r"], raw_region["b"])
            text = self._client.call(image, prompt=grounding_prompt(bbox)).strip()
            if not text:
                continue

            items.append(
                {
                    "text": text,
                    "category": category,
                    "bbox": {
                        "x0": page_region["l"],
                        "y0": page_region["t"],
                        "x1": page_region["r"],
                        "y1": page_region["b"],
                    },
                }
            )
        return items
