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
``BaseProcessor``\ 를 상속한 전용 서브클래스가 필요하다.

1. 파일 핸들링
~~~~~~~~~~~~~~~~

``max_page_split``
   PDF가 이 페이지 수를 넘으면 여러 파일로 잘라서 처리한다
   (:meth:`~base_processor.BaseProcessor.file_handling`).

2. 로더 (레이아웃 / OCR)
~~~~~~~~~~~~~~~~~~~~~~~~~~

``ext.<확장자>``
   확장자별로 쓸 로더 모듈 이름. ``loader.<확장자>.<이름>``\ (예:
   ``loader.pdf.pymupdf``)을 먼저 찾고, 없으면 ``converter.<이름>``\ (예:
   ``converter.libreoffice``\ 로 pdf 변환 후 로드)으로 대체한다. 둘 다 없으면
   그 확장자는 건너뛴다.

``layout.type`` (``rule`` | ``detr`` | ``dots_mocr``)
   페이지 줄마다 카테고리(``section_header`` 등)를 매기는 전략.
   ``rule``\ 이 아니면 ``resource/<type>.yaml``\ (예: ``detr.yaml``)을 함께
   읽어 ``url``/``image_dpi``/``timeout`` 등 세부 설정과 병합한다.

``ocr.type`` / ``ocr.mode`` (``auto`` | ``force`` | ``disable``)
   ``type: paddle``\ 이면 ``resource/paddle.yaml``\ 을 병합해 OCR 클라이언트를
   만든다. ``mode``\ 는 :meth:`loader.base_loader.BaseLoader._needs_ocr`\ 가
   페이지마다 OCR을 실제로 호출할지 판단하는 기준이다 - ``auto``\ 는 텍스트
   레이어가 없거나 글리프가 깨진 페이지만, ``force``\ 는 전부, ``disable``\ 은
   전혀 호출하지 않는다.

3. 전처리
~~~~~~~~~~~

``config.yaml``\ 에 해당하는 키가 없다. :meth:`~base_processor.BaseProcessor.preprocess`\
는 기본이 항등 함수(입력을 그대로 반환)라, 룰 기반 전처리(예: 띄어쓰기
보정)가 필요해지면 yaml 조합이 아니라 :doc:`custom_preprocessor`\ 처럼
서브클래스를 만들어 이 메서드를 오버라이드해야 한다.

4. pre-Enrichment
~~~~~~~~~~~~~~~~~~~

마찬가지로 ``config.yaml``\ 키가 없다. :meth:`~base_processor.BaseProcessor.pre_enrich`\
도 기본이 항등 함수라, 외부 모델 기반 아이템 보강이 필요하면
:doc:`custom_preprocessor`\ 처럼 서브클래스에서 오버라이드한다.

5. 청킹
~~~~~~~~~

``chunker.type`` / ``chunk_size`` / ``over_lap``
   ``chunker.<type>`` 모듈의 ``Chunker`` 클래스를
   ``Chunker(chunk_size, chunk_overlap)``\ 로 생성한다. 선택지는
   ``smart_chunker``\ (기본, section_header 경계 기준)/``hierarchical_chunker``\
   (병합·분할 없음)/``hybrid_chunker``\ (헤딩 단위 병합 후 분할).

6. 후처리
~~~~~~~~~~~

``config.yaml``\ 에 해당하는 키가 없다. :meth:`~base_processor.BaseProcessor.postprocess`\
도 기본이 항등 함수라, 청크 단위 후처리가 필요하면 :doc:`custom_preprocessor`\
처럼 서브클래스에서 오버라이드한다.

7. post-Enrichment
~~~~~~~~~~~~~~~~~~~~

``config.yaml``\ 에 해당하는 키가 없다. :meth:`~base_processor.BaseProcessor.post_enrich`\
도 기본이 항등 함수다. image_description/table_refiner 등 외부 모델 기반
청크 보강이 필요하면 :doc:`custom_preprocessor`\ 처럼 서브클래스에서
오버라이드한다.

8. 메타데이터
~~~~~~~~~~~~~~~

``config.yaml``\ 로는 선택할 수 없다. :class:`preprocessor.DocumentProcessor`\
의 ``__init__``\ 이 ``importlib.import_module("metadata.genos").GenosMetadata()``\
로 코드에 고정해뒀기 때문이다. 다른 메타데이터 빌더가 필요하면
:doc:`custom_metadata`\ 처럼 직접 서브클래스에서 ``self.metadata_builder``\
를 교체해야 한다.

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
