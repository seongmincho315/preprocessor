메타데이터
============

``config.yaml``\ 로는 선택할 수 없다. :class:`preprocessor.DocumentProcessor`\
의 ``__init__``\ 이 ``importlib.import_module("metadata.genos").GenosMetadata()``\
로 코드에 고정해뒀기 때문이다. 다른 메타데이터 빌더가 필요하면
:doc:`custom_metadata`\ 처럼 직접 서브클래스에서 ``self.metadata_builder``\
를 교체해야 한다.

더 보기
-------

- 처음부터 직접 만드는 법은 :doc:`custom_metadata`
- yaml 조합 개요는 :doc:`facade_usage`
- 각 단계가 내부적으로 정확히 뭘 하는지는 :doc:`architecture`
