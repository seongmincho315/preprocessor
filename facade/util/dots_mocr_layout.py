"""VLM 프롬프트 기반 원격 레이아웃 서버(dots.ocr/dots.mocr 계열 서빙)를 호출하는 layout 전략.

dots.ocr/dots.mocr(rednote-hilab)은 OpenAI 호환 chat completions 엔드포인트(예: vLLM으로
서빙)에 페이지 이미지 + 프롬프트를 보내면 다음 JSON 배열을 텍스트로 돌려준다::

    [{"bbox": [x1, y1, x2, y2], "category": "Section-header", "text": "..."}, ...]

detr와 동일한 방식으로 이 region의 bbox/category만 써서 로더가 이미 추출한 각 줄의
category를 매긴다 - region의 text 자체(모델이 직접 인식한 문자)는 쓰지 않는다.
참고: docling-project/docling의 ``docling/utils/dots_utils.py``,
``docling/utils/api_image_request.py``.
"""

import base64
import json
import urllib.request
from typing import List, Optional, Tuple

from util.util import CATEGORIES

DEFAULT_PROMPT = (
    "Please output the layout information from the PDF image, including each layout "
    "element's bbox, its category, and the corresponding text content within the bbox.\n\n"
    "1. Bbox format: [x1, y1, x2, y2]\n\n"
    "2. Layout Categories: The possible categories are ['Caption', 'Footnote', 'Formula', "
    "'List-item', 'Page-footer', 'Page-header', 'Picture', 'Section-header', 'Table', "
    "'Text', 'Title'].\n\n"
    "3. Text Extraction & Formatting Rules:\n"
    "    - Picture: For the 'Picture' category, the text field should be omitted.\n"
    "    - Formula: Format its text as LaTeX.\n"
    "    - Table: Format its text as HTML.\n"
    "    - All Others (Text, Title, etc.): Format their text as Markdown.\n\n"
    "4. Constraints:\n"
    "    - The output text must be the original text from the image, with no translation.\n"
    "    - All layout elements must be sorted according to human reading order.\n\n"
    "5. Final Output: The entire output must be a single JSON array."
)


