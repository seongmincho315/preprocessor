from typing import List


def build(chunks: List[str]) -> List[dict]:
    """청크 목록을 서빙용 벡터 dict 목록으로 변환한다."""
    return [{"text": chunk, "chunk_index": i} for i, chunk in enumerate(chunks)]
