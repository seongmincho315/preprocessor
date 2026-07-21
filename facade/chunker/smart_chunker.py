"""section_header 경계 기준 청커. ``config.yaml`` 의 ``chunker.type: smart_chunker`` 로 선택된다."""

from typing import List, Optional, Tuple

from chunker.base_chunker import BaseChunker


class Chunker(BaseChunker):
    """section_header 경계로 섹션을 나누고 각 섹션 앞에 헤딩을 붙인 뒤,
    chunk_size(문자 수)를 넘으면 겹치게 분할한다. chunk_size가 0/None이면 섹션을 통째로 반환한다.
    (doc_parser 레포 GenosSmartChunker의 '헤딩 유지 + 섹션 기준 분할' 아이디어를 문자 기반으로 단순화)"""

    def __call__(self, items: List[dict]) -> List[dict]:
        """아이템 목록을 섹션 단위로 묶고 필요시 분할해 청크 목록으로 반환한다.

        Args:
            items: 로더가 반환한 ``{text, category, bbox, page}`` 아이템 목록.

        Returns:
            ``{text, i_page, e_page, bboxes}`` 청크 목록. ``i_page``/``e_page`` 는
            그 청크가 속한 섹션(헤딩+본문)이 걸쳐 있는 페이지 범위, ``bboxes`` 는
            그 청크의 텍스트에 실제로 포함된 아이템들의 ``{page, bbox, category}``
            목록(뷰어에서 원문 위치 강조에 씀)이다. chunk_size로 섹션을 여러 조각으로
            쪼갠 경우, 각 조각은 자기 텍스트 범위에 걸친 아이템의 bbox만 갖는다
            (헤딩 아이템의 bbox는 모든 조각에 공통으로 들어간다 - 각 조각 텍스트
            앞에 헤딩이 다시 붙기 때문).
        """
        chunks = []
        for heading_item, body_items in self._group_by_section(items):
            heading = heading_item["text"] if heading_item else None
            body_text = "\n".join(item["text"] for item in body_items)
            section_text = self._render(heading, body_text)
            if not section_text:
                continue

            section_items = ([heading_item] if heading_item else []) + body_items
            # 섹션(헤딩+본문 전체)이 걸쳐 있는 페이지 범위. chunk_size로 쪼갠 조각들도
            # 정확한 글자 단위 페이지 추적 대신 이 섹션 범위를 그대로 물려받는다(근사치).
            pages = [item["page"] for item in section_items]
            i_page, e_page = min(pages), max(pages)

            heading_bboxes = [self._to_bbox_entry(heading_item)] if heading_item else []

            if not self.chunk_size:
                bboxes = heading_bboxes + [self._to_bbox_entry(item) for item in body_items]
                chunks.append({"text": section_text, "i_page": i_page, "e_page": e_page, "bboxes": bboxes})
                continue

            if not body_text:
                # 헤딩만 있고 본문이 없는 섹션 - _split_ranges(0, ...)는 빈 목록이라 아래
                # 루프를 그냥 타면 이 헤딩이 통째로 사라지므로 따로 처리한다.
                chunks.append({"text": section_text, "i_page": i_page, "e_page": e_page, "bboxes": heading_bboxes})
                continue

            spans = self._char_spans(body_items)
            for start, end in self._split_ranges(len(body_text), self.chunk_size, self.chunk_overlap):
                piece = body_text[start:end]
                piece_items = [item for s, e, item in spans if s < end and e > start]
                bboxes = heading_bboxes + [self._to_bbox_entry(item) for item in piece_items]
                chunks.append(
                    {"text": self._render(heading, piece), "i_page": i_page, "e_page": e_page, "bboxes": bboxes}
                )

        return chunks

    @staticmethod
    def _to_bbox_entry(item: dict) -> dict:
        return {"page": item["page"], "bbox": item.get("bbox"), "category": item.get("category")}

    @staticmethod
    def _char_spans(body_items: List[dict]) -> List[Tuple[int, int, dict]]:
        """``"\\n".join(item["text"] for item in body_items)`` 안에서 각 아이템 텍스트가
        차지하는 ``(start, end, item)`` 범위 목록을 반환한다(``\\n`` 구분자 1글자 포함)."""
        spans = []
        pos = 0
        for item in body_items:
            start = pos
            end = start + len(item["text"])
            spans.append((start, end, item))
            pos = end + 1
        return spans

    @staticmethod
    def _group_by_section(items: List[dict]) -> List[Tuple[Optional[dict], List[dict]]]:
        """category가 section_header인 아이템을 기준으로 (heading_item, body_items) 목록을 만든다.

        Args:
            items: 원본 아이템 목록.

        Returns:
            ``(heading_item, body_items)`` 튜플 목록. ``heading_item`` 은 헤딩
            아이템 자체(``text``/``page``/``bbox`` 포함)이고, 첫 section_header
            이전에 나온 아이템은 ``heading_item=None`` 인 섹션으로 묶인다.
        """
        sections = []
        heading_item, body = None, []
        for item in items:
            if item.get("category") == "section_header":
                if heading_item is not None or body:
                    sections.append((heading_item, body))
                heading_item, body = item, []
            else:
                body.append(item)
        if heading_item is not None or body:
            sections.append((heading_item, body))
        return sections
