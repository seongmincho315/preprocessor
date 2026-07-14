"""GenOS 문서 전처리기의 파사드.

``resource/config.yaml`` 설정에 따라 확장자별 로더, 레이아웃/OCR 전략, 청커,
메타데이터 빌더를 동적으로 구성하고, 파일 핸들링 -> 로드 -> 청킹 -> 메타데이터
순으로 이어지는 전체 파이프라인을 :class:`DocumentProcessor` 하나로 노출한다.
"""

import importlib
import shutil
from pathlib import Path
from typing import List

import yaml
from util.util import get_ext, file_split, CATEGORIES

CONFIG_PATH = Path(__file__).parent / "resource" / "config.yaml"


class DocumentProcessor:
    """``config.yaml``\ 에 설정된 조합으로 문서 하나를 파싱해 GenOS 벡터 메타데이터로 만든다.

    파이프라인은 4단계다:

    1. :meth:`file_handling` - 페이지 수가 많으면 여러 파일로 분할
    2. :meth:`load` - 확장자별 로더로 텍스트/레이아웃/OCR을 읽어 아이템 목록으로 변환
    3. :meth:`chunking` - 아이템을 청크로 묶고 페이지 범위를 함께 추적
    4. :meth:`build_metadata` - 청크를 GenOS 서빙용 벡터 dict로 변환

    Attributes:
        max_page_split (int): 이 페이지 수를 넘으면 파일을 분할한다.
        loader (dict[str, BaseLoader]): 확장자 -> 로더 인스턴스.
        chunker: ``config.yaml``\ 의 ``chunker.type``\ 으로 선택된 청커 인스턴스.
        metadata_builder: GenOS 메타데이터 빌더 인스턴스.
    """

    def __init__(self):
        """``resource/config.yaml``\ 을 읽어 로더/청커/메타데이터 빌더를 초기화한다."""
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.max_page_split = config["max_page_split"]

        # layout.type이 rule이 아니면 resource/<type>.yaml(전략별 세부 설정)을 읽어 병합한다.
        layout_config = dict(config.get("layout") or {})
        layout_type = layout_config.get("type", "rule")
        if layout_type != "rule":
            strategy_path = CONFIG_PATH.parent / f"{layout_type}.yaml"
            if strategy_path.exists():
                with open(strategy_path, encoding="utf-8") as f:
                    layout_config.update(yaml.safe_load(f) or {})

        # ocr.type이 있으면 resource/<type>.yaml(전략별 세부 설정)을 읽어 병합한다.
        ocr_config = dict(config.get("ocr") or {})
        ocr_type = ocr_config.get("type")
        if ocr_type:
            strategy_path = CONFIG_PATH.parent / f"{ocr_type}.yaml"
            if strategy_path.exists():
                with open(strategy_path, encoding="utf-8") as f:
                    ocr_config.update(yaml.safe_load(f) or {})

        # loader는 확장자별 loader.<ext>.<이름> 모듈의 Loader 클래스를 쓴다 (예: loader.pdf.pymupdf).
        # 없으면 converter.<이름>의 Loader로 대체한다 (예: libreoffice로 pdf 변환 후 로드).
        # 둘 다 없는 확장자/전략은 건너뛴다.
        self.loader = {}
        for ext, name in config["ext"].items():
            try:
                loader_module = importlib.import_module(f"loader.{ext}.{name}")
            except ModuleNotFoundError:
                try:
                    loader_module = importlib.import_module(f"converter.{name}")
                except ModuleNotFoundError:
                    continue
            self.loader[ext] = loader_module.Loader(layout_config, ocr_config)

        self.chunker = importlib.import_module(f"chunker.{config['chunker']['type']}").Chunker(
            chunk_size=config["chunker"]["chunk_size"],
            chunk_overlap=config["chunker"]["over_lap"],
        )
        self.metadata_builder = importlib.import_module("metadata.genos").GenosMetadata()

    def file_handling(self, file_path: str) -> List[str]:
        """``max_page_split``\ 을 넘는 PDF를 여러 파일로 잘라 경로 목록을 반환한다.

        분할된 파일은 ``preprocessor.py``\ 가 있는 디렉터리 밑에
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
            file_paths: :meth:`file_handling`\ 이 반환한 파일 경로 목록.

        Returns:
            ``{text, category, bbox, page}`` 형태의 아이템 목록.
        """
        items = []
        for file_path in file_paths:
            ext = get_ext(file_path=file_path)
            items.extend(self.loader[ext](file_path))
        return items

    def preprocess(self):
        # 띄어쓰기 보정
        # 딕셔너리 기능도 필요하겠당
        pass

    def chunking(self, items: List[dict]) -> List[dict]:
        """아이템을 청크로 묶는다.

        Args:
            items: :meth:`load`\ 가 반환한 아이템 목록.

        Returns:
            ``{text, i_page, e_page}`` 형태의 청크 목록. ``i_page``/``e_page``\ 는
            그 청크가 걸쳐 있는 페이지 범위다.
        """
        return self.chunker(items)

    def build_metadata(self, chunks: List[dict], file_path: str) -> List[dict]:
        """청크 목록을 GenOS 서빙용 벡터 dict 목록(메타데이터)으로 변환한다.

        Args:
            chunks: :meth:`chunking`\ 이 반환한 청크 목록.
            file_path: 원본 파일 경로(현재 구현에서는 사용하지 않음).

        Returns:
            GenOS Weaviate 컬렉션 스키마에 맞는 벡터 dict 목록.
        """
        return self.metadata_builder(chunks)

    async def __call__(self, request, file_path: str, **params):
        """전체 파이프라인(파일 분할 -> 로드 -> 청킹 -> 메타데이터)을 실행한다.

        Args:
            request: GenOS ``/run`` 요청 객체(현재 구현에서는 사용하지 않음).
            file_path: 처리할 원본 파일 경로.
            **params: 확장 파라미터(현재 구현에서는 사용하지 않음).

        Returns:
            :meth:`build_metadata`\ 가 반환한 벡터 dict 목록.
        """
        file_paths = self.file_handling(file_path)
        try:
            items = self.load(file_paths)
            chunks = self.chunking(items)
            return self.build_metadata(chunks, file_path)
        finally:
            self._cleanup_split_files(file_path, file_paths)

    @staticmethod
    def _cleanup_split_files(file_path: str, file_paths: List[str]) -> None:
        """``file_handling``\ 이 분할했을 때만(원본과 다를 때만) 생성된 임시 디렉터리를 지운다.

        Args:
            file_path: 원본 파일 경로.
            file_paths: :meth:`file_handling`\ 이 반환했던 파일 경로 목록.
        """
        if file_paths == [file_path]:
            return
        split_dir = Path(file_paths[0]).parent
        shutil.rmtree(split_dir, ignore_errors=True)
