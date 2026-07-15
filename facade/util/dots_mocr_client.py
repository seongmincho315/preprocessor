"""dots.ocr/dots.mocr(rednote-hilab) 계열 VLM 서버를 호출하는 클라이언트 + 공통 유틸리티.

`facade/util/dots_mocr_*_layout.py` 의 여러 layout 전략(레이아웃만 감지, 텍스트까지 한 번에
추출, region별 grounding OCR 등)이 공유하는 HTTP 호출/응답 파싱/좌표 보정 로직을 모아둔다.

참고로 삼은 실제 구현 두 곳:

- 공식 레포 ``rednote-hilab/dots.ocr``의 ``dots_ocr/utils/prompts.py`` (여러 프롬프트 변형)와
  ``dots_ocr/parser.py`` (``prompt_grounding_ocr`` 사용법 — 이미지를 자르지 않고 원본 이미지
  그대로 보내면서 bbox 좌표를 프롬프트 텍스트에 문자열로 첨부하는 grounding 방식).
- ``genonai/doc_parser``(GenOS의 기존 전처리기)의
  ``docling/models/genos_dots_ocr_layout_model.py`` — 실제 프로덕션에서 dots-mocr를 GenOS
  llmops 게이트웨이로 서빙해 호출하는 코드. bbox가 dots.ocr의 Qwen2.5-VL 비전 인코더가
  내부적으로 리사이즈한 해상도 기준이라 되돌려 스케일해야 한다는 점(:func:`_smart_resize`)과
  글리프 깨진 PDF 텍스트를 dots-ocr 텍스트로 교체하는 아이디어(``_replace_glyph_text_with_dotsocr``)
  를 여기서 가져왔다.
"""

import base64
import json
import math
import re
import struct
import urllib.error
import urllib.request
from typing import List, Optional, Tuple

from util.util import CATEGORIES

# dots.ocr 공식 레포(dots_ocr/utils/prompts.py)의 프롬프트 변형들.
LAYOUT_ONLY_PROMPT = (
    "Please output the layout information from this PDF image, including each layout's "
    "bbox and its category. The bbox should be in the format [x1, y1, x2, y2]. The layout "
    "categories for the PDF document include ['Caption', 'Footnote', 'Formula', "
    "'List-item', 'Page-footer', 'Page-header', 'Picture', 'Section-header', 'Table', "
    "'Text', 'Title']. Do not output the corresponding text. The layout result should be "
    "in JSON format."
)
"""`prompt_layout_only_en` — bbox/category만 detection하고 text는 뽑지 않는다."""

