"""PaddleX OCR 서버(`paddle-ocr` 레포 서빙)를 호출하는 ocr 전략. 텍스트 레이어가 없는(스캔된) 페이지에서 쓴다."""

import base64
import json
import urllib.request
from typing import List, Tuple


class PaddleOcr:
    """페이지 이미지를 paddle-ocr 서버 `/ocr`로 보내 (text, bbox, font_size=0) 줄 목록을 얻는다."""

    def __init__(self, config: dict = None):
        config = config or {}
        self.url = config.get("url")
        if not self.url:
            raise ValueError("ocr.type=paddle을 쓰려면 paddle.yaml에 url을 설정해야 합니다.")
        self.timeout = config.get("timeout", 60)

    def __call__(self, image: bytes, dpi: float = 150) -> List[Tuple[str, Tuple[float, float, float, float], float]]:
        texts, scores, boxes = self._ocr(image)
        # rec_boxes는 image_dpi 기준 픽셀 좌표라, 나머지 줄 bbox(PDF 포인트, 72dpi 기준)와 스케일을 맞춘다.
        scale = dpi / 72.0
        n = min(len(texts), len(scores), len(boxes))
        return [
            (texts[i], (boxes[i][0] / scale, boxes[i][1] / scale, boxes[i][2] / scale, boxes[i][3] / scale), 0.0)
            for i in range(n)
        ]

    def _ocr(self, image: bytes) -> Tuple[List[str], List[float], List[List[float]]]:
        payload = json.dumps(
            {
                "file": base64.b64encode(image).decode("ascii"),
                "fileType": 1,
                "visualize": False,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.url.rstrip("/") + "/ocr",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            result = json.loads(resp.read())
        pruned = result["result"]["ocrResults"][0]["prunedResult"]
        return pruned.get("rec_texts", []), pruned.get("rec_scores", []), pruned.get("rec_boxes", [])
