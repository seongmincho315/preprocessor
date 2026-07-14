"""PaddleX OCR 서버(`paddle-ocr` 레포 서빙)를 호출하는 ocr 전략. 텍스트 레이어가 없는(스캔된) 페이지에서 쓴다."""

import base64
import json
import urllib.request
from typing import List, Tuple


class PaddleOcr:
    """페이지 이미지를 paddle-ocr 서버 `/ocr`\ 로 보내 (text, bbox, font_size=0) 줄 목록을 얻는다.

    Attributes:
        url (str): paddle-ocr 서버 base URL.
        timeout (int): HTTP 요청 타임아웃(초).
    """

    def __init__(self, config: dict = None):
        """
        Args:
            config: ``url``, ``timeout``\ 을 담은 설정 dict(예: ``resource/paddle.yaml`` 내용).

        Raises:
            ValueError: ``config``\ 에 ``url``\ 이 없을 때.
        """
        config = config or {}
        self.url = config.get("url")
        if not self.url:
            raise ValueError("ocr.type=paddle을 쓰려면 paddle.yaml에 url을 설정해야 합니다.")
        self.timeout = config.get("timeout", 60)

    def __call__(self, image: bytes, dpi: float = 150) -> List[Tuple[str, Tuple[float, float, float, float], float]]:
        """페이지 이미지를 OCR해 텍스트 줄 목록으로 반환한다.

        Args:
            image: 페이지 이미지(PNG bytes).
            dpi: ``image``\ 를 렌더링한 DPI. bbox를 72dpi(PDF 포인트) 기준으로
                스케일 보정하는 데 쓰인다.

        Returns:
            ``(text, (x0, y0, x1, y1), 0.0)`` 튜플 목록. font_size는 OCR 결과에
            없으므로 항상 ``0.0``\ 이다.
        """
        texts, scores, boxes = self._ocr(image)
        # rec_boxes는 image_dpi 기준 픽셀 좌표라, 나머지 줄 bbox(PDF 포인트, 72dpi 기준)와 스케일을 맞춘다.
        scale = dpi / 72.0
        n = min(len(texts), len(scores), len(boxes))
        return [
            (texts[i], (boxes[i][0] / scale, boxes[i][1] / scale, boxes[i][2] / scale, boxes[i][3] / scale), 0.0)
            for i in range(n)
        ]

    def _ocr(self, image: bytes) -> Tuple[List[str], List[float], List[List[float]]]:
        """paddle-ocr 서버 ``/ocr``\ 을 호출해 원시 인식 결과를 받는다.

        Args:
            image: 페이지 이미지(PNG bytes).

        Returns:
            ``(rec_texts, rec_scores, rec_boxes)`` — 인식된 텍스트, 신뢰도,
            픽셀 좌표 bbox 목록. 응답에 없으면 빈 리스트.
        """
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
