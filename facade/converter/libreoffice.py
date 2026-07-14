"""LibreOffice로 다른 포맷을 PDF로 변환한 뒤 로드하는 컨버터.
전용 로더가 없는 확장자에 대해 ``preprocessor.py`` 가 대체(fallback)로 시도한다."""

from typing import List

from loader.base_loader import BaseLoader


class Loader(BaseLoader):
    """다른 포맷을 pdf로 변환한 뒤 로드한다. 아직 실제 변환/로드 로직은 없음 (placeholder)."""

    def _extract_pages(self, file_path: str) -> List[list]:
        """아직 미구현. 항상 :class:`NotImplementedError` 를 낸다.

        Args:
            file_path: 변환할 원본 파일 경로.

        Raises:
            NotImplementedError: 항상.
        """
        raise NotImplementedError(f"아직 지원하지 않는 파일 형식입니다: {file_path}")