LAYOUT_ALL_PROMPT = (
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
"""`prompt_layout_all_en` — bbox/category/text를 한 번에 뽑는다(genonai/doc_parser의 기본
프롬프트). 텍스트 생성이 토큰 상한까지 폭주하는 degeneration 위험이 있다(doc_parser가
`finish_reason == "length"` 감지 시 `LAYOUT_ONLY_PROMPT`로 재시도하는 이유)."""

GROUNDING_PROMPT_PREFIX = "Extract text from the given bounding box on the image (format: [x1, y1, x2, y2]).\nBounding Box:\n"
"""`prompt_grounding_ocr` — 이미지를 자르지 않고 원본 그대로 보내면서, 뒤에 bbox 좌표
문자열을 이어붙여 그 bbox 안의 텍스트만 뽑아달라고 요청한다(dots_ocr/parser.py의
`get_prompt` 참고). bbox는 모델이 실제로 보는 리사이즈된 좌표계 기준으로 붙여야 한다 —
:meth:`DotsMocrClient.detect_raw_regions` 가 돌려주는, 아직 스케일 보정 전인 region의
``l/t/r/b`` 를 그대로 쓰면 된다."""

# dots.ocr/dots.mocr는 Qwen2.5-VL 비전 인코더를 쓰는데, 전처리 단계에서 이미지를 이
# factor의 배수 해상도로 리사이즈해서 모델에 넣는다("smart resize", Qwen2-VL 계열 공통
# 알고리즘). 모델이 돌려주는 bbox는 우리가 보낸 원본 이미지가 아니라 이 리사이즈된 해상도
# 기준 픽셀 좌표라, :func:`_smart_resize` 로 그 해상도를 재계산해 되돌려 스케일해야 한다.
# 출처: genonai/doc_parser의 docling/models/genos_dots_ocr_layout_model.py
_IMAGE_FACTOR = 28
_MIN_PIXELS = 3136
_MAX_PIXELS = 11289600

# JSON 앞뒤에 ```json ... ``` 코드펜스를 붙이는 모델이 있어, 파싱 전에 벗겨낸다.
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class DotsMocrClient:
    """dots.ocr/dots.mocr OpenAI 호환 chat completions 엔드포인트 호출 + 응답 파싱 공통 로직.

    Attributes:
        url (str): chat completions 엔드포인트.
        api_key (str | None): 설정하면 ``Authorization: Bearer <api_key>`` 로 보낸다.
        model (str | None): 요청 payload의 ``model`` 필드. 서버가 모델 이름으로 라우팅하면 필요.
        image_dpi (int): 페이지 이미지를 렌더링한 DPI(region bbox와 스케일을 맞추는 데 쓰임).
        timeout (int): HTTP 요청 타임아웃(초).
        prompt (str): 이 클라이언트의 기본 프롬프트(호출 시 오버라이드 가능).
        max_completion_tokens (int): 모델 응답 최대 토큰 수.
        temperature (float): 생성 temperature.
        top_p (float): 생성 top_p.
        repetition_penalty (float | None): 반복 억제 페널티. ``None`` 이면 payload에서 뺀다.
        image_token_prefix (str): 프롬프트 앞에 붙일 접두어(GenOS 게이트웨이 등 채팅 템플릿을
            자동 적용하지 않는 서버 대응용). 기본값은 빈 문자열.
    """

    def __init__(self, config: dict, default_prompt: str):
        """
        Args:
            config: ``url``, ``api_key``, ``model``, ``image_dpi``, ``timeout``, ``prompt``,
                ``max_completion_tokens``, ``temperature``, ``top_p``, ``repetition_penalty``,
                ``image_token_prefix`` 를 담은 설정 dict.
            default_prompt: ``config`` 에 ``prompt`` 가 없을 때 쓸 기본 프롬프트.

        Raises:
            ValueError: ``config`` 에 ``url`` 이 없을 때.
        """
        config = config or {}
        self.url = config.get("url")
        if not self.url:
            raise ValueError("dots.ocr/dots.mocr layout 전략을 쓰려면 설정 yaml에 url을 지정해야 합니다.")
        self.api_key = config.get("api_key")
        self.model = config.get("model")
        self.image_dpi = config.get("image_dpi", 150)
        self.timeout = config.get("timeout", 60)
        self.prompt = config.get("prompt") or default_prompt
        self.max_completion_tokens = config.get("max_completion_tokens", config.get("max_tokens", 16384))
        self.temperature = config.get("temperature", 0.1)
        self.top_p = config.get("top_p", 0.9)
        self.repetition_penalty = config.get("repetition_penalty", 1.15)
        self.image_token_prefix = config.get("image_token_prefix", "")

    def call(self, image: bytes, prompt: Optional[str] = None) -> str:
        """모델을 호출해 응답 텍스트(``choices[0].message.content``)를 반환한다.

        일부 서버는 ``max_completion_tokens`` 대신 ``max_tokens`` 파라미터명을 쓰므로,
        전자로 보내 HTTP 400이 오면 후자로 한 번 더 시도한다
        (``genonai/doc_parser``의 ``call_vlm_server`` 참고).

        Args:
            image: 페이지(또는 grounding 용 원본) 이미지(PNG bytes).
            prompt: 이 호출에만 쓸 프롬프트. ``None`` 이면 :attr:`prompt` 를 쓴다.

        Returns:
            모델 응답 텍스트.
        """
        payload = self._build_payload(image, prompt if prompt is not None else self.prompt)
        try:
            return self._post(payload)
        except urllib.error.HTTPError as e:
            if e.code != 400:
                raise
            fallback = dict(payload)
            fallback["max_tokens"] = fallback.pop("max_completion_tokens")
            return self._post(fallback)

    def _build_payload(self, image: bytes, prompt: str) -> dict:
        """chat completions 요청 payload를 만든다."""
        image_b64 = base64.b64encode(image).decode("ascii")
        prompt_text = self.image_token_prefix + prompt
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": prompt_text},
                    ],
                }
            ],
            "max_completion_tokens": self.max_completion_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if self.model:
            payload["model"] = self.model
        if self.repetition_penalty is not None:
            payload["repetition_penalty"] = self.repetition_penalty
        return payload

    def _post(self, payload: dict) -> str:
        """payload를 POST하고 ``choices[0].message.content`` 를 반환한다."""
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
        return result["choices"][0]["message"]["content"]

    def detect_raw_regions(self, image: bytes, prompt: Optional[str] = None) -> List[dict]:
        """레이아웃을 감지해 region 목록을 반환한다(스케일 보정 전 - 모델이 실제로 본
        리사이즈 해상도 기준 좌표).

        ``prompt_grounding_ocr`` 용 bbox는 이 좌표계로 넘겨야 하므로(:data:`GROUNDING_PROMPT_PREFIX`
        참고), 보정 전 값을 그대로 노출한다. 줄 매칭이나 최종 출력에는 :meth:`rescale_regions` 로
        보정한 값을 써야 한다.

        Args:
            image: 페이지 이미지(PNG bytes).
            prompt: 감지에 쓸 프롬프트. ``None`` 이면 :attr:`prompt` 를 쓴다.

        Returns:
            ``{"label", "text", "l", "t", "r", "b"}`` 형태의 region 목록(``text`` 는 없으면
            ``None``). 파싱 실패 시 빈 리스트.
        """
        content = self.call(image, prompt=prompt)
        return parse_layout_json(content)

    def rescale_regions(self, regions: List[dict], image: bytes) -> List[dict]:
        """:meth:`detect_raw_regions` 가 돌려준 region의 bbox를 72dpi PDF 포인트 좌표로 보정한다.

        모델이 보는 이미지 해상도(smart-resize)와 우리가 보낸 이미지 해상도가 다르므로,
        (모델이 본 리사이즈 해상도) -> (우리가 보낸 이미지 픽셀) -> (72dpi 포인트) 순으로
        되돌린다. 입력과 같은 순서/개수를 유지하므로, ``zip(raw_regions, rescaled_regions)``
        로 같은 region의 두 좌표계를 함께 쓸 수 있다.

        Args:
            regions: :meth:`detect_raw_regions` 가 돌려준 region 목록.
            image: 감지에 쓴 페이지 이미지(PNG bytes) - 픽셀 크기를 읽는 데 쓴다.

        Returns:
            같은 길이의 region 목록(``l/t/r/b`` 만 PDF 포인트 좌표로 교체).
        """
        if not regions:
            return []

        image_size = _png_size(image)
        scale = self.image_dpi / 72.0
        if image_size is not None:
            img_w, img_h = image_size
            resized_h, resized_w = _smart_resize(
                height=img_h, width=img_w, factor=_IMAGE_FACTOR, min_pixels=_MIN_PIXELS, max_pixels=_MAX_PIXELS
            )
            scale_x = (resized_w / img_w) * scale
            scale_y = (resized_h / img_h) * scale
        else:
            scale_x = scale_y = scale

        return [
            {**r, "l": r["l"] / scale_x, "t": r["t"] / scale_y, "r": r["r"] / scale_x, "b": r["b"] / scale_y}
            for r in regions
        ]


