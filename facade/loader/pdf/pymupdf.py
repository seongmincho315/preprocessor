import fitz  # PyMuPDF

from loader.base_loader import BaseLoader


class Loader(BaseLoader):
    def _extract_pages(self, file_path: str):
        doc = fitz.open(file_path)
        try:
            for page in doc:
                yield self._extract_lines(page)
        finally:
            doc.close()

    @staticmethod
    def _extract_lines(page):
        """페이지의 텍스트를 줄 단위로 (text, bbox, font_size) 목록으로 반환한다."""
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
