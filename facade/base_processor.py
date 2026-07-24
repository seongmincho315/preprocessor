"""``DocumentProcessor`` 계열이 공통으로 따르는 파이프라인 골격.

:class:`preprocessor.DocumentProcessor` (config.yaml 기반, GenOS ``/run`` 진입점)와
:class:`custom_preprocessor.DocumentProcessor` (조합을 코드에 고정한 예제)는
``file_handling -> load -> preprocess -> pre_enrich -> chunking ->
postprocess -> post_enrich -> build_metadata`` 8단계를 공유한다. 이 클래스가
그 8단계를 구현하고, 서브클래스는 ``__init__`` 에서
``self.loader``/``self.chunker``/``self.metadata_builder`` 만 채우면 된다.
``preprocess``/``pre_enrich``/``postprocess``/``post_enrich`` 는 기본이 항등
함수(입력을 그대로 반환)라 아무것도 채우지 않아도 되고, 필요한 서브클래스만
오버라이드하면 된다.

``__call__`` 은 동기 ``(file_path)`` 진입점으로 이 8단계를 그대로 실행한다.
GenOS ``/run`` 처럼 진입점 계약이 다른 배포(async, ``request``/``params``
인자 필요)만 서브클래스에서 오버라이드한다.
"""

import shutil
from abc import ABC
from pathlib import Path
from typing import List

from util.util import file_split, get_ext


class BaseProcessor(ABC):
    """파일 분할 -> 로드 -> 전처리/보강 -> 청킹 -> 후처리/보강 -> 메타데이터
    파이프라인의 공통 구현.

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
        ``file_handling``(:func:`~util.util.file_split`)이 큰 PDF를 여러 파일로
        잘랐다면, 각 분할 파일의 페이지 번호는 1부터 다시 시작하므로 원본 문서
        기준 페이지 번호가 되도록 ``i * max_page_split`` 만큼 오프셋을 더한다
        (더하지 않으면 두 번째 이후 분할 파일의 아이템이 첫 파일과 같은 페이지
        번호를 갖게 되어, 서로 다른 원본 페이지의 내용이 같은 페이지로 겹쳐 보인다).

        Args:
            file_paths: :meth:`file_handling` 이 반환한 파일 경로 목록.

        Returns:
            ``{text, category, bbox, page}`` 형태의 아이템 목록.
        """
        items = []
        for i, file_path in enumerate(file_paths):
            ext = get_ext(file_path=file_path)
            page_offset = i * self.max_page_split
            for item in self.loader[ext](file_path):
                if page_offset:
                    item["page"] += page_offset
                items.append(item)
        return items

    def preprocess(self, items: List[dict]) -> List[dict]:
        """룰 기반 전처리(예: 띄어쓰기 보정, 사전 치환). 청킹 전, 아이템 단위로 적용된다.

        기본은 아무 것도 하지 않고 ``items`` 를 그대로 반환한다 - 서브클래스가
        필요할 때만 오버라이드한다.

        Args:
            items: :meth:`load` 가 반환한 아이템 목록.

        Returns:
            전처리된 아이템 목록.
        """
        return items

    def pre_enrich(self, items: List[dict]) -> List[dict]:
        """외부 모델 기반 보강. 청킹 전, 아이템 단위로 적용된다.

        기본은 아무 것도 하지 않고 ``items`` 를 그대로 반환한다 - 서브클래스가
        필요할 때만 오버라이드한다.

        Args:
            items: :meth:`preprocess` 가 반환한 아이템 목록.

        Returns:
            보강된 아이템 목록.
        """
        return items

    def chunking(self, items: List[dict]) -> List[dict]:
        """아이템을 청크로 묶는다.

        Args:
            items: :meth:`pre_enrich` 가 반환한 아이템 목록.

        Returns:
            ``{text, i_page, e_page}`` 형태의 청크 목록. ``i_page``/``e_page`` 는
            그 청크가 걸쳐 있는 페이지 범위다.
        """
        return self.chunker(items)

    def postprocess(self, chunks: List[dict]) -> List[dict]:
        """청크 단위 후처리. 청킹 후, 메타데이터 변환 전에 적용된다.

        기본은 아무 것도 하지 않고 ``chunks`` 를 그대로 반환한다 - 서브클래스가
        필요할 때만 오버라이드한다.

        Args:
            chunks: :meth:`chunking` 이 반환한 청크 목록.

        Returns:
            후처리된 청크 목록.
        """
        return chunks

    def post_enrich(self, chunks: List[dict]) -> List[dict]:
        """외부 모델 기반 보강(예: image_description, table_refiner). 청크 단위로,
        메타데이터 변환 전에 적용된다.

        기본은 아무 것도 하지 않고 ``chunks`` 를 그대로 반환한다 - 서브클래스가
        필요할 때만 오버라이드한다.

        Args:
            chunks: :meth:`postprocess` 가 반환한 청크 목록.

        Returns:
            보강된 청크 목록.
        """
        return chunks

    def build_metadata(self, chunks: List[dict], file_path: str = None) -> List[dict]:
        """청크 목록을 GenOS 서빙용 벡터 dict 목록(메타데이터)으로 변환한다.

        Args:
            chunks: :meth:`post_enrich` 가 반환한 청크 목록.
            file_path: 원본 파일 경로. GenOS 청크에디터가 기대하는 정규화된
                ``chunk_bboxes``(:mod:`metadata.genos` 참고)를 만들 때 페이지
                크기(포인트 단위)를 얻기 위해 PDF를 다시 여는 데 쓰인다.

        Returns:
            GenOS Weaviate 컬렉션 스키마에 맞는 벡터 dict 목록.
        """
        return self.metadata_builder(chunks, file_path)

    def __call__(self, file_path: str) -> List[dict]:
        """전체 파이프라인(파일 분할 -> 로드 -> 전처리/보강 -> 청킹 -> 후처리/보강
        -> 메타데이터)을 동기적으로 실행한다.

        GenOS ``/run`` 처럼 진입점 계약이 다른 배포(async, ``request``/``params``
        인자 필요)는 서브클래스가 이 메서드를 오버라이드한다
        (:class:`preprocessor.DocumentProcessor` 참고).

        Args:
            file_path: 처리할 원본 파일 경로.

        Returns:
            :meth:`build_metadata` 가 반환한 벡터 dict 목록.
        """
        file_paths = self.file_handling(file_path)
        try:
            items = self.load(file_paths)
            items = self.preprocess(items)
            items = self.pre_enrich(items)
            chunks = self.chunking(items)
            chunks = self.postprocess(chunks)
            chunks = self.post_enrich(chunks)
            return self.build_metadata(chunks, file_path)
        finally:
            self._cleanup_split_files(file_path, file_paths)

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