def parse_layout_json(content: str) -> List[dict]:
    """모델 응답 텍스트에서 ``[{"bbox": [...], "category": "...", "text": "..."}]`` 배열을 뽑는다.

    모델이 앞뒤에 잡담을 붙이거나(````json ...` 코드펜스 등) 토큰 한도로 배열을 중간에
    자르는 경우가 있어, 코드펜스를 벗기고 첫 ``[`` 이전을 버린 뒤 마지막 완전한 ``}``
    뒤에서 배열을 닫는 식으로 관용적으로 정리한 뒤 파싱한다.

    Args:
        content: 모델이 반환한 원본 텍스트.

    Returns:
        ``{"label", "text", "l", "t", "r", "b"}`` 형태의 region 목록(스케일 보정 전, 모델이 본
        해상도 기준). ``text`` 키는 응답에 없으면(예: `prompt_layout_only_en`) ``None``.
        파싱 실패 시 빈 리스트.
    """
    fenced = _CODE_FENCE_RE.search(content)
    cleaned = _clean_json_array(fenced.group(1) if fenced else content)
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
        text = elem.get("text")
        regions.append({"label": label, "text": text if isinstance(text, str) else None, "l": l, "t": t, "r": r, "b": b})
    return regions


def to_category(label: str) -> str:
    """dots.ocr/dots.mocr region label(예: ``"Section-header"``)을
    :data:`util.util.CATEGORIES` 값으로 정규화한다.

    Args:
        label: 원본 label 문자열.

    Returns:
        ``CATEGORIES`` 에 속하는 정규화된 카테고리, 없으면 ``"text"``.
    """
    key = label.lower().replace(" ", "_").replace("-", "_")
    return key if key in CATEGORIES else "text"


def match_region_index(bbox: Tuple[float, float, float, float], regions: List[dict]) -> Optional[int]:
    """bbox 중심점을 포함하는 region 중 가장 작은 것의 인덱스를 고른다.

    인덱스로 돌려주는 이유: ``detect_raw_regions``/``rescale_regions`` 는 같은 순서를
    유지하므로, 한 좌표계(예: 72dpi 포인트)에서 매칭한 인덱스로 다른 좌표계(모델이 본
    리사이즈 좌표)의 같은 region을 바로 찾을 수 있다(``dots_mocr_auto_layout`` 이
    grounding bbox를 만들 때 이렇게 쓴다).

    Args:
        bbox: 매칭할 ``(x0, y0, x1, y1)``.
        regions: 후보 region 목록(좌표계는 ``bbox`` 와 같아야 함).

    Returns:
        매칭되는 region이 없으면 ``None``, 있으면 그 region의 ``regions`` 내 인덱스.
    """
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    candidates = [(i, r) for i, r in enumerate(regions) if r["l"] <= cx <= r["r"] and r["t"] <= cy <= r["b"]]
    if not candidates:
        return None
    return min(candidates, key=lambda ir: (ir[1]["r"] - ir[1]["l"]) * (ir[1]["b"] - ir[1]["t"]))[0]


