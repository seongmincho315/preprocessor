"""preprocessor.py는 config.yaml의 type 값을 보고 importlib로 어떤 모듈을 쓸지
런타임에 정한다. 이 파일은 반대로 "pdf + detr 레이아웃 + paddle OCR + smart_chunker +
GenOS 메타데이터" 조합을 미리 정해두고, 필요한 클래스를 코드 상단에서 직접 import해서
조립하는 예제다. 특정 고객사 전용으로 파이프라인을 고정해야 할 때 이런 식으로 쓸 수 있다.
"""

from typing import List

from base_processor import BaseProcessor
from chunker.smart_chunker import Chunker
from loader.pdf.pymupdf import Loader as PdfLoader
from metadata.genos import GenosMetadata

LAYOUT_CONFIG = {
    "type": "detr",
    "url": "http://localhost:30881",
    "image_dpi": 150,
    "timeout": 60,
}
OCR_CONFIG = {
    "type": "paddle",
    "url": "http://localhost:30880",
    "timeout": 60,
}


class DocumentProcessor(BaseProcessor):
    """pdf + detr + paddle + smart_chunker + GenOS 메타데이터 조합을 고정한 전처리기.

    :class:`preprocessor.DocumentProcessor` 와 같은 4단계(:class:`base_processor.BaseProcessor` 가
    구현하는 파일 분할 -> 로드 -> 청킹 -> 메타데이터)를 거치지만, ``config.yaml``
    없이 이 파일 안의 :data:`LAYOUT_CONFIG`/:data:`OCR_CONFIG` 로 조합이
    코드에 고정돼 있다.
    """

    max_page_split = 50

    def __init__(self):
        self.loader = {"pdf": PdfLoader(LAYOUT_CONFIG, OCR_CONFIG)}
        self.chunker = Chunker(chunk_size=1000, chunk_overlap=100)
        self.metadata_builder = GenosMetadata()

    def __call__(self, file_path: str) -> List[dict]:
        """전체 파이프라인(파일 분할 -> 로드 -> 청킹 -> 메타데이터)을 실행한다.

        Args:
            file_path: 처리할 원본 파일 경로.

        Returns:
            GenOS 서빙용 벡터 dict 목록.
        """
        file_paths = self.file_handling(file_path)
        try:
            items = self.load(file_paths)
            chunks = self.chunking(items)
            return self.build_metadata(chunks)
        finally:
            self._cleanup_split_files(file_path, file_paths)
