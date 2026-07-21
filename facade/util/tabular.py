"""csv/xlsx/md의 표 블록이 공유하는 그리드 처리 로직.

doc_parser의 xlsx tabular 처리(``genon/preprocessor/converters/xlsx_processor.py``)
중 핵심만 옮겼다: 병합 셀 forward-fill, 빈 행 기준 표 블록 분리, 단일 레벨 헤더
감지. 계층형 그룹 헤더 flatten(``2024_매출`` 식)이나 열 방향 다중 표 분리처럼
doc_parser에만 있는 고급 기능은 의도적으로 스코프에서 뺐다 - 동작하는 포팅부터
하고, 모든 edge case를 쫓지 않는다.
"""

from html import escape
from typing import List, Optional, Tuple

Grid = List[List[str]]


def unmerge_and_fill(ws) -> Grid:
    """openpyxl 워크시트 전체를 2D grid로 뽑되, 병합된 범위는 좌상단 값을 범위
    전체에 forward-fill한다(제목 병합/헤더 병합/데이터 병합을 구분하지 않고
    전부 동일하게 처리한다).

    Args:
        ws: ``openpyxl`` 워크시트.

    Returns:
        문자열 grid(빈 셀은 ``""``).
    """
    grid: Grid = [
        ["" if cell is None else str(cell) for cell in row] for row in ws.iter_rows(values_only=True)
    ]
    for merged_range in ws.merged_cells.ranges:
        top_left = ws.cell(merged_range.min_row, merged_range.min_col).value
        value = "" if top_left is None else str(top_left)
        for row in range(merged_range.min_row, merged_range.max_row + 1):
            for col in range(merged_range.min_col, merged_range.max_col + 1):
                if row - 1 < len(grid) and col - 1 < len(grid[row - 1]):
                    grid[row - 1][col - 1] = value
    return grid


def split_blank_row_blocks(grid: Grid) -> List[Grid]:
    """완전히 빈 행이 연속되는 지점을 경계로 grid를 여러 표 블록으로 나눈다.

    한 시트 안에 열 방향으로 나란히 놓인 별개 표(빈 행이 아니라 빈 열로 구분되는
    경우)는 이 함수로는 분리되지 않는다 - 이번 포팅 범위 밖.

    Args:
        grid: 전체 시트/파일의 grid.

    Returns:
        빈 블록을 뺀 grid 목록.
    """
    blocks: List[Grid] = []
    current: Grid = []
    for row in grid:
        if any(cell.strip() for cell in row):
            current.append(row)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def detect_caption_header_body(rows: Grid) -> Tuple[Optional[str], List[str], Grid]:
    """블록의 첫 행이 전체 병합 타이틀(모든 non-empty 셀이 같은 값)이면 caption으로
    분리하고 그 다음 행을 header로 쓴다. 그렇지 않으면 첫 행 자체가 header다(csv는
    항상 이 경로).

    Args:
        rows: 표 블록 grid(빈 행 없음).

    Returns:
        ``(caption, header, body)`` 튜플. ``caption`` 은 없으면 ``None``.
    """
    first = rows[0]
    non_empty = {cell for cell in first if cell.strip()}
    if len(non_empty) == 1 and len(rows) > 1:
        return non_empty.pop(), rows[1], rows[2:]
    return None, first, rows[1:]


def rows_to_html_table(header: List[str], body: Grid, caption: Optional[str] = None) -> str:
    """header/body/caption으로 ``<table>`` HTML 문자열을 만든다.

    병합된 셀은 이미 forward-fill로 반복 텍스트가 들어있다는 전제라, colspan/rowspan
    계산은 하지 않는다.

    Args:
        header: 열 이름 목록.
        body: 데이터 행 목록.
        caption: 표 제목(있으면 ``<caption>``).

    Returns:
        ``<table>`` HTML 문자열.
    """
    parts = ["<table>"]
    if caption:
        parts.append(f"<caption>{escape(caption)}</caption>")
    parts.append("<thead><tr>" + "".join(f"<th>{escape(cell)}</th>" for cell in header) + "</tr></thead>")
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in body
    )
    parts.append(f"<tbody>{body_rows}</tbody>")
    parts.append("</table>")
    return "".join(parts)


def grid_to_table_items(grid: Grid) -> List[str]:
    """grid 하나에서 ``split_blank_row_blocks`` -> ``detect_caption_header_body`` ->
    ``rows_to_html_table`` 순서로 묶어, HTML 표 문자열 목록을 낸다.

    Args:
        grid: 전체 시트/파일의 grid.

    Returns:
        표 블록마다 하나씩인 HTML 문자열 목록(빈 grid면 빈 목록).
    """
    items = []
    for block in split_blank_row_blocks(grid):
        caption, header, body = detect_caption_header_body(block)
        items.append(rows_to_html_table(header, body, caption))
    return items
