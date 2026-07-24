"""GenOS 문서 전처리기의 파사드.

``resource/config.yaml`` 설정에 따라 확장자별 로더, 레이아웃/OCR 전략, 청커,
메타데이터 빌더를 동적으로 구성하고, :class:`base_processor.BaseProcessor` 가
정의하는 파일 핸들링 -> 로드 -> 전처리/보강 -> 청킹 -> 후처리/보강 -> 메타데이터
파이프라인을 :class:`DocumentProcessor` 하나로 노출한다.
"""

import importlib
from pathlib import Path

import yaml
from base_processor import BaseProcessor

CONFIG_PATH = Path(__file__).parent / "resource" / "config.yaml"


class DocumentProcessor(BaseProcessor):
    """``config.yaml`` 에 설정된 조합으로 문서 하나를 파싱해 GenOS 벡터 메타데이터로 만든다.

    파이프라인 8단계(:meth:`~base_processor.BaseProcessor.file_handling`,
    :meth:`~base_processor.BaseProcessor.load`,
    :meth:`~base_processor.BaseProcessor.preprocess`,
    :meth:`~base_processor.BaseProcessor.pre_enrich`,
    :meth:`~base_processor.BaseProcessor.chunking`,
    :meth:`~base_processor.BaseProcessor.postprocess`,
    :meth:`~base_processor.BaseProcessor.post_enrich`,
    :meth:`~base_processor.BaseProcessor.build_metadata`, 그리고 ``__call__``
    자체)는 :class:`base_processor.BaseProcessor` 로부터 그대로 물려받고, 이
    클래스는 ``config.yaml`` 을 읽어 로더/청커/메타데이터 빌더를 구성하고
    GenOS ``/run`` 의 async 시그니처만 얹는 역할을 한다.

    Attributes:
        max_page_split (int): 이 페이지 수를 넘으면 파일을 분할한다.
        loader (dict[str, BaseLoader]): 확장자 -> 로더 인스턴스.
        chunker: ``config.yaml`` 의 ``chunker.type`` 으로 선택된 청커 인스턴스.
        metadata_builder: GenOS 메타데이터 빌더 인스턴스.
    """

    def __init__(self):
        """``resource/config.yaml`` 을 읽어 로더/청커/메타데이터 빌더를 초기화한다."""
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

        # table_structure.type이 있으면 resource/<type>.yaml을 읽어 layout_config에 병합한다
        # (현재 detr 전용 보강 기능 - DetrLayout이 layout_config["table_structure"]를 읽는다).
        table_structure_config = dict(config.get("table_structure") or {})
        table_structure_type = table_structure_config.get("type")
        if table_structure_type:
            strategy_path = CONFIG_PATH.parent / f"{table_structure_type}.yaml"
            if strategy_path.exists():
                with open(strategy_path, encoding="utf-8") as f:
                    table_structure_config.update(yaml.safe_load(f) or {})
            layout_config["table_structure"] = table_structure_config

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

    async def __call__(self, request, file_path: str, **params):
        """GenOS ``/run`` 이 요구하는 async 시그니처(``request``/``**params`` 포함)만
        감싸고, 실제 흐름은 :meth:`~base_processor.BaseProcessor.__call__` 이
        그대로 수행한다.

        Args:
            request: GenOS ``/run`` 요청 객체(현재 구현에서는 사용하지 않음).
            file_path: 처리할 원본 파일 경로.
            **params: 확장 파라미터(현재 구현에서는 사용하지 않음).

        Returns:
            :meth:`~base_processor.BaseProcessor.build_metadata` 가 반환한 벡터 dict 목록.
        """
        # file_handling -> load -> preprocess -> pre_enrich -> chunking -> postprocess -> post_enrich -> build_metadata
        return super().__call__(file_path)
