"""GenOS 벡터DB(Weaviate) 스키마에 맞춰 청크를 메타데이터 dict로 변환한다.
필드명/타입은 GenOS admin-api의 PropertyBuilder.get_default_props() 기준.
vector_id, index, file_name, file_path, file_ext, file_size, file_hash, doc_id,
is_encrypted는 GenOS preprocess-api가 업로드 시 자체적으로 채우므로 여기서는 만들지 않는다."""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class GenosMetadata:
    """청커가 만든 ``{text, i_page, e_page, bboxes}`` 청크를 GenOS 벡터 dict로 변환한다."""

    def __call__(self, chunks: List[dict], file_path: str = None) -> List[dict]:
        """청크 목록을 GenOS 서빙용 벡터 dict 목록으로 변환한다.

        Args:
            chunks: 청커가 반환한 ``{text, i_page, e_page, bboxes}`` 청크 목록.
            file_path: 원본 파일 경로. PDF면 다시 열어 페이지 크기(포인트)를 얻고,
                이를 이용해 ``chunk_bboxes`` 를 0~1 정규화 좌표로 만든다
                (:meth:`_build_chunk_bboxes` 참고). ``None`` 이거나 PDF가 아니면
                ``chunk_bboxes`` 는 ``None``.

        Returns:
            각 청크마다 ``text``, ``n_chars``/``n_words``/``n_lines``,
            ``i_page``/``e_page``/``n_page``,
            ``i_chunk_on_page``/``n_chunk_of_page``,
            ``i_chunk_on_doc``/``n_chunk_of_doc``, ``reg_date``, ``chunk_bboxes`` 를
            담은 dict 목록. ``chunks`` 가 비어 있으면 빈 리스트.
        """
        if not chunks:
            return []

        reg_date = datetime.now().isoformat(timespec="seconds") + "Z"
        n_page = max(chunk["e_page"] for chunk in chunks)
        n_chunk_of_doc = len(chunks)
        page_sizes = self._page_sizes(file_path)

        n_chunk_of_page: dict = {}
        for chunk in chunks:
            n_chunk_of_page[chunk["i_page"]] = n_chunk_of_page.get(chunk["i_page"], 0) + 1

        vectors = []
        i_chunk_on_page: dict = {}
        for i_chunk_on_doc, chunk in enumerate(chunks):
            text = chunk["text"]
            i_page = chunk["i_page"]
            chunk_index_on_page = i_chunk_on_page.get(i_page, 0)
            i_chunk_on_page[i_page] = chunk_index_on_page + 1

            vectors.append(
                {
                    "text": text,
                    "n_chars": len(text),
                    "n_words": len(text.split()),
                    "n_lines": len(text.splitlines()),
                    "i_page": i_page,
                    "e_page": chunk["e_page"],
                    "n_page": n_page,
                    "i_chunk_on_page": chunk_index_on_page,
                    "n_chunk_of_page": n_chunk_of_page[i_page],
                    "i_chunk_on_doc": i_chunk_on_doc,
                    "n_chunk_of_doc": n_chunk_of_doc,
                    "reg_date": reg_date,
                    "chunk_bboxes": self._build_chunk_bboxes(chunk.get("bboxes"), page_sizes),
                }
            )
        return vectors

    @staticmethod
    def _page_sizes(file_path: Optional[str]) -> Dict[int, Tuple[float, float]]:
        """PDF를 다시 열어 ``{page_no: (width, height)}`` (포인트 단위)를 반환한다.

        doc_parser(docling)는 파싱 중에 이미 만든 ``DoclingDocument.pages[n].size`` 를
        재사용하지만, 우리는 그런 문서 전체 객체가 없어 여기서 가볍게 다시 연다
        (로더 인터페이스를 바꿔 모든 포맷에 페이지 크기를 흘려보내는 것보다 훨씬 작은 변경).
        PDF가 아니거나 열기 실패하면 빈 dict(= ``chunk_bboxes`` 생략).
        """
        if not file_path or not file_path.lower().endswith(".pdf"):
            return {}
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            try:
                return {i + 1: (page.rect.width, page.rect.height) for i, page in enumerate(doc)}
            finally:
                doc.close()
        except Exception:
            return {}

    @staticmethod
    def _build_chunk_bboxes(
        bboxes: Optional[List[dict]], page_sizes: Dict[int, Tuple[float, float]]
    ) -> Optional[str]:
        """청크의 ``bboxes``(절대 포인트, top-left 원점)를 GenOS 청크에디터가 기대하는
        0~1 정규화 좌표 JSON 문자열로 변환한다. doc_parser의 ``chunk_bboxes`` 와 같은
        ``{"page", "bbox": {"l","t","r","b","coord_origin"}, "type"}`` 형태이나,
        ``coord_origin`` 은 항상 ``"TOPLEFT"``(pymupdf 좌표계 그대로, docling의
        ``BOTTOMLEFT`` 처럼 뒤집을 필요 없음) - GenOS 프론트엔드
        (``admin-front/src/store/data/editor.js``)가 두 원점을 모두 처리한다.
        페이지 크기를 모르는 페이지의 항목은 건너뛴다. 남는 게 없으면 ``None``.
        """
        if not bboxes or not page_sizes:
            return None
        entries = []
        for entry in bboxes:
            bbox = entry.get("bbox")
            page = entry.get("page")
            size = page_sizes.get(page)
            if not bbox or not size:
                continue
            width, height = size
            if not width or not height:
                continue
            entries.append(
                {
                    "page": page,
                    "bbox": {
                        "l": bbox["x0"] / width,
                        "t": bbox["y0"] / height,
                        "r": bbox["x1"] / width,
                        "b": bbox["y1"] / height,
                        "coord_origin": "TOPLEFT",
                    },
                    "type": entry.get("category"),
                }
            )
        return json.dumps(entries, ensure_ascii=False) if entries else None
