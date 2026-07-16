"""줄바꿈으로 잘린 문단을 이어붙인다(페이지 안이든, 페이지 경계든).

docling-ibm-models(``docling_ibm_models.reading_order.reading_order_rb``)의
``predict_merges``/``docling.models.page_assemble_model.PageAssembleModel
.sanitize_text`` 두 함수를 그대로 옮겼다:

- 병합 여부 판단은 ``predict_merges``\\ 의 정규식 그대로다 - 이전 요소가
  (공백 제외) 소문자/쉼표/하이픈으로 끝나고, 다음 요소가 소문자로 시작하면
  이어지는 문장으로 본다. 실제 소스를 보면 이 조건에 페이지가 같은지
  다른지는 관여하지 않는다(``elem.page_no != next.label`` 비교라 상수 조건과
  같아 사실상 항상 참이 되는 부분이 있다) - 그래서 우리도 페이지 경계
  여부를 조건에 넣지 않는다.
- 실제로 이어붙이는 방식은 ``sanitize_text``\\ 를 그대로 따른다: 하이픈으로
  끝나면서 하이픈 앞/뒤 단어가 모두 영숫자일 때만 하이픈을 지우고 붙이고,
  그 외에는 공백으로 이어붙인다.
"""

import re
from typing import List

#: 재정렬 대상과 같은 본문 흐름 카테고리만 이어붙인다 - formula/table/caption
#: 등은 문장이 이어진다고 보기 어렵다.
MERGEABLE_CATEGORIES = {"text"}

#: docling_ibm_models.reading_order.reading_order_rb.ReadingOrderPredictor.predict_merges의 m1/m2 그대로.
_ENDS_MID_SENTENCE_RE = re.compile(r".+([a-z,\-])(\s*)")
_STARTS_MID_SENTENCE_RE = re.compile(r"(\s*[a-z])(.+)")
#: docling.models.page_assemble_model.PageAssembleModel.sanitize_text에서 쓰는 단어 경계 정규식.
_WORD_RE = re.compile(r"\b[\w]+\b")


def merge_split_paragraphs(items: List[dict]) -> List[dict]:
    """줄바꿈으로 잘린 문단을 이어붙인다.

    Args:
        items: ``{text, category, bbox, page}`` 아이템 목록(한 파일 전체).
            헤더/푸터 제거가 먼저 적용돼서, 잘린 문단의 앞/뒤 아이템이 목록에서
            바로 이웃해 있어야 한다.

    Returns:
        이어붙인 아이템을 하나로 합친 목록. 합쳐진 아이템은 앞쪽 아이템의
        ``category``/``bbox``/``page``\\ 를 그대로 쓰고 ``text``\\ 만 이어붙인다.
    """
    if not items:
        return items

    merged = [dict(items[0])]
    for item in items[1:]:
        prev = merged[-1]
        if (
            prev["category"] in MERGEABLE_CATEGORIES
            and item["category"] in MERGEABLE_CATEGORIES
            and _ENDS_MID_SENTENCE_RE.fullmatch(prev["text"])
            and _STARTS_MID_SENTENCE_RE.fullmatch(item["text"])
        ):
            prev["text"] = _join(prev["text"], item["text"])
            continue
        merged.append(dict(item))

    return merged


def _join(prev_text: str, next_text: str) -> str:
    """docling의 ``sanitize_text`` 그대로: 하이픈으로 끝나면서 하이픈 앞/뒤 단어가
    모두 영숫자일 때만 하이픈을 지우고 바로 붙인다. 하이픈으로 끝나지 않으면
    공백으로 이어붙인다. 하이픈으로 끝났는데 영숫자 조건을 못 채우면(예: 밑줄만
    있는 "토큰-") 원본처럼 공백 없이 그대로 붙인다 - docling 원본이 이 경우
    분기를 안 타서(else가 hyphen 분기와 배타적) 공백을 안 넣는 특이 동작을
    그대로 재현한 것."""
    if prev_text.endswith("-"):
        prev_words = _WORD_RE.findall(prev_text)
        next_words = _WORD_RE.findall(next_text)
        if prev_words and next_words and prev_words[-1].isalnum() and next_words[0].isalnum():
            return prev_text[:-1] + next_text
        return prev_text + next_text
    return prev_text + " " + next_text