def match_region(bbox: Tuple[float, float, float, float], regions: List[dict]) -> Optional[dict]:
    """bbox 중심점을 포함하는 region 중 가장 작은 것을 고른다. :func:`match_region_index` 참고.

    Args:
        bbox: 매칭할 ``(x0, y0, x1, y1)``.
        regions: 후보 region 목록(좌표계는 ``bbox`` 와 같아야 함).

    Returns:
        매칭되는 region이 없으면 ``None``, 있으면 그 region dict.
    """
    idx = match_region_index(bbox, regions)
    return regions[idx] if idx is not None else None


def grounding_prompt(bbox: Tuple[float, float, float, float]) -> str:
    """주어진(모델이 본 리사이즈 좌표계 기준) bbox에 대한 ``prompt_grounding_ocr`` 프롬프트를 만든다."""
    x0, y0, x1, y1 = bbox
    return GROUNDING_PROMPT_PREFIX + str([round(x0), round(y0), round(x1), round(y1)])


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


def _png_size(data: bytes) -> Optional[Tuple[int, int]]:
    """PNG bytes의 IHDR 청크에서 ``(width, height)`` 픽셀 크기를 읽는다.

    Pillow 등 이미지 라이브러리 없이, PNG 포맷 스펙(시그니처 8바이트 + IHDR 청크)만으로
    직접 파싱한다. PNG가 아니거나 형식이 예상과 다르면 ``None``.
    """
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _round_by_factor(number: float, factor: int) -> int:
    return round(number / factor) * factor


def _ceil_by_factor(number: float, factor: int) -> int:
    return math.ceil(number / factor) * factor


def _floor_by_factor(number: float, factor: int) -> int:
    return math.floor(number / factor) * factor


def _smart_resize(
    height: int,
    width: int,
    factor: int = _IMAGE_FACTOR,
    min_pixels: int = _MIN_PIXELS,
    max_pixels: int = _MAX_PIXELS,
) -> Tuple[int, int]:
    """Qwen2-VL 계열이 이미지 전처리에서 쓰는 "smart resize"를 재현한다.

    치수를 ``factor`` 의 배수로 반올림하고, 전체 픽셀 수가 ``[min_pixels, max_pixels]``
    범위를 벗어나면 종횡비를 유지한 채 그 범위 안으로 다시 스케일한다. dots.ocr가
    돌려주는 bbox는 이 함수가 계산하는 해상도 기준이라, 우리가 보낸 원본 이미지
    해상도로 되돌리려면 이 결과와 원본 크기의 비율만큼 나눠야 한다.
    출처: genonai/doc_parser의 docling/models/genos_dots_ocr_layout_model.py.

    Args:
        height: 원본(우리가 보낸) 이미지 높이(px).
        width: 원본(우리가 보낸) 이미지 너비(px).
        factor: 리사이즈된 치수가 맞춰야 하는 배수.
        min_pixels: 리사이즈 후 최소 총 픽셀 수.
        max_pixels: 리사이즈 후 최대 총 픽셀 수.

    Returns:
        ``(resized_height, resized_width)``.

    Raises:
        ValueError: ``height``/``width`` 가 0 이하이거나 종횡비가 200을 넘을 때.
    """
    if height <= 0 or width <= 0:
        raise ValueError(f"Invalid image size: height={height}, width={width}")
    if max(height, width) / min(height, width) > 200:
        raise ValueError(
            f"absolute aspect ratio must be smaller than 200, got {max(height, width) / min(height, width)}"
        )

    h_bar = max(factor, _round_by_factor(height, factor))
    w_bar = max(factor, _round_by_factor(width, factor))

    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = max(factor, _floor_by_factor(height / beta, factor))
        w_bar = max(factor, _floor_by_factor(width / beta, factor))
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = _ceil_by_factor(height * beta, factor)
        w_bar = _ceil_by_factor(width * beta, factor)
        if h_bar * w_bar > max_pixels:
            beta = math.sqrt((h_bar * w_bar) / max_pixels)
            h_bar = max(factor, _floor_by_factor(h_bar / beta, factor))
            w_bar = max(factor, _floor_by_factor(w_bar / beta, factor))

    return int(h_bar), int(w_bar)
