"""dots.ocr/dots.mocr `prompt_layout_only_en` 기반 layout 전략 - 평소엔 :mod:`util.dots_mocr_layout`
(``dots_mocr``)과 똑같이 bbox/category만 감지해 PDF/OCR가 이미 뽑은 줄 텍스트를 그대로 쓰지만,
그 줄의 글리프가 깨져 있으면(:func:`util.util.is_glyph_corrupted`) 그 줄만 골라 region의 bbox로
grounding OCR을 호출해 텍스트를 재추출한다.

``genonai/doc_parser``(GenOS의 기존 전처리기)의 ``genos_dots_ocr_layout_model.py``에 있는
``_replace_glyph_text_with_dotsocr`` 아이디어(글리프 깨진/누락된 클러스터만 dots-ocr 텍스트로
교체)를 우리 구조에 맞게 옮긴 것 - 다만 doc_parser는 `prompt_layout_all_en`으로 이미 모든
region의 text를 갖고 있어 교체만 하면 되는 반면, 우리는 감지에 `prompt_layout_only_en`을 쓰므로
(:mod:`util.dots_mocr_layout` 과 동일한 이유) 깨진 줄에 한해서만 별도로 `prompt_grounding_ocr`
을 호출한다. 페이지 전체를 다시 OCR하는 것보다 훨씬 저렴하면서도(대부분의 줄은 PDF 텍스트를
그대로 씀), 글리프 깨진 부분은 실제 모델 OCR로 채운다.

``dots_mocr_all``/``dots_mocr_grounding``과 달리 로더가 뽑은 ``lines`` 를 버리지 않고
그 줄 각각의 텍스트를 (필요할 때만) 보강한다 - 그래도 ``PRODUCES_ITEMS`` 인 이유는 카테고리뿐
아니라 텍스트도 줄 단위로 오버라이드해야 해서 ``BaseLoader`` 의 기본 category-zip 계약만으론
부족하기 때문이다.
"""

from typing import List, Optional, Tuple

from util.dots_mocr_client import LAYOUT_ONLY_PROMPT, DotsMocrClient, grounding_prompt, match_region_index, to_category
from util.util import is_glyph_corrupted

DEFAULT_PROMPT = LAYOUT_ONLY_PROMPT


class DotsMocrAutoLayout:
    """평소엔 PDF/OCR 텍스트 그대로, 글리프 깨진 줄만 dots.ocr grounding OCR로 재추출한다.

    설정 옵션은 :class:`util.dots_mocr_client.DotsMocrClient` 참고.
    """

    NEEDS_IMAGE = True
    """항상 ``True`` — 이 전략은 페이지 이미지가 반드시 필요하다."""

    PRODUCES_ITEMS = True
    """``True`` — :meth:`__call__` 이 카테고리 목록이 아니라 ``{"text","category","bbox"}``
    아이템 목록을 직접 반환한다(글리프 깨진 줄은 텍스트 자체를 오버라이드해야 하므로)."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: :class:`~util.dots_mocr_client.DotsMocrClient` 에 그대로 전달되는 설정 dict
                (예: ``resource/dots_mocr_auto.yaml`` 내용).

        Raises:
            ValueError: ``config`` 에 ``url`` 이 없을 때.
        """
        self._client = DotsMocrClient(config or {}, DEFAULT_PROMPT)

    def __call__(
        self,
        lines: List[Tuple[str, Tuple[float, float, float, float], float]],
        image: Optional[bytes] = None,
    ) -> List[dict]:
        """줄마다 category를 매기고, 글리프 깨진 줄만 grounding OCR로 텍스트를 재추출한다.

        Args:
            lines: ``(text, bbox, font_size)`` 튜플 목록.
            image: 페이지 이미지(PNG bytes). ``None`` 이면 카테고리 보정 없이 원본 텍스트만 담아 반환한다.

        Returns:
            ``{"text", "category", "bbox"}`` 형태의 아이템 목록(``bbox`` 는
            ``{"x0","y0","x1","y1"}`` dict, 72dpi PDF 포인트 좌표).
        """
        if not lines:
            return []
        if image is None:
            return [self._as_item(text, bbox, "text") for text, bbox, _ in lines]

        raw_regions = self._client.detect_raw_regions(image)
        page_regions = self._client.rescale_regions(raw_regions, image)

        items = []
        for text, bbox, _font_size in lines:
            idx = match_region_index(bbox, page_regions)
            category = to_category(page_regions[idx]["label"]) if idx is not None else "text"

            final_text = text
            if is_glyph_corrupted(text) and idx is not None:
                raw_region = raw_regions[idx]
                raw_bbox = (raw_region["l"], raw_region["t"], raw_region["r"], raw_region["b"])
                grounded = self._client.call(image, prompt=grounding_prompt(raw_bbox)).strip()
                if grounded:
                    final_text = grounded
            # idx가 None(이 줄을 포함하는 region이 없음)이면 grounding용 bbox를 만들 수 없어
            # 원본(글리프 깨진) 텍스트를 그대로 둔다 - 드물게 페이지/region 경계 근처에서 발생.

            items.append(self._as_item(final_text, bbox, category))
        return items

    @staticmethod
    def _as_item(text: str, bbox: Tuple[float, float, float, float], category: str) -> dict:
        x0, y0, x1, y1 = bbox
        return {"text": text, "category": category, "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1}}
