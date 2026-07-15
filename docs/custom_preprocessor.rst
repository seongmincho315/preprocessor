나만의 전처리기 만들기
========================

:class:`preprocessor.DocumentProcessor`\ 는 ``resource/config.yaml``\ 을 읽어서
로더/레이아웃/OCR/청커를 런타임에 갈아 끼우도록 만들어졌다. 하지만 특정 고객사
한 곳에만 배포한다면, 매번 yaml을 파싱하고 ``importlib``\ 로 모듈을 찾을 필요 없이
"이 조합으로 고정"해두는 편이 더 간단하고 예측 가능하다. 이 문서는
:mod:`custom_preprocessor`\ 를 처음부터 다시 만든다고 생각하고, 파이프라인
8단계(파일 핸들링 → 로더(레이아웃/OCR) → 전처리 → pre-Enrichment → 청킹 →
후처리 → post-Enrichment → 메타데이터) 각각에 어떤 구현체를 쓸지 하나씩
정하며 ``BaseProcessor``\ 를 상속해 나만의 전처리기를 만드는 법을 설명한다.

완성된 전체 코드는 다음과 같다 (아래 단계별 설명은 이 코드를 어떻게, 왜
이렇게 짰는지 하나씩 뜯어본다):

.. literalinclude:: ../facade/custom_preprocessor.py
   :language: python
   :linenos:

:class:`base_processor.BaseProcessor`\ 가 8단계 전부와, 이들을 순서대로
엮는 ``__call__(file_path)`` 자체를 이미 구현해뒀으므로, 서브클래스는
``__init__``\ 에서 각 단계가 쓸 구현체(``self.loader``/``self.chunker``/
``self.metadata_builder``)만 채우고, 스텁으로 남아있는 단계(전처리/
pre-Enrichment/후처리/post-Enrichment)는 필요할 때만 메서드를
오버라이드하면 된다.

파이프라인 단계별로 구현체 정하기
------------------------------------

여기서는 "영문 PDF, 레이아웃은 detr, 텍스트 없는 페이지만 paddle로 OCR,
섹션 단위로 청킹, GenOS로 서빙"을 예로 든다.

1. 파일 핸들링
~~~~~~~~~~~~~~~~

클래스 속성 ``max_page_split``\ 만 정하면 :meth:`~base_processor.BaseProcessor.file_handling`\
을 그대로 물려받아 쓴다:

.. code-block:: python

   class DocumentProcessor(BaseProcessor):
       max_page_split = 50

2. 로더 (레이아웃 / OCR)
~~~~~~~~~~~~~~~~~~~~~~~~~~

- 로더: :class:`loader.pdf.pymupdf.Loader` (PDF만 다루면 충분)
- 레이아웃: :class:`util.detr_layout.DetrLayout` (원격 RT-DETR 모델)
- OCR: :class:`util.paddle_ocr.PaddleOcr`, ``mode: auto`` (텍스트 없거나 글리프
  깨진 페이지만)

