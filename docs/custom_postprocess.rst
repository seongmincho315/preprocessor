나만의 후처리 만들기
========================

후처리는 :meth:`~base_processor.BaseProcessor.postprocess` 가 청킹 직후,
메타데이터 변환 전에 :meth:`~base_processor.BaseProcessor.chunking` 이
만든 ``{text, i_page, e_page}`` 청크 목록에 청크 단위로 적용하는 룰
기반 정리 단계다(빈 청크 제거, 경계 공백 정리 등). 전처리와 마찬가지로
base class가 없다 - 기본이 항등 함수라, 필요한 서브클래스만 이 메서드
하나를 오버라이드하면 된다.

.. note::
   외부 모델을 불러 청크를 보강하는 단계(image_description, table_refiner
   등)는 바로 다음 단계인 :meth:`~base_processor.BaseProcessor.post_enrich`
   다. 규칙으로 되는 정리는 ``postprocess``, 모델 호출이 필요한 보강은
   ``post_enrich`` 로 나눠서 넣는다.

1. 기존 계약 확인하기
------------------------

.. literalinclude:: ../facade/base_processor.py
   :language: python
   :pyobject: BaseProcessor.postprocess

확인할 계약은 딱 하나다: ``postprocess(self, chunks: List[dict]) ->
List[dict]``. 입력/출력 모두 ``{text, i_page, e_page}`` 청크 목록이고,
목록 길이를 바꿔도 된다(예: 빈 청크를 걸러내면 개수가 줄어든다).

2. 새 후처리 로직을 만든다
------------------------------

예를 들어 청킹 과정에서 생긴 빈 청크를 버리고, 각 청크 앞뒤 공백을
정리한다면:

.. code-block:: python

   from typing import List


   def drop_empty_and_trim(chunks: List[dict]) -> List[dict]:
       return [
           {**chunk, "text": chunk["text"].strip()}
           for chunk in chunks
           if chunk["text"].strip()
       ]

여러 규칙을 조합해야 하면 함수를 여러 개로 나누고
``drop_empty_and_trim`` 처럼 하나의 진입점 안에서 순서대로 적용하면
된다.

3. DocumentProcessor에 연결한다
-----------------------------------

:doc:`custom_preprocessor` 와 같은 패턴으로, ``BaseProcessor`` 를 상속한
전용 ``DocumentProcessor`` 에서 ``postprocess`` 를 오버라이드한다. 앞서
2단계에서 만든 ``drop_empty_and_trim`` 을 그대로 가져와서:

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

       def postprocess(self, chunks):
           return drop_empty_and_trim(chunks)

       # __call__(file_path) -> List[dict] 은 base_processor.BaseProcessor 의
       # 구현을 그대로 쓴다 - 동기 (file_path) 진입점이면 오버라이드할 필요가 없다.

로더/청커/메타데이터는 :doc:`custom_preprocessor` 의 조합을 그대로
가져다 썼다 - 파이프라인의 각 단계는 서로 독립적으로 갈아 끼울 수 있다.

4. 테스트한다
--------------

``tests/unit/test_base_processor.py`` 처럼, 실제 파일 없이 청크 dict
목록을 직접 만들어 ``postprocess`` 를 호출하고 반환된 목록을 검증하면
된다(``pytest.mark.unit``):

.. code-block:: python

   def test_drop_empty_and_trim_removes_blank_chunks():
       chunks = [
           {"text": "  본문  ", "i_page": 0, "e_page": 0},
           {"text": "   ", "i_page": 1, "e_page": 1},
       ]

       result = drop_empty_and_trim(chunks)

       assert result == [{"text": "본문", "i_page": 0, "e_page": 0}]

더 보기
-------

- 파이프라인 각 단계가 정확히 뭘 하는지는 :doc:`architecture`
- 조합 자체를 코드에 고정하는 법은 :doc:`custom_preprocessor`
- yaml로 조합을 바꾸는 법은 :doc:`facade_usage`
