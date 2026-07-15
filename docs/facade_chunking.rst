청킹
======

``chunker.type`` / ``chunk_size`` / ``over_lap``
   ``chunker.<type>`` 모듈의 ``Chunker`` 클래스를
   ``Chunker(chunk_size, chunk_overlap)``\ 로 생성한다. 선택지는
   ``smart_chunker``\ (기본, section_header 경계 기준)/``hierarchical_chunker``\
   (병합·분할 없음)/``hybrid_chunker``\ (헤딩 단위 병합 후 분할).

더 보기
-------

- yaml 조합 개요는 :doc:`facade_usage`
- 새 청커를 직접 만드는 법은 :doc:`custom_chunker`
- 각 단계가 내부적으로 정확히 뭘 하는지는 :doc:`architecture`
