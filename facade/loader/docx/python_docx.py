"""python-docx 기반 DOCX 로더. ``ext.docx`` 가 ``python_docx`` 일 때 쓰인다.

``document.element.body`` 를 원본 XML 순서 그대로 순회해(``w:p``/``w:tbl``), 문단
스타일/numPr로 카테고리를 정하고 표는 HTML로 직렬화한다. python-docx의 별도 flat
``.paragraphs``/``.tables`` 리스트는 상대 순서를 잃어버리므로 안 쓴다.

doc_parser의 ``GenosMsWordDocumentBackend``(2393줄)를 그대로 옮기지 않고, 흔한
케이스(헤딩/리스트/표/1x1 furniture 표 언랩)만 다루도록 스코프를 줄였다. 문서
헤더/푸터(``document.sections[i].header/footer``, body 순회에 안 잡히는 별도
파트)는 다루지 않는다 - 이 프로젝트의 ``strip_repeated_headers_footers`` 는 페이지
3개 이상일 때만 동작하는데 docx는 항상 합성 페이지 1개라 애초에 적용 대상이 아니다.
"""

from html import escape

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from loader.base_loader import BaseLoader
from util.passthrough_layout import PassthroughLayout

DUMMY_BBOX = (0.0, 0.0, 0.0, 0.0)


class Loader(BaseLoader):
    """docx 본문을 XML 순서대로 순회해 문단/표를 category 아이템으로 담는다."""

    def get_layout(self):
        return PassthroughLayout(self.layout_config)

    def get_ocr(self):
        return None

    def _extract_pages(self, file_path: str):
        """문서 전체를 페이지 1개로 취급해 (줄 목록, None) 쌍 하나만 낸다.

        Args:
            file_path: 읽을 docx 파일 경로.

        Yields:
            ``(lines, None)`` 튜플 하나.
        """
        document = Document(file_path)
        lines = []
        for el in document.element.body.iterchildren():
            self._walk(el, document, lines)
        yield lines, None

    @classmethod
    def _walk(cls, el, parent, lines):
        if el.tag == qn("w:p"):
            paragraph = Paragraph(el, parent)
            text = paragraph.text.strip()
            if text:
                lines.append((text, DUMMY_BBOX, cls._paragraph_category(paragraph)))
        elif el.tag == qn("w:tbl"):
            table = Table(el, parent)
            if cls._is_furniture(table):
                cell = table.rows[0].cells[0]
                for child in cell._tc.iterchildren():
                    cls._walk(child, cell, lines)
                return
            html = cls._table_to_html(table)
            if html:
                lines.append((html, DUMMY_BBOX, "table"))

    @staticmethod
    def _is_furniture(table) -> bool:
        """셀 하나짜리 표가 그 안에 중첩 표만 담은 "래퍼"인지 판별한다."""
        return len(table.rows) == 1 and len(table.columns) == 1 and bool(table.rows[0].cells[0].tables)

    @staticmethod
    def _table_to_html(table) -> str:
        rows_html = "".join(
            "<tr>" + "".join(f"<td>{escape(cell.text)}</td>" for cell in row.cells) + "</tr>"
            for row in table.rows
        )
        return f"<table><tbody>{rows_html}</tbody></table>"

    @staticmethod
    def _paragraph_category(paragraph) -> str:
        style = (paragraph.style.name or "").lower()
        if style == "title":
            return "title"
        if style.startswith("heading") or style == "subtitle":
            return "section_header"
        if style == "caption":
            return "caption"
        if style.startswith("list") or Loader._has_numbering(paragraph):
            return "list_item"
        return "text"

    @staticmethod
    def _has_numbering(paragraph) -> bool:
        p_pr = paragraph._p.find(qn("w:pPr"))
        return p_pr is not None and p_pr.find(qn("w:numPr")) is not None
