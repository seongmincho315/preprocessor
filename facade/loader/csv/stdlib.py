"""표준 라이브러리 csv 모듈 기반 CSV 로더. ``ext.csv`` 가 ``stdlib`` 일 때 쓰인다.

xlsx와 같은 표 블록 파이프라인(:mod:`util.tabular`)을 그대로 재사용한다 - 병합
셀 개념이 없다는 점만 다르므로 :func:`util.tabular.unmerge_and_fill` 은 건너뛰고
``csv.reader`` 결과를 바로 grid로 쓴다.
"""

import csv

from loader.base_loader import BaseLoader
from util.passthrough_layout import PassthroughLayout
from util.tabular import grid_to_table_items

DUMMY_BBOX = (0.0, 0.0, 0.0, 0.0)


class Loader(BaseLoader):
    """csv 전체를 표 블록 하나(또는 빈 행으로 나뉜 여러 개)로 뽑아 ``category="table"``
    아이템으로 담는다."""

    def get_layout(self):
        return PassthroughLayout(self.layout_config)

    def get_ocr(self):
        return None

    def _extract_pages(self, file_path: str):
        """csv 파일 전체를 페이지 1개로 취급해 (줄 목록, None) 쌍 하나만 낸다.

        Args:
            file_path: 읽을 csv 파일 경로.

        Yields:
            ``(lines, None)`` 튜플 하나.
        """
        with open(file_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        width = max((len(row) for row in rows), default=0)
        grid = [row + [""] * (width - len(row)) for row in rows]
        lines = [(html, DUMMY_BBOX, "table") for html in grid_to_table_items(grid)]
        yield lines, None, None
