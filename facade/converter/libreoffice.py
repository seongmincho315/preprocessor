from typing import List

from loader.base_loader import BaseLoader


class Loader(BaseLoader):
    """다른 포맷을 pdf로 변환한 뒤 로드한다. 아직 실제 변환/로드 로직은 없음 (placeholder)."""

    def _extract_pages(self, file_path: str) -> List[list]:
        raise NotImplementedError(f"아직 지원하지 않는 파일 형식입니다: {file_path}")
