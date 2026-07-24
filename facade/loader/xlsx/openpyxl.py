"""openpyxl 기반 XLSX 로더. ``ext.xlsx`` 가 ``openpyxl`` 일 때 쓰인다.

xlsx는 페이지 개념이 없는 표 네이티브 포맷이라, 워크북 전체를 문서 1페이지로
취급하고 시트마다 병합 해제 + 빈 행 기준 분할로 뽑아낸 표 블록을 category="table"
아이템 하나씩으로 담는다. bbox는 bs4.py와 같은 더미 값(0,0,0,0)을 쓴다 - 이
값이어야 reorder_by_category가 순서를 흐트러뜨리지 않는다(겹치는 영역이 전혀
없는 zero-area 박스라 그래프 간선이 하나도 안 생기기 때문).
"""

import openpyxl

from loader.base_loader import BaseLoader
from util.passthrough_layout import PassthroughLayout
from util.tabular import grid_to_table_items, unmerge_and_fill

DUMMY_BBOX = (0.0, 0.0, 0.0, 0.0)


class Loader(BaseLoader):
    """시트마다 표 블록을 뽑아 ``category="table"`` 아이템으로 담는다."""

    def get_layout(self):
        return PassthroughLayout(self.layout_config)

    def get_ocr(self):
        return None

    def _extract_pages(self, file_path: str):
        """워크북 전체를 페이지 1개로 취급해 (줄 목록, None) 쌍 하나만 낸다.

        Args:
            file_path: 읽을 xlsx 파일 경로.

        Yields:
            ``(lines, None)`` 튜플 하나. ``lines`` 는 시트마다의 표 블록을
            ``(html, DUMMY_BBOX, "table")`` 로 담은 목록.
        """
        wb = openpyxl.load_workbook(file_path, data_only=True)
        try:
            lines = []
            for ws in wb.worksheets:
                grid = unmerge_and_fill(ws)
                for html in grid_to_table_items(grid):
                    lines.append((html, DUMMY_BBOX, "table"))
            yield lines, None, None
        finally:
            wb.close()
