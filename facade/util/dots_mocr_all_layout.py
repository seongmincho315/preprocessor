"""dots.ocr/dots.mocr `prompt_layout_all_en` 기반 layout 전략 - bbox/category/text를
한 번의 VLM 호출로 전부 추출한다.

:mod:`util.dots_mocr_layout` (``dots_mocr``)와 달리 region의 ``text`` 를 그대로 최종
텍스트로 쓴다 - 로더가 PDF/OCR에서 뽑은 ``lines`` 는 아예 무시하고, 이 전략이 페이지의
텍스트 아이템을 직접 만든다(``PRODUCES_ITEMS``). 스캔 문서처럼 PDF 텍스트 레이어가 없거나
못 믿을 때 쓴다 - 그 경우 ``ocr.mode: disable`` 로 설정해 불필요한 OCR 호출을 막는 게 좋다.

``genonai/doc_parser``(GenOS의 기존 전처리기)가 실제 프로덕션에서 기본으로 쓰는 프롬프트와
동일하다(``docling/models/genos_dots_ocr_layout_model.py``). 그쪽은 텍스트 생성이 토큰
상한까지 폭주하는 degeneration(``finish_reason == "length"``)이 실제로 발생해서 대응
로직(재시도 시 텍스트 없는 프롬프트로 폴백)을 두는데, 여기서는 그 폴백까지는 옮기지
않았다 - 필요하면 :mod:`util.dots_mocr_layout`(``dots_mocr``, 텍스트 없는 버전)로
바꿔 쓰면 된다.
"""

from typing import List, Optional, Tuple

from util.dots_mocr_client import LAYOUT_ALL_PROMPT, DotsMocrClient, to_category

DEFAULT_PROMPT = LAYOUT_ALL_PROMPT


class DotsMocrAllLayout:
    """페이지 이미지를 dots.ocr/dots.mocr 서버에 보내 bbox/category/text가 담긴 region을
    받아, 그대로 페이지의 텍스트 아이템으로 만든다.

    설정 옵션은 :class:`util.dots_mocr_client.DotsMocrClient` 참고.
    """

    NEEDS_IMAGE = True
    """항상 ``True`` — 이 전략은 페이지 이미지가 반드시 필요하다."""

    PRODUCES_ITEMS = True
    """``True`` — :meth:`__call__` 이 카테고리 목록이 아니라 ``{"text","category","bbox"}``
    아이템 목록을 직접 반환한다. ``BaseLoader`` 는 이 경우 로더가 뽑은 ``lines`` 를 버리고
    이 아이템들을 그대로 쓴다."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: :class:`~util.dots_mocr_client.DotsMocrClient` 에 그대로 전달되는 설정 dict
                (예: ``resource/dots_mocr_all.yaml`` 내용).

        Raises:
            ValueError: ``config`` 에 ``url`` 이 없을 때.
        """
        self._client = DotsMocrClient(config or {}, DEFAULT_PROMPT)

    def __call__(
        self,
        lines: List[Tuple[str, Tuple[float, float, float, float], float]],
        image: Optional[bytes] = None,
    ) -> List[dict]:
        """페이지 이미지에서 텍스트 아이템을 직접 추출한다. ``lines`` 는 쓰지 않는다.

        Args:
            lines: 사용하지 않음(``PRODUCES_ITEMS`` 계약상 시그니처만 맞춘다).
            image: 페이지 이미지(PNG bytes). ``None`` 이면 빈 목록.

        Returns:
            ``{"text", "category", "bbox"}`` 형태의 아이템 목록(``bbox`` 는
            ``{"x0","y0","x1","y1"}`` dict, 72dpi PDF 포인트 좌표).
        """
        if image is None:
            return []

        regions = self._client.detect_raw_regions(image)
        regions = self._client.rescale_regions(regions, image)

        items = []
        for region in regions:
            text = (region.get("text") or "").strip()
            if not text:
                # Picture는 공식 스펙상 text 없음. 그 외 빈 text는 뽑을 콘텐츠가 없다는 뜻이라 스킵.
                continue
            items.append(
                {
                    "text": text,
                    "category": to_category(region["label"]),
                    "bbox": {"x0": region["l"], "y0": region["t"], "x1": region["r"], "y1": region["b"]},
                }
            )
        return items
