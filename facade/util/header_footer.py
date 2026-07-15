"""여러 페이지에 걸쳐 상단/하단에 반복되는 줄(머리말/꼬리말)을 걸러낸다.

로고, 문서 제목, 페이지 번호처럼 페이지마다 반복되는 텍스트는 청크 내용에 실질적인
정보를 주지 않으면서 잡음만 늘린다. 페이지 수가 충분하고, 어떤 텍스트가 페이지
상단/하단 근처에서 대부분의 페이지에 반복되면 머리말/꼬리말로 보고 제거한다.
"""

import re
from collections import Counter, defaultdict
from typing import List

#: 페이지 수가 이보다 적으면 "반복"이라는 판단 자체가 통계적으로 의미가 없다.
MIN_PAGES = 3
#: 페이지 콘텐츠 높이(그 페이지 안 bbox의 최소~최대 y) 대비 이 비율 안에 있으면
#: 상단/하단 밴드로 본다.
EDGE_BAND_RATIO = 0.1
#: 전체 페이지 중 이 비율 이상에서 반복되면 머리말/꼬리말로 판단한다.
REPEAT_RATIO = 0.6

#: "Page 3", "3 of 10", "- 3 -"처럼 페이지 번호만 있는 줄. 숫자 자체는 페이지마다
#: 다르지만 같은 꼬리말로 취급해야 하므로 별도로 잡는다. "Chapter 3"처럼 숫자
#: 앞에 다른 단어가 붙은 실제 제목까지 뭉개지 않도록, 이 패턴에 매칭되는 줄만
#: 예외로 다룬다.
_PAGE_NUMBER_RE = re.compile(r"^[\-\s]*(page\s*)?\d+(\s*(of|/)\s*\d+)?[\-\s]*$", re.IGNORECASE)


def strip_repeated_headers_footers(items: List[dict]) -> List[dict]:
    """여러 페이지에서 상단/하단에 반복되는 줄(머리말/꼬리말)을 제거한다.

    Args:
        items: ``{text, category, bbox, page}`` 아이템 목록(한 파일 전체, 여러 페이지).

    Returns:
        머리말/꼬리말로 판단된 아이템을 뺀 목록. 페이지 수가 :data:`MIN_PAGES`\\ 보다
        적으면(예: html처럼 항상 1페이지) 판단할 근거가 부족해 입력을 그대로 반환한다.
    """
    pages = defaultdict(list)
    for item in items:
        pages[item["page"]].append(item)

    if len(pages) < MIN_PAGES:
        return items

    header_counts = Counter()
    footer_counts = Counter()
    for page_items in pages.values():
        if not page_items:
            continue
        top = min(it["bbox"]["y0"] for it in page_items)
        bottom = max(it["bbox"]["y1"] for it in page_items)
        band = max(bottom - top, 1.0) * EDGE_BAND_RATIO

        seen_on_page = set()
        for it in page_items:
            key = _normalize(it["text"])
            if not key or key in seen_on_page:
                continue
            if it["bbox"]["y1"] <= top + band:
                header_counts[key] += 1
            elif it["bbox"]["y0"] >= bottom - band:
                footer_counts[key] += 1
            else:
                continue
            seen_on_page.add(key)

    threshold = max(2, round(len(pages) * REPEAT_RATIO))
    repeated = {key for key, count in header_counts.items() if count >= threshold}
    repeated |= {key for key, count in footer_counts.items() if count >= threshold}
    if not repeated:
        return items

    return [item for item in items if _normalize(item["text"]) not in repeated]


def _normalize(text: str) -> str:
    """반복 여부를 비교할 키를 만든다. 페이지 번호 패턴(:data:`_PAGE_NUMBER_RE`)이면
    숫자가 달라도 같은 꼬리말로 묶고, 그 외에는 원문 그대로 써서 "Chapter 3"처럼
    숫자가 들어간 실제(페이지마다 다른) 제목을 잘못 지우지 않는다."""
    text = text.strip()
    if _PAGE_NUMBER_RE.match(text):
        return "\0page-number\0"
    return text
