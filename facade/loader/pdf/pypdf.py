"""pypdf 기반 PDF 로더. ``ext.pdf`` 가 ``pypdf`` 일 때 쓰인다.

PyMuPDF 로더(:mod:`loader.pdf.pymupdf`)의 대안으로, 페이지 이미지 렌더링을
지원하지 않으므로(항상 ``None``) 이미지가 필요한 레이아웃/OCR 전략과는
같이 쓸 수 없다.
"""

from pypdf import PdfReader

from loader.base_loader import BaseLoader


class Loader(BaseLoader):
    """pypdf의 텍스트 추출 visitor로 줄 단위 텍스트를 뽑는다. 페이지 이미지는 만들지 않는다."""

    def _extract_pages(self, file_path: str):
        """PDF를 열어 페이지마다 (텍스트 줄 목록, None) 쌍을 순서대로 낸다.

        Args:
            file_path: 읽을 PDF 파일 경로.

        Yields:
            ``(lines, None)`` 튜플. ``lines`` 는 :meth:`_extract_lines` 의 결과.
        """
        reader = PdfReader(file_path)
        for page in reader.pages:
            yield self._extract_lines(page), None, None

    @staticmethod
    def _extract_lines(page):
        """페이지 안의 텍스트를 y 좌표 기준으로 줄 단위로 묶어 (text, bbox, font_size) 목록으로 반환한다.

        Args:
            page: ``pypdf`` 페이지 객체.

        Returns:
            ``(text, (x0, y0, x1, y1), font_size)`` 튜플 목록. bbox는 글자 수와
            폰트 크기로 폭을 근사한 값(실제 span bbox가 아님).
        """
        lines = []
        buffer = {"text": "", "x": None, "y": None, "font_size": None}

        def flush():
            if buffer["text"].strip():
                width = buffer["font_size"] * 0.5 * len(buffer["text"])
                bbox = (buffer["x"], buffer["y"], buffer["x"] + width, buffer["y"] + buffer["font_size"])
                lines.append((buffer["text"], bbox, buffer["font_size"]))

        def visitor(text, cm, tm, font_dict, font_size):
            if not text or not text.strip():
                return
            x, y = tm[4], tm[5]
            if buffer["y"] is not None and abs(y - buffer["y"]) > 1:
                flush()
                buffer["text"] = ""
                buffer["x"] = None
            buffer["text"] += text
            buffer["x"] = buffer["x"] if buffer["x"] is not None else x
            buffer["y"] = y
            buffer["font_size"] = font_size

        page.extract_text(visitor_text=visitor)
        flush()

        return lines
