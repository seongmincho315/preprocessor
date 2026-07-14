"""GenOS 벡터DB(Weaviate) 스키마에 맞춰 청크를 메타데이터 dict로 변환한다.
필드명/타입은 GenOS admin-api의 PropertyBuilder.get_default_props() 기준.
vector_id, index, file_name, file_path, file_ext, file_size, file_hash, doc_id,
is_encrypted는 GenOS preprocess-api가 업로드 시 자체적으로 채우므로 여기서는 만들지 않는다."""

from datetime import datetime
from typing import List


class GenosMetadata:
    """청커가 만든 ``{text, i_page, e_page}`` 청크를 GenOS 벡터 dict로 변환한다."""

    def __call__(self, chunks: List[dict]) -> List[dict]:
        """청크 목록을 GenOS 서빙용 벡터 dict 목록으로 변환한다.

        Args:
            chunks: 청커가 반환한 ``{text, i_page, e_page}`` 청크 목록.

        Returns:
            각 청크마다 ``text``, ``n_chars``/``n_words``/``n_lines``,
            ``i_page``/``e_page``/``n_page``,
            ``i_chunk_on_page``/``n_chunk_of_page``,
            ``i_chunk_on_doc``/``n_chunk_of_doc``, ``reg_date`` 를 담은 dict
            목록. ``chunks`` 가 비어 있으면 빈 리스트.
        """
        if not chunks:
            return []

        reg_date = datetime.now().isoformat(timespec="seconds") + "Z"
        n_page = max(chunk["e_page"] for chunk in chunks)
        n_chunk_of_doc = len(chunks)

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
                }
            )
        return vectors
