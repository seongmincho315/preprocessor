facade 사용법 (yaml 기반)
==========================

:class:`preprocessor.DocumentProcessor`\ 는 GenOS에 배포될 때 쓰는 기본
파사드다. ``resource/config.yaml``\ 하나만 고쳐서 로더/레이아웃/OCR/청커
조합을 코드 수정 없이 바꿀 수 있다.

config.yaml 전체 구조
-----------------------

.. literalinclude:: ../facade/resource/config.yaml
   :language: yaml

이 값들이 그대로 :class:`preprocessor.DocumentProcessor`\ 의 ``__init__``\ 에서
읽혀 각 단계 구현체를 조립한다.

파이프라인 단계별 설정
-------------------------

파일 핸들링 → 로더(레이아웃/OCR) → 전처리 → pre-Enrichment → 청킹 →
후처리 → post-Enrichment → 메타데이터, 8단계 중 ``config.yaml``\ 로
실제로 갈아 끼울 수 있는 건 파일 핸들링/로더/청킹 셋뿐이다. 전처리/
pre-Enrichment/후처리/post-Enrichment는 기본이 항등 함수(스텁)라 yaml
키가 없고, 메타데이터는 :class:`preprocessor.DocumentProcessor`\ 코드에
:class:`metadata.genos.GenosMetadata`\ 로 고정돼 있어 역시 yaml로는
못 바꾼다 - 이 네 단계를 바꾸려면 :doc:`custom_preprocessor`\ 처럼
``BaseProcessor``\ 를 상속한 전용 서브클래스가 필요하다. 단계별 설정/제약은
아래 문서를 참고(파이프라인 순서대로):

.. toctree::
   :maxdepth: 1

   facade_file_handling
   facade_loader
   facade_preprocess
   facade_pre_enrich
   facade_chunking
   facade_postprocess
   facade_post_enrich
   facade_metadata

실행해본다
-----------

.. code-block:: python

   import sys
   sys.path.insert(0, "facade")

   from preprocessor import DocumentProcessor

   processor = DocumentProcessor()  # resource/config.yaml을 읽어 조립
   file_paths = processor.file_handling("sample/pdf/long(eng)/Information Theory.pdf")
   items = processor.load(file_paths)
   items = processor.pre_enrich(processor.preprocess(items))  # 기본은 항등 함수(스텁)
   chunks = processor.chunking(items)
   chunks = processor.post_enrich(processor.postprocess(chunks))  # 기본은 항등 함수(스텁)
   vectors = processor.build_metadata(chunks, file_paths[0])

``chunker.type``\ 이나 ``ext.pdf``\ 값만 바꿔서 다시 실행해보면 코드 변경
없이 조합이 바뀌는 걸 바로 확인할 수 있다.

더 보기
-------

- 각 단계가 내부적으로 정확히 뭘 하는지는 :doc:`architecture`
- 이 yaml 조합 대신 코드에 고정하고 싶다면 :doc:`custom_preprocessor`
- 클래스/함수 시그니처는 :doc:`api`
