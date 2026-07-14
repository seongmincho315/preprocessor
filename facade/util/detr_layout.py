"""RT-DETR 기반 원격 레이아웃 서버(`detr` 레포 서빙)를 호출하는 layout 전략."""

import base64
import json
import urllib.request
from typing import List, Optional, Tuple

from util.util import CATEGORIES


class DetrLayout:
    """페이지 이미지를 detr 서버 `/detect`\ 로 보내 감지된 region으로 각 줄의 category를 매긴다.

    Attributes:
        url (str): detr 서버 base URL.
        image_dpi (int): 페이지 이미지를 렌더링한 DPI(줄 bbox와 스케일을 맞추는 데 쓰임).
        timeout (int): HTTP 요청 타임아웃(초).
    """

    NEEDS_IMAGE = True
    """항상 ``True`` — 이 전략은 페이지 이미지가 반드시 필요하다."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: ``url``, ``image_dpi``, ``timeout``\ 을 담은 설정 dict
                (예: ``resource/detr.yaml`` 내용).

        Raises:
            ValueError: ``config``\ 에 ``url``\ 이 없을 때.
        """
        config = config or {}
        self.url = config.get("url")
        if not self.url:
            raise ValueError("layout.type=detr을 쓰려면 detr.yaml에 url을 설정해야 합니다.")
        self.image_dpi = config.get("image_dpi", 150)
        self.timeout = config.get("timeout", 60)

    def __call__(
        self,
        lines: List[Tuple[str, Tuple[float, float, float, float], float]],
        image: Optional[bytes] = None,
    ) -> List[str]:
        """줄마다 카테고리를 매긴다.

        Args:
            lines: ``(text, bbox, font_size)`` 튜플 목록.
            image: 페이지 이미지(PNG bytes). ``None``\ 이면 모든 줄을 ``"text"``\ 로 취급한다.

        Returns:
            ``lines``\ 와 같은 길이의 카테고리 문자열 목록.
        """
        if not lines:
            return []
        if image is None:
            return ["text"] * len(lines)

        regions = self._detect(image)
        # detr region bbox는 image_dpi 기준 픽셀 좌표라, 줄 bbox(PDF 포인트, 72dpi 기준)와 스케일을 맞춘다.
        scale = self.image_dpi / 72.0
        regions = [
            {**r, "l": r["l"] / scale, "t": r["t"] / scale, "r": r["r"] / scale, "b": r["b"] / scale}
            for r in regions
        ]
        return [self._match_category(bbox, regions) for _, bbox, _ in lines]

    def _detect(self, image: bytes) -> List[dict]:
        """detr 서버 ``/detect``\ 를 호출해 이미지 하나의 감지 region 목록을 받는다.

        Args:
            image: 페이지 이미지(PNG bytes).

        Returns:
            ``{"label", "confidence", "l", "t", "r", "b"}`` 형태의 region 목록.
        """
        payload = json.dumps({"images": [base64.b64encode(image).decode("ascii")]}).encode("utf-8")
        req = urllib.request.Request(
            self.url.rstrip("/") + "/detect",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            result = json.loads(resp.read())
        return result["results"][0]

    @staticmethod
    def _match_category(bbox: Tuple[float, float, float, float], regions: List[dict]) -> str:
        """줄의 bbox 중심점을 포함하는 region 중 가장 작은 것의 카테고리를 고른다.

        Args:
            bbox: 줄의 ``(x0, y0, x1, y1)``.
            regions: :meth:`_detect`\ 가 반환한 region 목록(스케일 보정 완료).

        Returns:
            매칭되는 region이 없으면 ``"text"``, 있으면 :meth:`_to_category` 결과.
        """
        x0, y0, x1, y1 = bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        candidates = [r for r in regions if r["l"] <= cx <= r["r"] and r["t"] <= cy <= r["b"]]
        if not candidates:
            return "text"
        best = min(candidates, key=lambda r: (r["r"] - r["l"]) * (r["b"] - r["t"]))
        return DetrLayout._to_category(best["label"])

    @staticmethod
    def _to_category(label: str) -> str:
        """detr region label을 :data:`util.util.CATEGORIES` 값으로 정규화한다.

        Args:
            label: detr이 반환한 원본 label 문자열(예: ``"Section Header"``).

        Returns:
            ``CATEGORIES``\ 에 속하는 정규화된 카테고리, 없으면 ``"text"``.
        """
        key = label.lower().replace(" ", "_").replace("-", "_")
        return key if key in CATEGORIES else "text"
