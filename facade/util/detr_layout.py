"""RT-DETR 기반 원격 레이아웃 서버(`detr` 레포 서빙)를 호출하는 layout 전략."""

import base64
import json
import urllib.request
from typing import List, Optional, Tuple

from util.util import CATEGORIES


class DetrLayout:
    """페이지 이미지를 detr 서버 `/detect`로 보내 감지된 region으로 각 줄의 category를 매긴다."""

    NEEDS_IMAGE = True

    def __init__(self, config: dict = None):
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
        x0, y0, x1, y1 = bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        candidates = [r for r in regions if r["l"] <= cx <= r["r"] and r["t"] <= cy <= r["b"]]
        if not candidates:
            return "text"
        best = min(candidates, key=lambda r: (r["r"] - r["l"]) * (r["b"] - r["t"]))
        return DetrLayout._to_category(best["label"])

    @staticmethod
    def _to_category(label: str) -> str:
        key = label.lower().replace(" ", "_").replace("-", "_")
        return key if key in CATEGORIES else "text"
