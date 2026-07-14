나만의 청커 만들기
========================

청커는 :meth:`~base_processor.BaseProcessor.chunking` 이 호출하는, 로더가
반환한 ``{text, category, bbox, page}`` 아이템 목록을 ``{text, i_page,
e_page}`` 청크 목록으로 바꾸는 컴포넌트다. ``smart_chunker``/``hierarchical_chunker``/
``hybrid_chunker`` 셋 다 :class:`chunker.base_chunker.BaseChunker` 를 상속하며,
``config.yaml`` 의 ``chunker.type`` 값으로 선택된다.

1. BaseChunker가 이미 해주는 것
---------------------------------

:class:`~chunker.base_chunker.BaseChunker` 는 서브클래스가 매번 새로 짤
필요 없는 세 가지를 이미 구현해뒀다:

- ``__init__(chunk_size, chunk_overlap)`` - 두 값을 ``self`` 에 저장. 대부분의
  청커는 이 시그니처 그대로 쓰면 되므로 오버라이드할 필요가 없다.
- :meth:`~chunker.base_chunker.BaseChunker._render` - heading과 본문
  텍스트를 ``", "`` 로 합친다(heading이 없으면 본문만).
- :meth:`~chunker.base_chunker.BaseChunker._split_text` - 텍스트를
  ``chunk_size`` 문자 단위로, ``chunk_overlap`` 만큼 겹치게 슬라이딩 윈도우
  분할한다.

서브클래스가 반드시 구현해야 하는 건 :meth:`~chunker.base_chunker.BaseChunker.__call__`
하나뿐이다(추상 메서드라 오버라이드하지 않으면 인스턴스화 시점에
``TypeError``\ 가 난다). 실제로 ``smart_chunker``/``hybrid_chunker`` 도
원래는 heading 합치기와 슬라이딩 윈도우 분할을 각자 중복 구현하고 있었는데,
``BaseChunker`` 로 옮기면서 두 모듈 다 이 두 메서드를 그대로 가져다 쓰도록
정리됐다.

2. 클래스를 선언하고 BaseChunker를 상속한다
---------------------------------------------

.. code-block:: python

   from typing import List

   from chunker.base_chunker import BaseChunker


   class Chunker(BaseChunker):
       """설명: 이 청커가 어떤 기준으로 아이템을 묶는지."""

클래스 이름은 항상 ``Chunker`` 로 고정한다 - :class:`preprocessor.DocumentProcessor`
가 ``chunker.<type>`` 모듈에서 이 이름을 ``importlib`` 로 찾기 때문이다.

3. __call__을 구현한다
------------------------

예를 들어 ``section_header`` 구분 없이 문서 전체 텍스트를 이어붙이고
``chunk_size`` 로만 기계적으로 자르는 청커를 만든다면:

.. code-block:: python

   def __call__(self, items: List[dict]) -> List[dict]:
       texts, pages = [], []
       for item in items:
           text = item.get("text")
           if not text:
               continue
           texts.append(text)
           pages.append(item["page"])
       if not texts:
           return []

       i_page, e_page = min(pages), max(pages)
       full_text = "\n".join(texts)
       if not self.chunk_size:
           return [{"text": full_text, "i_page": i_page, "e_page": e_page}]

       return [
           {"text": piece, "i_page": i_page, "e_page": e_page}
           for piece in self._split_text(full_text, self.chunk_size, self.chunk_overlap)
       ]

여기서 새로 짠 건 "아이템을 어떻게 모아서 자를지"뿐이고, 실제 분할
알고리즘(``_split_text``)과 heading 렌더링(``_render``, 이 예제처럼 heading을
아예 쓰지 않는 청커라면 호출할 필요도 없다)은 베이스 클래스 것을 그대로
쓴다.

.. note::
   문자 단위 오프셋으로 페이지를 정확히 추적하지 않고 문서 전체의
   최소/최대 페이지를 모든 조각에 그대로 붙이는 건 근사치다. ``smart_chunker``
   가 섹션 단위로 페이지 범위를 좁히는 것과 대비된다 - 어느 쪽이든 문자
   단위 정확한 페이지 추적은 하지 않는다.

4. 모듈로 저장한다
--------------------

