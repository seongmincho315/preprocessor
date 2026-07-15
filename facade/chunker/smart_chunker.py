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
            그 섹션을 이룬 아이템들의 ``{page, bbox}`` 목록(뷰어에서 원문 위치
            강조에 씀)이다.
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
            # bbox도 페이지 범위와 동일한 근사치 원칙 — 쪼갠 조각들도 섹션 전체의
            # bbox 목록을 그대로 물려받는다(어느 조각이 어느 bbox인지까지는 안 나눔).
            bboxes = [{"page": item["page"], "bbox": item.get("bbox")} for item in section_items]

            if not self.chunk_size:
                chunks.append({"text": section_text, "i_page": i_page, "e_page": e_page, "bboxes": bboxes})
                continue

            chunks.extend(
                {"text": text, "i_page": i_page, "e_page": e_page, "bboxes": bboxes}
                for text in self._split_with_heading(heading, body_text, self.chunk_size, self.chunk_overlap)
            )

        return chunks

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

    @classmethod
    def _split_with_heading(cls, heading: Optional[str], body_text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """body_text를 chunk_size 기준으로 겹치게 자르고, 조각마다 heading을 다시 붙인다.

        Args:
            heading: 이 섹션의 헤딩 텍스트(없으면 ``None``).
            body_text: 헤딩을 제외한 본문 텍스트.
            chunk_size: 조각 하나의 최대 문자 수.
            chunk_overlap: 인접 조각끼리 겹치는 문자 수.

        Returns:
            헤딩이 다시 붙은 텍스트 조각 목록.
        """
        if not body_text:
            return [heading] if heading else []
        return [cls._render(heading, piece) for piece in cls._split_text(body_text, chunk_size, chunk_overlap)]
