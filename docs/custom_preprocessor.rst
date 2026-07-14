나만의 전처리기 만들기
========================

:class:`preprocessor.DocumentProcessor`\ 는 ``resource/config.yaml``\ 을 읽어서
로더/레이아웃/OCR/청커를 런타임에 갈아 끼우도록 만들어졌다. 하지만 특정 고객사
한 곳에만 배포한다면, 매번 yaml을 파싱하고 ``importlib``\ 로 모듈을 찾을 필요 없이
"이 조합으로 고정"해두는 편이 더 간단하고 예측 가능하다. 이 문서는
:mod:`custom_preprocessor`\ 를 처음부터 다시 만든다고 생각하고, 한 단계씩 따라가며
``BaseProcessor``\ 를 상속해 나만의 전처리기를 만드는 법을 설명한다.

완성된 전체 코드는 다음과 같다 (아래 단계별 설명은 이 코드를 어떻게, 왜
이렇게 짰는지 하나씩 뜯어본다):

.. literalinclude:: ../facade/custom_preprocessor.py
   :language: python
   :linenos:

1. 조합을 정한다
-----------------

먼저 이 전처리기가 다룰 문서 종류와, 각 단계에 어떤 구현체를 쓸지 정한다.
여기서는 "영문 PDF, 레이아웃은 detr, 텍스트 없는 페이지만 paddle로 OCR,
섹션 단위로 청킹, GenOS로 서빙"을 예로 든다.

- 로더: :class:`loader.pdf.pymupdf.Loader` (PDF만 다루면 충분)
- 레이아웃: :class:`util.detr_layout.DetrLayout` (원격 RT-DETR 모델)
- OCR: :class:`util.paddle_ocr.PaddleOcr`, ``mode: auto`` (텍스트 없거나 글리프
  깨진 페이지만)
- 청커: :class:`chunker.smart_chunker.Chunker`
- 메타데이터: :class:`metadata.genos.GenosMetadata`

2. 레이아웃/OCR 설정을 코드에 고정한다
---------------------------------------

``config.yaml``\ /``resource/*.yaml`` 대신, 이 전처리기 전용 설정을 모듈
상수로 박아둔다:

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

3. BaseProcessor를 상속하고 조합을 구성한다
---------------------------------------------

:class:`base_processor.BaseProcessor`\ 가 ``file_handling``/``load``/``chunking``/
``build_metadata``\ 를 이미 구현해뒀으므로, 서브클래스는 ``__init__``\ 에서
``self.loader``/``self.chunker``/``self.metadata_builder``\ 만 채우면 된다.

.. code-block:: python

   class DocumentProcessor(BaseProcessor):
       max_page_split = 50

       def __init__(self):
           self.loader = {"pdf": PdfLoader(LAYOUT_CONFIG, OCR_CONFIG)}
           self.chunker = Chunker(chunk_size=1000, chunk_overlap=100)
           self.metadata_builder = GenosMetadata()

.. note::
   ``self.loader``\ 가 PDF 하나만 다루는데도 딕셔너리(``{"pdf": ...}``)인 이유는
   :meth:`~base_processor.BaseProcessor.load`\ 가 확장자로 이 딕셔너리를
   찾아 쓰기 때문이다. 확장자를 늘리고 싶으면 이 딕셔너리에 항목만 추가하면 된다.

4. __call__을 구현한다
------------------------

:meth:`~base_processor.BaseProcessor.__call__`\ 은 배포 맥락마다 진입점
계약이 달라서(GenOS ``/run``\ 은 async + ``request`` 인자가 필요하지만, 이
예제는 그럴 필요가 없다) ``BaseProcessor``\ 가 추상 메서드로 남겨뒀다.
오버라이드하지 않으면 인스턴스화 시점에 ``TypeError``\ 가 난다.

.. code-block:: python

   def __call__(self, file_path: str) -> List[dict]:
       file_paths = self.file_handling(file_path)
       try:
           items = self.load(file_paths)
           chunks = self.chunking(items)
           return self.build_metadata(chunks)
       finally:
           self._cleanup_split_files(file_path, file_paths)

5. (선택) 레이아웃/OCR을 더 세밀하게 고정하고 싶다면
-------------------------------------------------------

위 3단계처럼 ``config`` dict의 ``type`` 값으로 :class:`loader.base_loader.BaseLoader`\ 의
내장 분기(``get_layout()``/``get_ocr()``)를 타는 대신, 로더를 상속해서 아예
분기 자체를 없앨 수도 있다:

.. code-block:: python

   class CustomPdfLoader(PdfLoader):
       def get_layout(self):
           return DetrLayout(self.layout_config)

       def get_ocr(self):
           return PaddleOcr(self.ocr_config)

둘 다 실행 결과는 동일하다 — config의 ``type`` 문자열로 분기시킬지, 코드에서
클래스를 직접 지정할지의 차이일 뿐이다.

6. 실행해본다
--------------

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