``config.yaml``\ /``resource/*.yaml`` 대신, 이 전처리기 전용 설정을 모듈
상수로 박아두고:

.. code-block:: python

   LAYOUT_CONFIG = {
       "type": "detr",
       "url": "http://localhost:30881",
       "image_dpi": 150,
       "timeout": 60,
   }
   OCR_CONFIG = {
       "type": "paddle",
       "url": "http://localhost:30880",
       "timeout": 60,
   }

``__init__``\ 에서 ``self.loader``\ 딕셔너리를 채운다:

.. code-block:: python

   def __init__(self):
       self.loader = {"pdf": PdfLoader(LAYOUT_CONFIG, OCR_CONFIG)}

.. note::
   ``self.loader``\ 가 PDF 하나만 다루는데도 딕셔너리(``{"pdf": ...}``)인 이유는
   :meth:`~base_processor.BaseProcessor.load`\ 가 확장자로 이 딕셔너리를
   찾아 쓰기 때문이다. 확장자를 늘리고 싶으면 이 딕셔너리에 항목만 추가하면 된다.

레이아웃/OCR을 config dict의 ``type`` 문자열로 분기시키는 대신 더 세밀하게
고정하고 싶다면, 로더를 상속해서 분기 자체를 없앨 수도 있다:

.. code-block:: python

   class CustomPdfLoader(PdfLoader):
       def get_layout(self):
           return DetrLayout(self.layout_config)

       def get_ocr(self):
           return PaddleOcr(self.ocr_config)

둘 다 실행 결과는 동일하다 - config의 ``type`` 문자열로 분기시킬지, 코드에서
클래스를 직접 지정할지의 차이일 뿐이다.

3. 전처리
~~~~~~~~~~~

:meth:`~base_processor.BaseProcessor.preprocess`\ 는 기본이 항등 함수라
``BaseProcessor``\ 로부터 그대로 물려받으면 아무것도 하지 않는다. 룰 기반
전처리(예: 띄어쓰기 보정)가 필요할 때만 오버라이드한다:

.. code-block:: python

   def preprocess(self, items):
       return [my_rule_based_fix(item) for item in items]

4. pre-Enrichment
~~~~~~~~~~~~~~~~~~~

:meth:`~base_processor.BaseProcessor.pre_enrich`\ 도 기본이 항등 함수다.
청킹 전 외부 모델로 아이템을 보강해야 할 때만 오버라이드한다:

.. code-block:: python

   def pre_enrich(self, items):
       return my_external_model_enrich(items)

5. 청킹
~~~~~~~~~

- 청커: :class:`chunker.smart_chunker.Chunker`

``__init__``\ 에서 ``self.chunker``\ 를 채운다:

.. code-block:: python

   def __init__(self):
       ...
       self.chunker = Chunker(chunk_size=1000, chunk_overlap=100)

6. 후처리
~~~~~~~~~~~

:meth:`~base_processor.BaseProcessor.postprocess`\ 도 기본이 항등 함수다.
청크 단위 후처리가 필요할 때만 오버라이드한다:

.. code-block:: python

   def postprocess(self, chunks):
       return [my_chunk_fix(chunk) for chunk in chunks]

7. post-Enrichment
~~~~~~~~~~~~~~~~~~~~

:meth:`~base_processor.BaseProcessor.post_enrich`\ 도 기본이 항등 함수다.
image_description/table_refiner처럼 외부 모델로 청크를 보강해야 할 때만
오버라이드한다:

.. code-block:: python

   def post_enrich(self, chunks):
       return my_external_model_enrich(chunks)

8. 메타데이터
~~~~~~~~~~~~~~~

- 메타데이터: :class:`metadata.genos.GenosMetadata`

``__init__``\ 에서 ``self.metadata_builder``\ 를 채운다:

.. code-block:: python

   def __init__(self):
       ...
       self.metadata_builder = GenosMetadata()

조립하고 실행하기
--------------------

위 8단계에서 정한 구현체를 한 클래스로 모으면 :class:`custom_preprocessor.DocumentProcessor`\
가 된다:

.. code-block:: python

   class DocumentProcessor(BaseProcessor):
       max_page_split = 50

       def __init__(self):
           self.loader = {"pdf": PdfLoader(LAYOUT_CONFIG, OCR_CONFIG)}
           self.chunker = Chunker(chunk_size=1000, chunk_overlap=100)
           self.metadata_builder = GenosMetadata()

:meth:`~base_processor.BaseProcessor.__call__`\ 은 동기 ``(file_path)``
시그니처로 8단계를 그대로 실행하는 구현체가 이미 있어서, 이 예제처럼 동기
호출이면 오버라이드할 필요가 없다. GenOS ``/run``\ 처럼 진입점 계약이
다를 때만(:class:`preprocessor.DocumentProcessor` 가 async + ``request``
인자를 받는 것처럼) 오버라이드한다:

.. code-block:: python

   async def __call__(self, request, file_path: str, **params):
       return super().__call__(file_path)

실행해본다:

.. code-block:: python

   processor = DocumentProcessor()
   vectors = processor("sample/pdf/long(eng)/Information Theory.pdf")
   print(len(vectors), "vectors")

완성된 코드는 :mod:`custom_preprocessor`\ 에 있다.

로더/청커/메타데이터를 직접 만들기
-------------------------------------

여기서 다룬 건 이미 있는 로더/청커/메타데이터를 조합하는 법이다. 각
컴포넌트를 처음부터 새로 만들려면 아래 문서를 참고:

.. toctree::
   :maxdepth: 1

   custom_loader
   custom_chunker
   custom_metadata

더 보기
-------

- 파이프라인 각 단계가 정확히 뭘 하는지는 :doc:`architecture`
- 클래스/함수 시그니처는 :doc:`api`
