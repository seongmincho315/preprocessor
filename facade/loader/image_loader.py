"""PIL(Pillow)로 이미지 파일 하나를 페이지 이미지 1장으로 취급하는 공통 베이스.
png/jpeg가 공유한다 - Pillow로 디코딩한 뒤에는 원본 포맷이 무의미해지기 때문이다.

lines를 항상 빈 리스트로 내서 ``BaseLoader._needs_ocr`` 이 빈 lines를 보고 자동으로
OCR을 트리거하게 한다. layout/ocr 전략은 강제하지 않고 config.yaml 그대로 쓴다 -
html과 달리 이미지는 실제 시각적/기하학적 내용이 있어 DETR/paddle이 정확히 설계
의도대로 맞는 케이스이기 때문이다.
"""

import io
from typing import Iterable, List, Optional, Tuple

from PIL import Image

from loader.base_loader import BaseLoader


class PillowImageLoader(BaseLoader):
    """이미지 파일을 페이지 이미지 1장으로 취급하는 공통 베이스 로더."""

    def _extract_pages(
        self, file_path: str
    ) -> Iterable[Tuple[List[Tuple[str, Tuple[float, float, float, float], float]], Optional[bytes]]]:
        """이미지를 열어 PNG bytes로 재인코딩한 뒤, 빈 lines와 함께 페이지 1개로 낸다.

        Args:
            file_path: 읽을 이미지 파일 경로.

        Yields:
            ``([], png_bytes)`` 튜플 하나.
        """
        with Image.open(file_path) as img:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            yield [], buf.getvalue(), None
