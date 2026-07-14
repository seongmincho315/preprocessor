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

각 키가 결정하는 것
---------------------

``max_page_split``
   PDF가 이 페이지 수를 넘으면 여러 파일로 잘라서 처리한다
   (:meth:`~base_processor.BaseProcessor.file_handling`).

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

``ext.<확장자>``
   확장자별로 쓸 로더 모듈 이름. ``loader.<확장자>.<이름>``\ (예:
   ``loader.pdf.pymupdf``)을 먼저 찾고, 없으면 ``converter.<이름>``\ (예:
   ``converter.libreoffice``\ 로 pdf 변환 후 로드)으로 대체한다. 둘 다 없으면
   그 확장자는 건너뛴다.

``chunker.type`` / ``chunk_size`` / ``over_lap``
   ``chunker.<type>`` 모듈의 ``Chunker`` 클래스를
   ``Chunker(chunk_size, chunk_overlap)``\ 로 생성한다. 선택지는
   ``smart_chunker``\ (기본, section_header 경계 기준)/``hierarchical_chunker``\
   (병합·분할 없음)/``hybrid_chunker``\ (헤딩 단위 병합 후 분할).

실행해본다
-----------

.. code-block:: python

   import sys
   sys.path.insert(0, "facade")

   from preprocessor import DocumentProcessor

   processor = DocumentProcessor()  # resource/config.yaml을 읽어 조립
   file_paths = processor.file_handling("sample/pdf/long(eng)/Information Theory.pdf")
   items = processor.load(file_paths)
   chunks = processor.chunking(items)
   vectors = processor.build_metadata(chunks, file_paths[0])

``chunker.type``\ 이나 ``ext.pdf``\ 값만 바꿔서 다시 실행해보면 코드 변경
없이 조합이 바뀌는 걸 바로 확인할 수 있다.

더 보기
-------

- 각 단계가 내부적으로 정확히 뭘 하는지는 :doc:`architecture`
- 이 yaml 조합 대신 코드에 고정하고 싶다면 :doc:`custom_preprocessor`
- 클래스/함수 시그니처는 :doc:`api`
