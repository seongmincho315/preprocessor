doc-parser-preprocessor
========================

GenOS 문서 전처리기. 파일 핸들링 -> 로더(레이아웃/OCR) -> 전처리/보강 -> 청킹
-> 후처리/보강 -> 메타데이터 순으로 이어지는 파이프라인을, 확장자/전략별로
갈아 끼울 수 있는 모듈로 구성했다.

파이프라인
----------

:class:`base_processor.BaseProcessor`\ 가 정의하는 8단계와, 이를 순서대로
엮는 ``__call__`` 자체를 모든 ``DocumentProcessor``\ (:class:`preprocessor.DocumentProcessor`\ ,
:class:`custom_preprocessor.DocumentProcessor`\ )가 공유한다:

1. **파일 핸들링** - PDF가 ``max_page_split``\ (기본 50) 페이지를 넘으면
   여러 파일로 분할한다.
2. **로더** (:class:`loader.base_loader.BaseLoader`\ ) - 확장자별로 지정된
   로더(``ext.<확장자>``\ , 예: ``loader.pdf.pymupdf``\ )가 페이지 텍스트를
   추출하고, 레이아웃 전략(``layout.type``\ : rule/detr)으로 줄마다
   카테고리를 매기고, 필요하면 OCR(``ocr.type: paddle``\ )로 대체한다.
   결과: ``{text, category, bbox, page}`` 아이템 목록.
3. **전처리**/**pre-Enrichment** - 룰 기반 전처리와 외부 모델 기반 보강.
   청킹 전, 아이템 단위로 적용된다. 기본은 둘 다 항등 함수(아무것도 하지
   않고 그대로 반환).
4. **청킹** (:class:`chunker.base_chunker.BaseChunker`\ ) - ``chunker.type``\
   으로 선택된 ``smart_chunker``\ /``hierarchical_chunker``\ /``hybrid_chunker``\
   중 하나가 아이템을 청크로 묶는다. 결과: ``{text, i_page, e_page}`` 청크
   목록.
5. **후처리**/**post-Enrichment** - 청크 단위 후처리와 외부 모델 기반
   보강(예: image_description, table_refiner). 메타데이터 변환 전에
   적용된다. 기본은 둘 다 항등 함수.
6. **메타데이터** (:class:`metadata.genos.GenosMetadata`\ ) - 청크를 GenOS
   Weaviate 컬렉션 스키마에 맞는 벡터 dict 목록으로 변환한다.

로더/청커/메타데이터는 ``resource/config.yaml``\ 의 설정값에 따라 런타임에
갈아 끼워지고, 전처리/보강 단계는 지금은 스텁이라 서브클래스가 필요할 때만
오버라이드한다. yaml로 조합만 바꾸는 법은 :doc:`facade_usage`\ , 단계별
흐름은 :doc:`architecture`\ , 조합을 코드에 고정하는 법은
:doc:`custom_preprocessor`\ 를 참고.

.. toctree::
   :maxdepth: 3
   :caption: 목차

   getting_started
   facade_usage
   custom_preprocessor
   architecture
   api

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
