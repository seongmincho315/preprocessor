from typing import List, Optional, Tuple


class Chunker:
    """section_header 경계로 섹션을 나누고 각 섹션 앞에 헤딩을 붙인 뒤,
    chunk_size(문자 수)를 넘으면 겹치게 분할한다. chunk_size가 0/None이면 섹션을 통째로 반환한다.
    (doc_parser 레포 GenosSmartChunker의 '헤딩 유지 + 섹션 기준 분할' 아이디어를 문자 기반으로 단순화)"""

    def __init__(self, chunk_size: int = 0, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def __call__(self, items: List[dict]) -> List[str]:
        chunks = []
        for heading, body_items in self._group_by_section(items):
            body_text = "\n".join(item["text"] for item in body_items)
            section_text = ", ".join(t for t in (heading, body_text) if t)
            if not section_text:
                continue

            if not self.chunk_size:
                chunks.append(section_text)
                continue

            chunks.extend(self._split_with_heading(heading, body_text, self.chunk_size, self.chunk_overlap))

        return chunks

    @staticmethod
    def _group_by_section(items: List[dict]) -> List[Tuple[Optional[str], List[dict]]]:
        """category가 section_header인 아이템을 기준으로 (heading, body_items) 목록을 만든다."""
        sections = []
        heading, body = None, []
        for item in items:
            if item.get("category") == "section_header":
                if heading is not None or body:
                    sections.append((heading, body))
                heading, body = item["text"], []
            else:
                body.append(item)
        if heading is not None or body:
            sections.append((heading, body))
        return sections

    @staticmethod
    def _split_with_heading(heading: Optional[str], body_text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """body_text를 chunk_size 기준으로 겹치게 자르고, 조각마다 heading을 다시 붙인다."""
        if not body_text:
            return [heading] if heading else []

        pieces = []
        start = 0
        while start < len(body_text):
            end = start + chunk_size
            pieces.append(body_text[start:end])
            start = end - chunk_overlap if end < len(body_text) else end

        return [", ".join(t for t in (heading, piece) if t) for piece in pieces]