class DotsMocrLayout:
    """페이지 이미지를 dots.ocr/dots.mocr 서버에 보내 감지된 region으로 각 줄의 category를 매긴다.

    Attributes:
        url (str): OpenAI 호환 chat completions 엔드포인트.
        api_key (str | None): 인증이 필요하면 ``Authorization: Bearer <api_key>`` 로 보낸다.
        image_dpi (int): 페이지 이미지를 렌더링한 DPI(줄 bbox와 스케일을 맞추는 데 쓰임).
        timeout (int): HTTP 요청 타임아웃(초).
        prompt (str): 모델에 보낼 레이아웃 분석 프롬프트.
        max_tokens (int): 모델 응답 최대 토큰 수.
    """

    NEEDS_IMAGE = True
    """항상 ``True`` — 이 전략은 페이지 이미지가 반드시 필요하다."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: ``url``, ``api_key``, ``image_dpi``, ``timeout``, ``prompt``, ``max_tokens``
                를 담은 설정 dict(예: ``resource/dots_mocr.yaml`` 내용).

        Raises:
            ValueError: ``config`` 에 ``url`` 이 없을 때.
        """
        config = config or {}
        self.url = config.get("url")
        if not self.url:
            raise ValueError("layout.type=dots_mocr를 쓰려면 dots_mocr.yaml에 url을 설정해야 합니다.")
        self.api_key = config.get("api_key")
        self.image_dpi = config.get("image_dpi", 150)
        self.timeout = config.get("timeout", 60)
        self.prompt = config.get("prompt") or DEFAULT_PROMPT
        self.max_tokens = config.get("max_tokens", 24000)

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

        regions = self._detect(image)
        # dots.ocr/dots.mocr region bbox는 우리가 보낸 이미지(image_dpi 기준) 픽셀 좌표라,
        # 줄 bbox(PDF 포인트, 72dpi 기준)와 스케일을 맞춘다.
        scale = self.image_dpi / 72.0
        regions = [
            {**r, "l": r["l"] / scale, "t": r["t"] / scale, "r": r["r"] / scale, "b": r["b"] / scale}
            for r in regions
        ]
        return [self._match_category(bbox, regions) for _, bbox, _ in lines]

    def _detect(self, image: bytes) -> List[dict]:
        """OpenAI 호환 chat completions 엔드포인트를 호출해 페이지 하나의 레이아웃 region 목록을 받는다.

        Args:
            image: 페이지 이미지(PNG bytes).

        Returns:
            ``{"label", "l", "t", "r", "b"}`` 형태의 region 목록. 응답 파싱에 실패하면 빈 리스트.
        """
        image_b64 = base64.b64encode(image).decode("ascii")
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": self.prompt},
                    ],
                }
            ],
            "max_tokens": self.max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"]
        return self._parse_regions(content)

    @staticmethod
    def _parse_regions(content: str) -> List[dict]:
        """모델 응답 텍스트에서 ``[{"bbox": [...], "category": "..."}]`` 배열을 뽑는다.

        모델이 앞뒤에 잡담을 붙이거나(````json ...` 등) 토큰 한도로 배열을 중간에
        자르는 경우가 있어, 첫 ``[`` 이전을 버리고 마지막 완전한 ``}`` 뒤에서 배열을
        닫는 등 관용적으로 정리한 뒤 파싱한다.

        Args:
            content: 모델이 반환한 원본 텍스트.

        Returns:
            ``{"label", "l", "t", "r", "b"}`` 형태의 region 목록. 파싱 실패 시 빈 리스트.
        """
        cleaned = _clean_json_array(content)
        try:
            elements = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
        if not isinstance(elements, list):
            return []

        regions = []
        for elem in elements:
            if not isinstance(elem, dict):
                continue
            bbox = elem.get("bbox")
            label = elem.get("category")
            if not isinstance(bbox, list) or len(bbox) != 4 or not label:
                continue
            try:
                l, t, r, b = (float(v) for v in bbox)
            except (TypeError, ValueError):
                continue
            regions.append({"label": label, "l": l, "t": t, "r": r, "b": b})
        return regions

    @staticmethod
    def _match_category(bbox: Tuple[float, float, float, float], regions: List[dict]) -> str:
        """줄의 bbox 중심점을 포함하는 region 중 가장 작은 것의 카테고리를 고른다.

        Args:
            bbox: 줄의 ``(x0, y0, x1, y1)``.
            regions: :meth:`_detect` 가 반환한 region 목록(스케일 보정 완료).

        Returns:
            매칭되는 region이 없으면 ``"text"``, 있으면 :meth:`_to_category` 결과.
        """
        x0, y0, x1, y1 = bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        candidates = [r for r in regions if r["l"] <= cx <= r["r"] and r["t"] <= cy <= r["b"]]
        if not candidates:
            return "text"
        best = min(candidates, key=lambda r: (r["r"] - r["l"]) * (r["b"] - r["t"]))
        return DotsMocrLayout._to_category(best["label"])

    @staticmethod
    def _to_category(label: str) -> str:
        """dots.ocr/dots.mocr region label(예: ``"Section-header"``)을
        :data:`util.util.CATEGORIES` 값으로 정규화한다.

        Args:
            label: 원본 label 문자열.

        Returns:
            ``CATEGORIES`` 에 속하는 정규화된 카테고리, 없으면 ``"text"``.
        """
        key = label.lower().replace(" ", "_").replace("-", "_")
        return key if key in CATEGORIES else "text"


def _clean_json_array(raw: str) -> str:
    """잘렸거나 잡담이 섞인 응답에서 JSON 배열만 관용적으로 추출한다.

    1. 첫 ``[`` 이전 텍스트는 버린다.
    2. ``]`` 로 끝나지 않으면 마지막 ``}`` 뒤에서 배열을 닫는다.
    3. 유효한 구조를 찾지 못하면 ``"[]"``.
    """
    idx = raw.find("[")
    if idx == -1:
        return "[]"
    raw = raw[idx:]

    stripped = raw.rstrip()
    if not stripped.endswith("]"):
        last_brace = stripped.rfind("}")
        if last_brace == -1:
            return "[]"
        raw = stripped[: last_brace + 1] + "]"

    return raw
