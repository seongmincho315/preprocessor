"""tableformer(표 구조 인식) 서버(`tableformer` 레포 서빙)를 호출하는 클라이언트.

detr(`/detect`)와 대칭되는 계약을 따른다: 페이지 이미지 + 감지된 table region bbox(+ 페이지의
줄 단위 텍스트 토큰)를 `/structure`로 보내면, region마다 행/열 구조와 셀(텍스트/병합/헤더 여부)을
받는다. 응답 셀 스키마는 `tableformer` 레포가 그대로 넘기는 `docling_ibm_models`의
`tf_predictor.py::_merge_tf_output` 출력과 동일하다 (`bbox`, `row_span`/`col_span`,
`start_row_offset_idx`/`end_row_offset_idx`/`start_col_offset_idx`/`end_col_offset_idx`,
`column_header`/`row_header`/`row_section`, `text_cell_bboxes`: 매칭된 단어 토큰들의
``{"b","l","r","t","token"}`` 목록).
"""

import base64
import html
import json
import urllib.request
from typing import Dict, List, Optional, Tuple


class TableFormer:
    """페이지 이미지 + table region bbox + 텍스트 토큰을 tableformer 서버로 보내 표 구조를 얻는다."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: ``url``, ``timeout`` 을 담은 설정 dict(예: ``resource/tableformer.yaml`` 내용).

        Raises:
            ValueError: ``config`` 에 ``url`` 이 없을 때.
        """
        config = config or {}
        self.url = config.get("url")
        if not self.url:
            raise ValueError("table_structure.type=tableformer를 쓰려면 tableformer.yaml에 url을 설정해야 합니다.")
        self.timeout = config.get("timeout", 60)

    def structure(
        self,
        image: bytes,
        table_bboxes: List[Tuple[float, float, float, float]],
        tokens: List[Dict],
    ) -> List[dict]:
        """페이지 이미지 하나에 있는 table region들의 구조를 한 번에 요청한다.

        Args:
            image: 페이지 이미지(PNG bytes).
            table_bboxes: 이 페이지에서 감지된 table region bbox 목록, 각 ``(l, t, r, b)``
                픽셀 좌표(``image`` 와 같은 좌표계).
            tokens: 이 페이지의 줄 단위 토큰 ``{"id", "text", "bbox": [l, t, r, b]}`` 목록
                (표 밖 텍스트가 섞여 있어도 무방 - tableformer가 bbox 겹침으로 표별로 알아서
                매칭한다).

        Returns:
            ``table_bboxes`` 와 같은 순서의 ``{"num_rows", "num_cols", "otsl_seq", "cells"}`` 목록.
        """
        if not table_bboxes:
            return []
        payload = json.dumps(
            {
                "images": [base64.b64encode(image).decode("ascii")],
                "tables": [[list(b) for b in table_bboxes]],
                "tokens": [tokens],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.url.rstrip("/") + "/structure",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            result = json.loads(resp.read())
        return result["results"][0]

    @staticmethod
    def _index_cells(structure: dict) -> Tuple[int, int, Dict[Tuple[int, int], dict]]:
        """``cells`` 목록을 시작 위치 ``(row, col)`` -> 정리된 셀 dict로 인덱싱한다.

        각 셀의 텍스트는 그 칸에 매칭된 ``text_cell_bboxes`` 토큰들을 위→아래, 왼→오 순으로
        이어붙인 것이다.
        """
        num_rows = structure.get("num_rows", 0)
        num_cols = structure.get("num_cols", 0)
        cell_at: Dict[Tuple[int, int], dict] = {}
        for cell in structure.get("cells", []):
            r0, c0 = cell.get("start_row_offset_idx"), cell.get("start_col_offset_idx")
            if r0 is None or c0 is None or not (0 <= r0 < num_rows) or not (0 <= c0 < num_cols):
                continue
            tokens = sorted(cell.get("text_cell_bboxes") or [], key=lambda t: (t.get("t", 0), t.get("l", 0)))
            cell_at[(r0, c0)] = {
                "text": " ".join(t.get("token", "") for t in tokens if t.get("token")).strip(),
                "row_span": max(1, cell.get("row_span", 1) or 1),
                "col_span": max(1, cell.get("col_span", 1) or 1),
                "column_header": bool(cell.get("column_header")),
            }
        return num_rows, num_cols, cell_at

    @staticmethod
    def to_markdown(structure: dict) -> str:
        """tableformer ``/structure`` 응답 하나(표 1개)를 markdown 표 문자열로 렌더링한다.

        병합 셀(``row_span``/``col_span`` > 1)은 시작 칸에만 텍스트를 채우고 나머지 칸은
        비워둔다 - markdown 표 문법 자체가 셀 병합을 표현 못 하므로 빈 칸으로 근사한다
        (병합 정보를 그대로 보존하려면 :meth:`to_html` 을 쓸 것).
        """
        num_rows, num_cols, cell_at = TableFormer._index_cells(structure)
        if num_rows <= 0 or num_cols <= 0:
            return ""

        grid = [["" for _ in range(num_cols)] for _ in range(num_rows)]
        header_rows = set()
        for (r0, c0), cell in cell_at.items():
            grid[r0][c0] = cell["text"]
            if cell["column_header"]:
                header_rows.add(r0)

        # column_header로 표시된 셀이 하나도 없으면(단순 데이터 나열 등) 구분선을 억지로 넣지
        # 않는다 - 없는 헤더를 있는 것처럼 꾸미는 것보다 구분선 없는 텍스트가 낫다.
        header_idx = min(header_rows) if header_rows else None
        lines = []
        for r, row in enumerate(grid):
            lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |")
            if r == header_idx:
                lines.append("| " + " | ".join(["---"] * num_cols) + " |")
        return "\n".join(lines)

    @staticmethod
    def to_html(structure: dict) -> str:
        """tableformer ``/structure`` 응답 하나(표 1개)를 HTML ``<table>`` 로 렌더링한다.

        markdown과 달리 병합 셀을 ``rowspan``/``colspan`` 속성으로 그대로 보존한다 - doc_parser의
        ``chunking_processor.py::_extract_table_text`` 가 기본값(``export_to_html=1``)으로
        내보내는 것과 동등한 방식(같은 tableformer 출력을 렌더링만 다르게 함).
        """
        num_rows, num_cols, cell_at = TableFormer._index_cells(structure)
        if num_rows <= 0 or num_cols <= 0:
            return ""

        # 병합 셀이 덮는 칸은 시작 칸을 제외하고 별도 <td>를 내면 안 되므로 미리 표시해둔다.
        occupied = set()
        for (r0, c0), cell in cell_at.items():
            for dr in range(cell["row_span"]):
                for dc in range(cell["col_span"]):
                    if dr == 0 and dc == 0:
                        continue
                    occupied.add((r0 + dr, c0 + dc))

        rows_html = []
        for r in range(num_rows):
            cells_html = []
            for c in range(num_cols):
                if (r, c) in occupied:
                    continue
                cell = cell_at.get((r, c))
                if cell is None:
                    cells_html.append("<td></td>")
                    continue
                tag = "th" if cell["column_header"] else "td"
                attrs = ""
                if cell["row_span"] > 1:
                    attrs += f' rowspan="{cell["row_span"]}"'
                if cell["col_span"] > 1:
                    attrs += f' colspan="{cell["col_span"]}"'
                cells_html.append(f"<{tag}{attrs}>{html.escape(cell['text'])}</{tag}>")
            rows_html.append("<tr>" + "".join(cells_html) + "</tr>")
        return "<table>" + "".join(rows_html) + "</table>"