``facade/chunker/`` 밑에 새 파일(예: ``facade/chunker/my_chunker.py``)로
저장한다.

5. DocumentProcessor에 연결한다
-----------------------------------

:doc:`custom_preprocessor` 와 같은 패턴으로, ``BaseProcessor`` 를 상속한
전용 ``DocumentProcessor`` 의 ``__init__`` 에서 ``self.chunker`` 에 새
청커를 채워 넣으면 된다. 앞서 2~3단계에서 만든 ``MyChunker`` 구현을
그대로 가져와서:

.. code-block:: python

   from typing import List

   from base_processor import BaseProcessor
   from chunker.base_chunker import BaseChunker
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


   class MyChunker(BaseChunker):
       """section_header 구분 없이 문서 전체 텍스트를 이어붙인 뒤 chunk_size로 자른다."""

       def __call__(self, items: List[dict]) -> List[dict]:
           texts, pages = [], []
           for item in items:
               text = item.get("text")
               if not text:
                   continue
               texts.append(text)
               pages.append(item["page"])
           if not texts:
               return []

           i_page, e_page = min(pages), max(pages)
           full_text = "\n".join(texts)
           if not self.chunk_size:
               return [{"text": full_text, "i_page": i_page, "e_page": e_page}]

           return [
               {"text": piece, "i_page": i_page, "e_page": e_page}
               for piece in self._split_text(full_text, self.chunk_size, self.chunk_overlap)
           ]


   class DocumentProcessor(BaseProcessor):
       max_page_split = 50

       def __init__(self):
           self.loader = {"pdf": PdfLoader(LAYOUT_CONFIG, OCR_CONFIG)}
           self.chunker = MyChunker(chunk_size=1000, chunk_overlap=100)
           self.metadata_builder = GenosMetadata()

       # __call__(file_path) -> List[dict] 은 base_processor.BaseProcessor 의
       # 구현을 그대로 쓴다 - 동기 (file_path) 진입점이면 오버라이드할 필요가 없다.

새로 만든 청커(``MyChunker``)만 바뀌었을 뿐, 로더/메타데이터는
:mod:`custom_preprocessor` 의 조합을 그대로 가져다 썼다. 실제로는
``MyChunker`` 를 ``facade/chunker/my_chunker.py`` 에 저장해두고
``from chunker.my_chunker import Chunker as MyChunker`` 로 임포트해도
되지만, 여기서는 클래스와 조립을 한 곳에서 보여주기 위해 같은 코드
블록에 뒀다.

6. 테스트한다
--------------

``tests/unit/test_chunkers.py`` 의 기존 테스트들처럼, 아이템 목록을 직접
만들어 ``Chunker`` 를 호출하고 결과를 검증하면 된다(로더/레이아웃/OCR 없이
순수 로직만 테스트하므로 ``pytest.mark.unit``):

.. code-block:: python

   from chunker.my_chunker import Chunker

   ITEMS = [
       {"text": "Intro", "category": "section_header", "page": 1},
       {"text": "para one on page 1", "category": "text", "page": 1},
       {"text": "para two on page 2", "category": "text", "page": 2},
   ]

   def test_splits_by_chunk_size_with_overlap():
       chunks = Chunker(chunk_size=15, chunk_overlap=3)(ITEMS)
       assert len(chunks) > 1

.. note::
   위 5단계 예제는 조합을 코드에 고정하는 :doc:`custom_preprocessor` 방식이라
   ``resource/config.yaml`` 을 읽지 않는다. ``config.yaml`` 로 계속 갈아
   끼우는 :class:`preprocessor.DocumentProcessor` 를 쓰고 싶다면, 이
   ``DocumentProcessor`` 서브클래스를 따로 만들 필요 없이 ``facade/chunker/my_chunker.py``
   의 ``Chunker`` 클래스 이름만 그대로 두고 ``chunker.type: my_chunker`` 만
   추가하면 된다 - 자세한 건 :doc:`facade_usage`.

더 보기
-------

- 파이프라인 각 단계가 정확히 뭘 하는지는 :doc:`architecture`
- 클래스/함수 시그니처는 :doc:`api`
- 조합 자체를 코드에 고정하는 법은 :doc:`custom_preprocessor`
- yaml로 조합을 바꾸는 법은 :doc:`facade_usage`
