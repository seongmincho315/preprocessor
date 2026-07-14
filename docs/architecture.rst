아키텍처
========

파이프라인
----------

:class:`preprocessor.DocumentProcessor`\ 는 4단계로 문서를 처리한다.

1. **파일 핸들링** (:meth:`preprocessor.DocumentProcessor.file_handling`) -
   PDF가 ``max_page_split`` 페이지를 넘으면 여러 파일로 분할한다.
2. **로드** (:meth:`preprocessor.DocumentProcessor.load`) - 확장자별 로더가
   텍스트를 줄 단위로 추출하고, 레이아웃 전략으로 카테고리를 매기고,
   필요하면 OCR로 대체한다. 결과는 ``{text, category, bbox, page}`` 아이템.
3. **청킹** (:meth:`preprocessor.DocumentProcessor.chunking`) - 아이템을
   섹션/헤딩 기준으로 묶어 ``{text, i_page, e_page}`` 청크로 만든다.
4. **메타데이터** (:meth:`preprocessor.DocumentProcessor.build_metadata`) -
   청크를 GenOS 서빙용 벡터 dict로 변환한다.

설정 기반 모듈 교체
-------------------

``resource/config.yaml``\ 의 ``type`` 값에 따라 각 단계의 구현체가
``importlib``\ 로 동적 로드된다:

.. list-table::
   :header-rows: 1

   * - 단계
     - config 키
     - 선택지
   * - 로더
     - ``ext.<확장자>``
     - :mod:`loader.pdf.pymupdf`, :mod:`loader.pdf.pypdf`, ...
   * - 레이아웃
     - ``layout.type``
     - ``rule`` (:class:`util.rule_layout.Layout`), ``detr`` (:class:`util.detr_layout.DetrLayout`)
   * - OCR
     - ``ocr.type``, ``ocr.mode``
     - ``paddle`` (:class:`util.paddle_ocr.PaddleOcr`); mode는 auto/force/disable
   * - 청커
     - ``chunker.type``
     - ``smart_chunker``, ``hierarchical_chunker``, ``hybrid_chunker``

새 전략을 추가하려면 해당 패키지 밑에 같은 인터페이스(``Loader``/``Layout``/
``Chunker`` 클래스, 같은 시그니처)를 구현한 모듈만 추가하면 되고, 다른 코드는
건드릴 필요가 없다.

직접 조립하는 예시
------------------

``config.yaml``\ 의 동적 로딩 대신, 조합을 코드에 고정해두고 싶을 때는
:mod:`custom_preprocessor`\ 처럼 각 클래스를 직접 import해서 조립하면 된다.
:class:`loader.base_loader.BaseLoader`\ 의 ``get_layout()``/``get_ocr()``\ 를
오버라이드하면 config의 ``type`` 문자열 분기 없이도 레이아웃/OCR 전략을
고정할 수 있다.

OCR이 호출되는 조건
-------------------

:meth:`loader.base_loader.BaseLoader._needs_ocr`\ 가 ``ocr.mode``\ 에 따라 판단한다:

- ``force``: 모든 페이지를 무조건 OCR
- ``disable``: OCR을 아예 쓰지 않음(OCR 클라이언트 자체를 생성하지 않음)
- ``auto`` (기본값): 텍스트 레이어가 없는 페이지, 또는
  :func:`util.util.has_glyph_corruption`\ 로 감지된 글리프 손상 페이지만 OCR
