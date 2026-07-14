아키텍처
========

파이프라인
----------

:class:`base_processor.BaseProcessor`\ 가 4단계 파이프라인을 정의하고,
:class:`preprocessor.DocumentProcessor`\ 와 :class:`custom_preprocessor.DocumentProcessor`\ 는
둘 다 이를 상속해 ``__init__``\ 에서 ``loader``/``chunker``/``metadata_builder``\ 만
구성하고, 배포 맥락에 맞는 ``__call__``\ 만 각자 구현한다.

1. **파일 핸들링** (:meth:`~base_processor.BaseProcessor.file_handling`) -
   PDF가 ``max_page_split`` 페이지를 넘으면 여러 파일로 분할한다.
2. **로드** (:meth:`~base_processor.BaseProcessor.load`) - 확장자별 로더가
   텍스트를 줄 단위로 추출하고, 레이아웃 전략으로 카테고리를 매기고,
   필요하면 OCR로 대체한다. 결과는 ``{text, category, bbox, page}`` 아이템.
3. **청킹** (:meth:`~base_processor.BaseProcessor.chunking`) - 아이템을
   섹션/헤딩 기준으로 묶어 ``{text, i_page, e_page}`` 청크로 만든다.
4. **메타데이터** (:meth:`~base_processor.BaseProcessor.build_metadata`) -
   청크를 GenOS 서빙용 벡터 dict로 변환한다.

설정 기반 모듈 교체
-------------------

:class:`preprocessor.DocumentProcessor`\ 는 ``resource/config.yaml``\ 의
``type`` 값에 따라 각 단계의 구현체를 ``importlib``\ 로 동적 로드한다 (로더는
``ext.<확장자>``, 레이아웃은 ``layout.type``, OCR은 ``ocr.type``, 청커는
``chunker.type``). 새 전략을 추가하려면 해당 패키지 밑에 같은 인터페이스
(``Loader``/``Layout``/``Chunker`` 클래스, 같은 시그니처)를 구현한 모듈만
추가하면 되고, 다른 코드는 건드릴 필요가 없다.

이 동적 로딩 대신 조합을 코드에 고정해두고 싶다면 :doc:`custom_preprocessor`\ 를 참고.

OCR이 호출되는 조건
-------------------

:meth:`loader.base_loader.BaseLoader._needs_ocr`\ 가 ``ocr.mode``\ 에 따라 판단한다:

- ``force``: 모든 페이지를 무조건 OCR
- ``disable``: OCR을 아예 쓰지 않음(OCR 클라이언트 자체를 생성하지 않음)
- ``auto`` (기본값): 텍스트 레이어가 없는 페이지, 또는
  :func:`util.util.has_glyph_corruption`\ 로 감지된 글리프 손상 페이지만 OCR
