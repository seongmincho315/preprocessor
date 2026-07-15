나만의 post-Enrichment 만들기
=================================

post-Enrichment는 :meth:`~base_processor.BaseProcessor.post_enrich` 가
:meth:`~base_processor.BaseProcessor.postprocess` 직후, 메타데이터 변환
직전에 청크 단위로 적용하는 외부 모델 기반 보강 단계다(예:
image_description, table_refiner). :doc:`custom_postprocess` 의 룰 기반
정리와 짝을 이루는데, 차이는 딱 하나 - 규칙으로 되는 건 ``postprocess``,
모델을 호출해야 하는 건 ``post_enrich`` 다. 기본이 항등 함수라, 필요한
서브클래스만 이 메서드 하나를 오버라이드하면 된다.

1. 기존 계약 확인하기
------------------------

.. literalinclude:: ../facade/base_processor.py
   :language: python
   :pyobject: BaseProcessor.post_enrich

확인할 계약은 딱 하나다: ``post_enrich(self, chunks: List[dict]) ->
List[dict]``. 입력/출력 모두 ``{text, i_page, e_page}`` 청크 목록이다.

2. 새 보강 로직을 만든다
------------------------------

예를 들어 청크에 포함된 표를 외부 table_refiner 모델로 정리해서 텍스트에
덧붙인다면:

.. code-block:: python

   from typing import List

   import requests


   def call_table_refiner(text: str) -> str:
       resp = requests.post(
           "http://localhost:30883/refine-table",
           json={"text": text},
           timeout=60,
       )
       resp.raise_for_status()
       return resp.json()["refined_text"]


   def my_external_model_enrich(chunks: List[dict]) -> List[dict]:
       return [{**chunk, "text": call_table_refiner(chunk["text"])} for chunk in chunks]

3. DocumentProcessor에 연결한다
-----------------------------------

:doc:`custom_preprocessor` 와 같은 패턴으로, ``BaseProcessor`` 를 상속한
전용 ``DocumentProcessor`` 에서 ``post_enrich`` 를 오버라이드한다. 앞서
2단계에서 만든 ``my_external_model_enrich`` 를 그대로 가져와서:

.. code-block:: python

   from base_processor import BaseProcessor
   from chunker.smart_chunker import Chunker
   from loader.pdf.pymupdf import Loader as PdfLoader
   from metadata.genos import GenosMetadata

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


   class DocumentProcessor(BaseProcessor):
       max_page_split = 50

       def __init__(self):
           self.loader = {"pdf": PdfLoader(LAYOUT_CONFIG, OCR_CONFIG)}
           self.chunker = Chunker(chunk_size=1000, chunk_overlap=100)
           self.metadata_builder = GenosMetadata()

       def post_enrich(self, chunks):
           return my_external_model_enrich(chunks)

       # __call__(file_path) -> List[dict] 은 base_processor.BaseProcessor 의
       # 구현을 그대로 쓴다 - 동기 (file_path) 진입점이면 오버라이드할 필요가 없다.

로더/청커/메타데이터는 :doc:`custom_preprocessor` 의 조합을 그대로
가져다 썼다 - 파이프라인의 각 단계는 서로 독립적으로 갈아 끼울 수 있다.

4. 테스트한다
--------------

``tests/unit/test_base_processor.py`` 처럼, 실제 모델 서버 없이
``call_table_refiner`` 를 목(mock)으로 대체해 ``post_enrich`` 오케스트레이션만
검증하면 된다(``pytest.mark.unit``). 실제 모델 서버까지 띄워 붙여보는
검증은 ``pytest.mark.integration`` 으로 분리한다.

더 보기
-------

- 파이프라인 각 단계가 정확히 뭘 하는지는 :doc:`architecture`
- 룰 기반 정리는 :doc:`custom_postprocess`
- 조합 자체를 코드에 고정하는 법은 :doc:`custom_preprocessor`
- yaml로 조합을 바꾸는 법은 :doc:`facade_usage`
