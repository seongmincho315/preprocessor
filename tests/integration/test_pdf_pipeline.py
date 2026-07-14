"""로컬 통합 테스트: 실제 detr(:30881)/paddle(:30880) 파드에 붙여
DocumentProcessor 전체 파이프라인(파일분할 -> 로드 -> 전처리/보강 -> 청킹 ->
후처리/보강 -> 메타데이터)을 검증한다. 로컬에 두 파드가 떠 있지 않으면
자동으로 skip된다."""

import pytest

pytestmark = pytest.mark.integration

EXPECTED_ITEM_KEYS = {"text", "category", "bbox", "page"}
EXPECTED_CHUNK_KEYS = {"text", "i_page", "e_page"}
EXPECTED_METADATA_KEYS = {
    "text", "n_chars", "n_words", "n_lines", "i_page", "e_page", "n_page",
    "i_chunk_on_page", "n_chunk_of_page", "i_chunk_on_doc", "n_chunk_of_doc", "reg_date",
}


def test_pdf_pipeline_end_to_end(document_processor, sample_pdf):
    dp = document_processor
    file_paths = dp.file_handling(str(sample_pdf))
    try:
        items = dp.load(file_paths)
        assert items, "아이템이 하나도 추출되지 않음"
        assert all(EXPECTED_ITEM_KEYS <= item.keys() for item in items)

        items = dp.pre_enrich(dp.preprocess(items))

        chunks = dp.chunking(items)
        assert chunks, "청크가 하나도 생성되지 않음"
        assert all(EXPECTED_CHUNK_KEYS <= chunk.keys() for chunk in chunks)

        chunks = dp.post_enrich(dp.postprocess(chunks))

        metadata = dp.build_metadata(chunks, str(sample_pdf))
        assert len(metadata) == len(chunks)
        assert all(EXPECTED_METADATA_KEYS <= entry.keys() for entry in metadata)
        assert metadata[0]["i_chunk_on_doc"] == 0
        assert metadata[-1]["i_chunk_on_doc"] == len(metadata) - 1
        assert all(entry["n_chunk_of_doc"] == len(metadata) for entry in metadata)
    finally:
        dp._cleanup_split_files(str(sample_pdf), file_paths)
