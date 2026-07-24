"""PyMuPDF(``fitz``) 기반 PDF 로더. ``ext.pdf`` 가 ``pymupdf`` 일 때 쓰인다."""

from typing import List, Tuple

import fitz  # PyMuPDF

from loader.base_loader import BaseLoader


class Loader(BaseLoader):
    """PyMuPDF로 PDF의 텍스트 레이어와 페이지 이미지를 페이지 단위로 추출한다."""

    def _extract_pages(self, file_path: str):
        """PDF를 열어 페이지마다 (텍스트 줄 목록, 페이지 이미지, 단어 목록) 튜플을 순서대로 낸다.

        Args:
            file_path: 읽을 PDF 파일 경로.

        Yields:
            ``(lines, image, words)`` 튜플. ``lines`` 는 :meth:`_extract_lines` 의 결과,
            ``image`` 는 :attr:`needs_image` 일 때만 PNG bytes(아니면 ``None``), ``words`` 는
            :meth:`_extract_words` 의 결과(``image`` 와 마찬가지로 ``needs_image`` 일 때만).
        """
        doc = fitz.open(file_path)
        try:
            for page in doc:
                lines = self._extract_lines(page)
                image = page.get_pixmap(dpi=self.image_dpi).tobytes("png") if self.needs_image else None
                words = self._extract_words(page) if self.needs_image else None
                yield lines, image, words
        finally:
            doc.close()

    @staticmethod
    def _extract_words(page) -> List[Tuple[str, Tuple[float, float, float, float]]]:
        """페이지의 텍스트를 PDF 원본 단어 단위 ``(text, bbox)`` 목록으로 반환한다.

        PyMuPDF가 실제 glyph 위치를 기반으로 나눈 단어 그대로 쓴다(문자 수 비례 추정이 아님) -
        tableformer의 cell 매칭(``do_matching``)에 줄 단위보다 훨씬 정확하게 쓰인다.
        """
        return [(w[4], (w[0], w[1], w[2], w[3])) for w in page.get_text("words")]

    #: span 사이 가로 간격이 (두 span 폰트 크기 평균) * 이 값보다 크면, 원본에서
    #: 띄어져 있던 것으로 보고 공백을 끼워 넣는다.
    SPACE_GAP_RATIO = 0.25

    @staticmethod
    def _extract_lines(page):
        """페이지의 텍스트를 줄 단위로 (text, bbox, font_size) 목록으로 반환한다.

        Args:
            page: ``fitz.Page`` 인스턴스.

        Returns:
            ``(text, (x0, y0, x1, y1), font_size)`` 튜플 목록. bbox는 같은 줄에
            속한 span들의 좌표 min/max, font_size는 그 줄에서 글자 수가 가장 많은
            span의 크기다(각주 번호처럼 크기가 다른 span이 줄 맨 앞에 와도
            흔들리지 않도록).
        """
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = Loader._join_spans(spans).strip()
                if not text:
                    continue
                x0 = min(span["bbox"][0] for span in spans)
                y0 = min(span["bbox"][1] for span in spans)
                x1 = max(span["bbox"][2] for span in spans)
                y1 = max(span["bbox"][3] for span in spans)
                font_size = Loader._dominant_font_size(spans)
                lines.append((text, (x0, y0, x1, y1), font_size))
        return lines

    @staticmethod
    def _dominant_font_size(spans) -> float:
        """줄 안에서 글자 수가 가장 많은 span의 폰트 크기를 그 줄의 대표 크기로 쓴다."""
        totals = {}
        for span in spans:
            totals[span["size"]] = totals.get(span["size"], 0) + len(span["text"])
        return max(totals, key=totals.get)

    @staticmethod
    def _join_spans(spans) -> str:
        """볼드/색상 등으로 같은 줄 안에서 span이 나뉜 경우, span 사이 가로 간격을
        보고 원본에 있었을 공백을 복원해서 이어붙인다. PyMuPDF가 span을 나눌 때
        그 사이의 공백 문자를 아무 span에도 포함시키지 않는 경우가 있어서, 그냥
        이어붙이면 "단어단어"처럼 붙어버릴 수 있다."""
        parts = [spans[0]["text"]]
        for prev, span in zip(spans, spans[1:]):
            gap = span["bbox"][0] - prev["bbox"][2]
            threshold = (prev["size"] + span["size"]) / 2 * Loader.SPACE_GAP_RATIO
            if gap > threshold and not parts[-1].endswith(" ") and not span["text"].startswith(" "):
                parts.append(" ")
            parts.append(span["text"])
        return "".join(parts)
