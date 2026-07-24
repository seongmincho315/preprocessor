"""정규식 기반 경량 마크다운 구조 파서. ``ext.md`` 가 ``regex`` 일 때 쓰인다.

doc_parser의 실제 marko 기반 md_backend.py는 라이브 경로에서 죽은 코드이고(실사용은
평문 TextLoader), 헤딩/리스트/표/코드 블록만 구분하는 이 수준의 파서도 이미
doc_parser의 실제 동작보다 낫다. marko 등 신규 의존성은 추가하지 않는다.
"""

import re

from loader.base_loader import BaseLoader
from util.passthrough_layout import PassthroughLayout
from util.tabular import rows_to_html_table

DUMMY_BBOX = (0.0, 0.0, 0.0, 0.0)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_ITEM_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+(.*)$")
_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?$")


class Loader(BaseLoader):
    """헤딩/리스트/표/코드 블록만 구분하는 경량 마크다운 파서."""

    def get_layout(self):
        return PassthroughLayout(self.layout_config)

    def get_ocr(self):
        return None

    def _extract_pages(self, file_path: str):
        """문서 전체를 페이지 1개로 취급해 (줄 목록, None) 쌍 하나만 낸다.

        Args:
            file_path: 읽을 markdown 파일 경로.

        Yields:
            ``(lines, None)`` 튜플 하나.
        """
        with open(file_path, encoding="utf-8") as f:
            raw_lines = f.read().splitlines()
        yield self._parse(raw_lines), None, None

    @classmethod
    def _parse(cls, raw_lines):
        lines = []
        i, n = 0, len(raw_lines)
        while i < n:
            stripped = raw_lines[i].strip()
            if not stripped:
                i += 1
                continue
            if stripped.startswith("```"):
                block, i = cls._consume_code_block(raw_lines, i)
                lines.append((block, DUMMY_BBOX, "code"))
                continue
            heading = _HEADING_RE.match(stripped)
            if heading:
                lines.append((heading.group(2).strip(), DUMMY_BBOX, "section_header"))
                i += 1
                continue
            if stripped.startswith("|"):
                html, i = cls._consume_table(raw_lines, i)
                lines.append((html, DUMMY_BBOX, "table"))
                continue
            list_item = _LIST_ITEM_RE.match(stripped)
            if list_item:
                lines.append((list_item.group(1).strip(), DUMMY_BBOX, "list_item"))
                i += 1
                continue
            lines.append((stripped, DUMMY_BBOX, "text"))
            i += 1
        return lines

    @staticmethod
    def _consume_code_block(raw_lines, start):
        body = []
        i = start + 1
        while i < len(raw_lines) and not raw_lines[i].strip().startswith("```"):
            body.append(raw_lines[i])
            i += 1
        return "\n".join(body), min(i + 1, len(raw_lines))

    @staticmethod
    def _split_row(line: str):
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    @classmethod
    def _consume_table(cls, raw_lines, start):
        header = cls._split_row(raw_lines[start])
        i = start + 1
        if i < len(raw_lines) and _TABLE_SEP_RE.match(raw_lines[i].strip()):
            i += 1
        body = []
        while i < len(raw_lines) and raw_lines[i].strip().startswith("|"):
            body.append(cls._split_row(raw_lines[i]))
            i += 1
        return rows_to_html_table(header, body), i
