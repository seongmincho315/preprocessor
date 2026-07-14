import importlib
import shutil
from pathlib import Path
from typing import List

import yaml
from util.util import get_ext, file_split, CATEGORIES

CONFIG_PATH = Path(__file__).parent / "resource" / "config.yaml"


class DocumentProcessor:
    def __init__(self):
        """config.yaml 값 할당"""
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
        self.metadata_builder = importlib.import_module("metadata.test").build

    def file_handling(self, file_path: str) -> List[str]:
        """PDF가 50페이지를 넘으면 여러 파일로 잘라 경로 목록을 반환한다.
        경로: preprocessor.py 가 있는 디렉토리
        저장방식: ./<파일이름>/1.pdf, 2.pdf ......"""
        return file_split(file_path, self.max_page_split, Path(__file__).parent)

    def load(self, file_paths: List[str]) -> List[dict]:
        """분할된 파일들을 순서대로 읽어 {text, category, bbox, page} 아이템 목록으로 반환한다."""
        items = []
        for file_path in file_paths:
            ext = get_ext(file_path=file_path)
            items.extend(self.loader[ext](file_path))
        return items

    def preprocess(self):
        # 띄어쓰기 보정
        # 딕셔너리 기능도 필요하겠당
        pass

    def chunking(self, items: List[dict]) -> List[str]:
        """아이템의 텍스트를 이어붙인 뒤 chunk_size 기준으로 겹치게 분할한다."""
        return self.chunker(items)

    def build_metadata(self, chunks: List[str], file_path: str) -> List[dict]:
        """청크 목록을 서빙용 벡터 dict 목록으로 변환한다."""
        return self.metadata_builder(chunks)

    async def __call__(self, request, file_path: str, **params):
        file_paths = self.file_handling(file_path)
        try:
            items = self.load(file_paths)
            chunks = self.chunking(items)
            return self.build_metadata(chunks, file_path)
        finally:
            self._cleanup_split_files(file_path, file_paths)

    @staticmethod
    def _cleanup_split_files(file_path: str, file_paths: List[str]) -> None:
        """file_handling이 분할했을 때만(원본과 다를 때만) 생성된 <파일이름>/*.pdf 디렉터리를 지운다."""
        if file_paths == [file_path]:
            return
        split_dir = Path(file_paths[0]).parent
        shutil.rmtree(split_dir, ignore_errors=True)
