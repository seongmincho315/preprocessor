나만의 전처리 만들기
========================

전처리는 :meth:`~base_processor.BaseProcessor.preprocess` 가 청킹 직전,
:meth:`~base_processor.BaseProcessor.load` 가 만든 ``{text, category, bbox,
page}`` 아이템 목록에 아이템 단위로 적용하는 룰 기반 보정 단계다(띄어쓰기
보정, 사전 치환 등). 로더/청커와 달리 base class가 없다 - 기본이 항등
함수(입력을 그대로 반환)라, 필요한 서브클래스만 이 메서드 하나를
오버라이드하면 된다.

.. note::
   외부 모델을 불러 아이템을 보강하는 단계는 바로 다음 단계인
   :meth:`~base_processor.BaseProcessor.pre_enrich` 다. 규칙(정규식,
   사전 등)으로 되는 보정은 ``preprocess``, 모델 호출이 필요한 보강은
   ``pre_enrich`` 로 나눠서 넣는다.

1. 기존 계약 확인하기
------------------------

.. literalinclude:: ../facade/base_processor.py
   :language: python
   :pyobject: BaseProcessor.preprocess

확인할 계약은 딱 하나다: ``preprocess(self, items: List[dict]) ->
List[dict]``. 입력/출력 모두 ``{text, category, bbox, page}`` 아이템
목록이고, 목록 길이나 아이템 개수를 바꿔도 된다(예: 빈 텍스트 아이템을
걸러내기).

2. 새 전처리 로직을 만든다
------------------------------

예를 들어 한글 문서에서 흔한 붙어 쓴 조사를 띄어 쓰는 규칙 하나만
적용한다면:

.. code-block:: python

   import re
   from typing import List


   def fix_spacing(text: str) -> str:
       return re.sub(r"(\S)(은|는|이|가|을|를)(\s)", r"\1 \2\3", text)


   def my_rule_based_preprocess(items: List[dict]) -> List[dict]:
       return [{**item, "text": fix_spacing(item["text"])} for item in items]

여러 규칙을 조합해야 하면 함수를 여러 개로 나누고
``my_rule_based_preprocess`` 안에서 순서대로 적용하면 된다 - 규칙마다
별도 헬퍼로 쪼개두면 3단계에서 다시 조합하기 쉽다.

3. DocumentProcessor에 연결한다
-----------------------------------

:doc:`custom_preprocessor` 와 같은 패턴으로, ``BaseProcessor`` 를 상속한
전용 ``DocumentProcessor`` 에서 ``preprocess`` 를 오버라이드한다. 앞서
2단계에서 만든 ``my_rule_based_preprocess`` 를 그대로 가져와서:

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

       def preprocess(self, items):
           return my_rule_based_preprocess(items)

       # __call__(file_path) -> List[dict] 은 base_processor.BaseProcessor 의
       # 구현을 그대로 쓴다 - 동기 (file_path) 진입점이면 오버라이드할 필요가 없다.

로더/청커/메타데이터는 :doc:`custom_preprocessor` 의 조합을 그대로
가져다 썼다 - 파이프라인의 각 단계는 서로 독립적으로 갈아 끼울 수 있다.

4. 테스트한다
--------------

``tests/unit/test_base_processor.py`` 처럼, 실제 파일 없이 아이템 dict
목록을 직접 만들어 ``preprocess`` 를 호출하고 반환된 텍스트를
검증하면 된다(``pytest.mark.unit``):

.. code-block:: python

   def test_fix_spacing_splits_particle():
       items = [{"text": "문서를전처리한다", "category": None, "bbox": None, "page": 0}]

       result = my_rule_based_preprocess(items)

       assert result[0]["text"] == "문서를 전처리한다"

더 보기
-------

- 파이프라인 각 단계가 정확히 뭘 하는지는 :doc:`architecture`
- 조합 자체를 코드에 고정하는 법은 :doc:`custom_preprocessor`
- yaml로 조합을 바꾸는 법은 :doc:`facade_usage`
