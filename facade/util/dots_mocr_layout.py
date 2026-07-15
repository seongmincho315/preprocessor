"""VLM 프롬프트 기반 원격 레이아웃 서버(dots.ocr/dots.mocr 계열 서빙)를 호출하는 layout 전략.

detr와 동일한 방식으로 이 region의 bbox/category만 써서 로더가 이미 추출한 각 줄의
category를 매긴다 - region의 text 자체(모델이 직접 인식한 문자)는 쓰지 않는다.
줄의 텍스트는 PDF 자체(또는 ocr.type 설정에 따른 OCR)에서 이미 뽑은 것을 그대로 쓴다.

dots.ocr는 여러 프롬프트 변형이 있어 텍스트 소스가 다른 여러 layout 전략으로 나눠 구현했다:

- ``dots_mocr``(이 파일) — bbox/category만 감지, 텍스트는 PDF/OCR 그대로 (가장 저렴).
- ``dots_mocr_all``(:mod:`util.dots_mocr_all_layout`) — bbox/category/text를 한 번에 추출,
  region의 text를 그대로 최종 텍스트로 씀.
- ``dots_mocr_grounding``(:mod:`util.dots_mocr_grounding_layout`) — bbox/category만 감지한
  뒤, region마다 별도로 grounding OCR을 호출해 텍스트를 뽑음(region 개수만큼 추가 호출).
- ``dots_mocr_auto``(:mod:`util.dots_mocr_auto_layout`) — 이 파일과 동일하게 PDF/OCR 텍스트를
  기본으로 쓰되, 글리프가 깨진 줄만 골라 grounding OCR로 재추출.

공통 HTTP 호출/응답 파싱/좌표 보정 로직은 :mod:`util.dots_mocr_client` 에 있다.
"""

from typing import List, Optional, Tuple

from util.dots_mocr_client import LAYOUT_ONLY_PROMPT, DotsMocrClient, match_region, to_category

DEFAULT_PROMPT = LAYOUT_ONLY_PROMPT
"""dots.ocr 공식 레포의 `prompt_layout_only_en` — bbox/category만 detection하고 text는
뽑지 않는다(``genonai/doc_parser`` 에서는 텍스트 폭주 시의 fallback 프롬프트로만 쓰지만,
우리는 region의 text 자체를 안 쓰므로 처음부터 이걸 기본값으로 쓴다)."""


class DotsMocrLayout:
    """페이지 이미지를 dots.ocr/dots.mocr 서버에 보내 감지된 region으로 각 줄의 category를 매긴다.

    설정 옵션(``url``/``api_key``/``model``/``image_dpi``/``timeout``/``prompt``/
    ``max_completion_tokens``/``temperature``/``top_p``/``repetition_penalty``/
    ``image_token_prefix``)은 :class:`util.dots_mocr_client.DotsMocrClient` 참고.
    """

    NEEDS_IMAGE = True
    """항상 ``True`` — 이 전략은 페이지 이미지가 반드시 필요하다."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: :class:`~util.dots_mocr_client.DotsMocrClient` 에 그대로 전달되는 설정 dict
                (예: ``resource/dots_mocr.yaml`` 내용).

        Raises:
            ValueError: ``config`` 에 ``url`` 이 없을 때.
        """
        self._client = DotsMocrClient(config or {}, DEFAULT_PROMPT)

    def __call__(
        self,
        lines: List[Tuple[str, Tuple[float, float, float, float], float]],
        image: Optional[bytes] = None,
    ) -> List[str]:
        """줄마다 카테고리를 매긴다.

        Args:
            lines: ``(text, bbox, font_size)`` 튜플 목록.
            image: 페이지 이미지(PNG bytes). ``None`` 이면 모든 줄을 ``"text"`` 로 취급한다.

        Returns:
            ``lines`` 와 같은 길이의 카테고리 문자열 목록.
        """
        if not lines:
            return []
        if image is None:
            return ["text"] * len(lines)

        regions = self._client.rescale_regions(self._client.detect_raw_regions(image), image)
        return [self._match_category(bbox, regions) for _, bbox, _ in lines]

    @staticmethod
    def _match_category(bbox: Tuple[float, float, float, float], regions: List[dict]) -> str:
        """줄의 bbox 중심점을 포함하는 region 중 가장 작은 것의 카테고리를 고른다."""
        region = match_region(bbox, regions)
        return to_category(region["label"]) if region else "text"
