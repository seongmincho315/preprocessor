"""청킹 전략 모음. 각 모듈은 같은 시그니처(``Chunker(chunk_size, chunk_overlap)``,
``__call__(items) -> List[dict]``)의 ``Chunker`` 클래스를 제공하며,
``config.yaml`` 의 ``chunker.type`` 으로 선택된다."""
