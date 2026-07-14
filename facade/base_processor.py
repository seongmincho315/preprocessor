"""``DocumentProcessor`` 계열이 공통으로 따르는 파이프라인 골격.

:class:`preprocessor.DocumentProcessor` (config.yaml 기반, GenOS ``/run`` 진입점)와
:class:`custom_preprocessor.DocumentProcessor` (조합을 코드에 고정한 예제)는
``file_handling -> load -> chunking -> build_metadata`` 4단계를 공유한다.
이 클래스가 그 4단계를 구현하고, 서브클래스는 ``__init__`` 에서
``self.loader``/``self.chunker``/``self.metadata_builder`` 만 채우면 된다.

``__call__`` 은 배포 맥락마다 진입점 계약이 달라(예: GenOS의 async
``(request, file_path, **params)`` vs 단순 동기 ``(file_path)``) 서브클래스가
반드시 구현해야 하는 추상 메서드로 남겨둔다.
"""

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from util.util import file_split, get_ext


class BaseProcessor(ABC):
    """파일 분할 -> 로드 -> 청킹 -> 메타데이터 파이프라인의 공통 구현.

    서브클래스가 ``__init__`` 에서 채워야 하는 인스턴스 속성:

    Attributes:
        max_page_split (int): 이 페이지 수를 넘으면 파일을 분할한다.
        loader (dict[str, BaseLoader]): 확장자 -> 로더 인스턴스.
        chunker: ``__call__(items) -> List[dict]`` 시그니처의 청커 인스턴스.
        metadata_builder: ``__call__(chunks) -> List[dict]`` 시그니처의 메타데이터 빌더.
    """

    def file_handling(self, file_path: str) -> List[str]:
        """``max_page_split`` 을 넘는 PDF를 여러 파일로 잘라 경로 목록을 반환한다.

        분할된 파일은 이 클래스가 정의된 디렉터리 밑에
        ``<파일이름>/1.pdf, 2.pdf ...`` 형태로 저장된다. 분할이 필요 없으면
        원본 경로 하나만 담긴 리스트를 그대로 반환한다.

        Args:
            file_path: 원본 파일 경로.

        Returns:
            처리할 파일 경로 목록(분할 없으면 길이 1).
        """
        return file_split(file_path, self.max_page_split, Path(__file__).parent)

    def load(self, file_paths: List[str]) -> List[dict]:
        """분할된 파일들을 순서대로 읽어 아이템 목록으로 반환한다.

        각 파일은 확장자(매직 바이트로 판별)에 맞는 로더로 읽으며, 로더는
        내부적으로 레이아웃 분석(카테고리 부여)과 필요시 OCR을 함께 수행한다.

        Args:
            file_paths: :meth:`file_handling` 이 반환한 파일 경로 목록.

        Returns:
            ``{text, category, bbox, page}`` 형태의 아이템 목록.
        """
        items = []
        for file_path in file_paths:
            ext = get_ext(file_path=file_path)
            items.extend(self.loader[ext](file_path))
        return items

    def chunking(self, items: List[dict]) -> List[dict]:
        """아이템을 청크로 묶는다.

        Args:
            items: :meth:`load` 가 반환한 아이템 목록.

        Returns:
            ``{text, i_page, e_page}`` 형태의 청크 목록. ``i_page``/``e_page`` 는
            그 청크가 걸쳐 있는 페이지 범위다.
        """
        return self.chunker(items)

    def build_metadata(self, chunks: List[dict], file_path: str = None) -> List[dict]:
        """청크 목록을 GenOS 서빙용 벡터 dict 목록(메타데이터)으로 변환한다.

        Args:
            chunks: :meth:`chunking` 이 반환한 청크 목록.
            file_path: 원본 파일 경로(현재 구현에서는 사용하지 않음).

        Returns:
            GenOS Weaviate 컬렉션 스키마에 맞는 벡터 dict 목록.
        """
        return self.metadata_builder(chunks)

    @abstractmethod
    def __call__(self, *args, **kwargs) -> List[dict]:
        """전체 파이프라인(파일 분할 -> 로드 -> 청킹 -> 메타데이터)을 실행한다.

        배포 맥락에 따라 시그니처가 달라지므로(GenOS ``/run`` async 진입점 vs
        단순 동기 호출) 서브클래스가 직접 구현해야 한다.
        """
        raise NotImplementedError

    @staticmethod
    def _cleanup_split_files(file_path: str, file_paths: List[str]) -> None:
        """``file_handling`` 이 분할했을 때만(원본과 다를 때만) 생성된 임시 디렉터리를 지운다.

        Args:
            file_path: 원본 파일 경로.
            file_paths: :meth:`file_handling` 이 반환했던 파일 경로 목록.
        """
        if file_paths == [file_path]:
            return
        split_dir = Path(file_paths[0]).parent
        shutil.rmtree(split_dir, ignore_errors=True)
