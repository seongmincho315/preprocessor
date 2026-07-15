"""다단(2단/3단) 레이아웃에서 실제로 읽는 순서로 줄을 재정렬하는 규칙 기반 알고리즘.

docling이 쓰는 ``docling-ibm-models``의 reading-order 알고리즘(공간 인덱스로 위/아래
관계를 그래프로 만들고 DFS로 순서를 뽑는 방식)의 핵심 아이디어를, rtree/docling_core
같은 무거운 서드파티 없이 우리 ``(text, bbox, font_size)`` 튜플에 맞게 옮겼다.
캡션/각주 연결, 페이지 간 문장 병합, 좌우 폭 보정(dilation)처럼 이 프로젝트에 당장
필요 없는 부분은 뺐다 - 필요해지면 그때 추가한다.

PyMuPDF는 수식 한 줄(예: ``E f(X) = ∫ f(x) dpX(x)``)을 적분 기호/수식 번호 같은
여러 개의 잘게 쪼개진 "line"으로 주는데, 이 조각들은 서로 다른 칼럼처럼 보이는
bbox를 가져서 기하학적 재정렬 대상에 넣으면 오히려 순서가 망가진다(원래 콘텐츠
스트림 순서가 이미 맞는데도). 그래서 :func:`reorder_by_category`\\ 로 레이아웃이
매긴 카테고리 중 본문 흐름(:data:`FLOW_CATEGORIES`)에 속하는 줄만 재정렬하고,
formula/table/picture/page_header/page_footer 같은 나머지는 원래 순서 그대로
"바로 앞에 있던 본문 줄" 뒤에 붙여서 재정렬 대상에서 제외한다.
"""

from typing import List, Sequence, Tuple

Line = Tuple[str, Tuple[float, float, float, float], float]
Box = Tuple[float, float, float, float]

#: 이 줄 수를 넘는 페이지는 O(n^3) 비교가 너무 비싸져서 원래 순서를 그대로 반환한다.
MAX_LINES_FOR_REORDER = 500

#: 여러 줄에 걸쳐 자연스럽게 이어지는 본문 흐름 카테고리만 재정렬 대상으로 삼는다.
#: formula/table/picture/page_header/page_footer/caption/footnote/chart/code 등은
#: 원래 콘텐츠 스트림 순서가 이미 맞고(수식이 특히 그렇다), 기하학적으로 재정렬하면
#: 오히려 깨지기 쉬워서 뺐다 - :mod:`util.util`\\ 의 ``CATEGORIES`` 참고.
FLOW_CATEGORIES = {"text", "section_header", "title", "list_item"}


def reorder_by_category(
    lines: List[Line], categories: Sequence[str], flow_categories=FLOW_CATEGORIES
) -> Tuple[List[Line], List[str]]:
    """레이아웃이 카테고리를 매긴 뒤, 본문 흐름 줄만 읽는 순서로 재정렬한다.

    ``flow_categories``\\ 에 속하지 않는 줄(formula/table/page_header 등)은 원래
    상대 순서를 유지한 채, 재정렬 뒤에도 "원래 자기 바로 앞에 있던 본문 흐름 줄"의
    새 위치 뒤에 그대로 붙는다. 그 앞에 본문 흐름 줄이 아예 없었다면 맨 앞에 온다.

    Args:
        lines: ``(text, bbox, font_size)`` 튜플 목록.
        categories: ``lines``\\ 와 같은 길이의 카테고리 문자열 목록.
        flow_categories: 재정렬 대상으로 삼을 카테고리 집합(기본 :data:`FLOW_CATEGORIES`).

    Returns:
        ``(재정렬된 lines, 그에 맞춰 같이 재배열된 categories)`` 튜플.
    """
    n = len(lines)
    flow_indices = [i for i in range(n) if categories[i] in flow_categories]
    if len(flow_indices) < 2:
        return list(lines), list(categories)

    local_order = sort_indices([lines[i][1] for i in flow_indices])
    reordered_flow_indices = [flow_indices[k] for k in local_order]

    flow_set = set(flow_indices)
    pinned_after: dict = {}
    last_flow_seen = None
    for i in range(n):
        if i in flow_set:
            last_flow_seen = i
            continue
        pinned_after.setdefault(last_flow_seen, []).append(i)

    order = list(pinned_after.get(None, []))
    for i in reordered_flow_indices:
        order.append(i)
        order.extend(pinned_after.get(i, []))

    return [lines[i] for i in order], [categories[i] for i in order]


