from pypdf import PdfReader

from loader.base_loader import BaseLoader


class Loader(BaseLoader):
    def _extract_pages(self, file_path: str):
        reader = PdfReader(file_path)
        for page in reader.pages:
            yield self._extract_lines(page)

    @staticmethod
    def _extract_lines(page):
        """페이지 안의 텍스트를 y 좌표 기준으로 줄 단위로 묶어 (text, bbox, font_size) 목록으로 반환한다."""
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
