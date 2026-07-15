로더 (레이아웃 / OCR)
========================

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

더 보기
-------

- yaml 조합 개요는 :doc:`facade_usage`
- 새 확장자/레이아웃/OCR 구현체를 직접 만드는 법은 :doc:`custom_loader`
- 각 단계가 내부적으로 정확히 뭘 하는지는 :doc:`architecture`