def sort_reading_order(lines: List[Line]) -> List[Line]:
    """페이지의 (text, bbox, font_size) 줄 목록을 기하학적 위치 기준으로 재정렬한다.

    "같은 칼럼(가로로 겹침)에서 바로 위에 있는 줄"을 그래프로 연결하고(단, 그
    사이에 다른 줄이 끼어 있으면 직접 연결하지 않는다 - 이래야 옆 칼럼 텍스트를
    건너뛰어 잘못 이어붙이지 않는다), 이 그래프를 위상 정렬(topological sort)해서
    순서를 뽑는다. 위쪽 예선이 없는 줄(칼럼 시작점)부터, 다음 줄이 준비되는 즉시
    그 칼럼을 끝까지 파고드는 식으로 처리되기 때문에, 여러 칼럼이 있어도 왼쪽
    칼럼을 끝까지 읽은 뒤 오른쪽 칼럼으로 넘어가는 순서가 나온다.

    단일 칼럼 문서에서는 원래 순서(PyMuPDF가 준 순서)와 결과가 같다. 수식처럼
    잘게 쪼개진 줄까지 뒤섞을 위험이 있으니, 로더에서 직접 쓰지 말고
    :func:`reorder_by_category`\\ 를 통해서만 쓴다.

    Args:
        lines: 재정렬할 ``(text, (x0, y0, x1, y1), font_size)`` 튜플 목록.

    Returns:
        같은 튜플들을 읽는 순서로 재배열한 목록. 줄이 1개 이하이거나
        :data:`MAX_LINES_FOR_REORDER`\\ 를 넘으면 입력을 그대로 반환한다.
    """
    order = sort_indices([line[1] for line in lines])
    return [lines[i] for i in order]


def sort_indices(boxes: List[Box]) -> List[int]:
    """bbox 목록을 기하학적 위치 기준으로 읽는 순서로 정렬한, 원래 인덱스 목록을 낸다.

    Args:
        boxes: ``(x0, y0, x1, y1)`` bbox 목록.

    Returns:
        읽는 순서대로 나열한 ``range(len(boxes))`` 의 순열. bbox가 1개 이하이거나
        :data:`MAX_LINES_FOR_REORDER`\\ 를 넘으면 원래 순서(``[0, 1, ..., n-1]``)를
        그대로 반환한다.
    """
    n = len(boxes)
    if n <= 1 or n > MAX_LINES_FOR_REORDER:
        return list(range(n))

    up, down = _build_graph(boxes)

    # 스택(LIFO)은 pop()이 "위쪽/왼쪽부터, 동률이면 원래 순서대로" 나오도록 담아야
    # 하므로, (y, x, 원래 인덱스) 내림차순으로 쌓는다 - 그래야 가장 작은 값이
    # 스택 맨 끝에 남아 제일 먼저 꺼내진다.
    def sort_key(i):
        return (boxes[i][1], boxes[i][0], i)

    indegree = [len(up[i]) for i in range(n)]
    stack = sorted((i for i in range(n) if indegree[i] == 0), key=sort_key, reverse=True)

    order = []
    while stack:
        i = stack.pop()
        order.append(i)
        for c in sorted(down[i], key=sort_key, reverse=True):
            indegree[c] -= 1
            if indegree[c] == 0:
                stack.append(c)

    return order


def _build_graph(boxes: List[Tuple[float, float, float, float]]):
    """"바로 위 칼럼 줄 -> 이 줄" 관계를 위(up)/아래(down) 인접 리스트로 만든다."""
    n = len(boxes)
    up = [[] for _ in range(n)]
    down = [[] for _ in range(n)]

    for j in range(n):
        for i in range(n):
            if i == j or not _is_above(boxes[i], boxes[j]) or not _overlaps_horizontally(boxes[i], boxes[j]):
                continue
            if any(_is_between(boxes[i], boxes[j], boxes[k]) for k in range(n) if k != i and k != j):
                continue
            up[j].append(i)
            down[i].append(j)

    return up, down


def _overlaps_horizontally(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2]


def _is_above(a, b) -> bool:
    """a가 b보다 위(작은 y)에 있고 서로 겹치지 않는지. bbox는 top-left origin 기준
    ``(x0, y0, x1, y1)``\\ 라 y가 클수록 페이지 아래쪽이다."""
    return a[3] <= b[1]


def _is_between(above, below, c) -> bool:
    """``above``\\ 와 ``below``\\ 사이(수직으로)에 ``c``\\ 가 끼어 있고, 둘 중 하나와
    가로로 겹치는지. 그렇다면 ``above -> below``\\ 직접 연결을 막아야 한다(``c``\\ 를
    건너뛰고 잘못 이어붙이게 되므로)."""
    if not (above[3] <= c[1] and c[3] <= below[1]):
        return False
    return _overlaps_horizontally(above, c) or _overlaps_horizontally(below, c)
