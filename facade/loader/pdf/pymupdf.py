"""PyMuPDF(``fitz``) 기반 PDF 로더. ``ext.pdf``\ 가 ``pymupdf``\ 일 때 쓰인다."""

import fitz  # PyMuPDF

from loader.base_loader import BaseLoader


class Loader(BaseLoader):
    """PyMuPDF로 PDF의 텍스트 레이어와 페이지 이미지를 페이지 단위로 추출한다."""

    def _extract_pages(self, file_path: str):
        """PDF를 열어 페이지마다 (텍스트 줄 목록, 페이지 이미지) 쌍을 순서대로 낸다.

        Args:
            file_path: 읽을 PDF 파일 경로.

        Yields:
            ``(lines, image)`` 튜플. ``lines``\ 는 :meth:`_extract_lines`\ 의 결과,
            ``image``\ 는 :attr:`needs_image`(레이아웃/OCR 전략이 이미지를 필요로
            할 때)일 때만 PNG bytes, 아니면 ``None``.
        """
        doc = fitz.open(file_path)
        try:
            for page in doc:
                lines = self._extract_lines(page)
                image = page.get_pixmap(dpi=self.image_dpi).tobytes("png") if self.needs_image else None
                yield lines, image
        finally:
            doc.close()

    @staticmethod
    def _extract_lines(page):
        """페이지의 텍스트를 줄 단위로 (text, bbox, font_size) 목록으로 반환한다.

        Args:
            page: ``fitz.Page`` 인스턴스.

        Returns:
            ``(text, (x0, y0, x1, y1), font_size)`` 튜플 목록. bbox는 같은 줄에
            속한 span들의 좌표 min/max, font_size는 그 줄 첫 span의 크기다.
        """
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(span["text"] for span in spans).strip()
                if not text:
                    continue
                x0 = min(span["bbox"][0] for span in spans)
                y0 = min(span["bbox"][1] for span in spans)
                x1 = max(span["bbox"][2] for span in spans)
                y1 = max(span["bbox"][3] for span in spans)
                font_size = spans[0]["size"]
                lines.append((text, (x0, y0, x1, y1), font_size))
        return lines
