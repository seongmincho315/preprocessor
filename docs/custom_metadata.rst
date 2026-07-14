나만의 메타데이터 빌더 만들기
================================

메타데이터 빌더는 :meth:`~base_processor.BaseProcessor.build_metadata` 가
호출하는, 청커가 만든 ``{text, i_page, e_page}`` 청크 목록을 서빙용 벡터
dict 목록으로 바꾸는 마지막 단계다. 지금은 GenOS Weaviate 컬렉션 스키마용
:class:`metadata.genos.GenosMetadata` 하나뿐이고, 로더/청커와 달리 base
class 없이 ``__call__(chunks) -> List[dict]`` 시그니처만 맞추면 되는
덕타이핑 방식이다.

.. note::
   로더(``BaseLoader``)/청커(``BaseChunker``)에 base class가 있는 건 여러
   구현체가 중복 구현하던 로직(레이아웃/OCR 조립, heading 렌더링·슬라이딩
   윈도우 분할)을 한 곳으로 모으기 위해서였다. 메타데이터 빌더는 구현체가
   ``GenosMetadata`` 하나뿐이라 지금은 추상화할 공통 로직이 없다 - 두 번째
   구현체가 생기고 나서 공통 로직이 보이면 그때 base class를 만들어도
   늦지 않다.

1. 기존 구현체로 계약 확인하기
--------------------------------

.. literalinclude:: ../facade/metadata/genos.py
   :language: python
   :linenos:

여기서 확인할 계약은 딱 하나다: ``__call__(self, chunks: List[dict]) ->
List[dict]``. 입력은 청커가 만든 ``{text, i_page, e_page}`` dict 목록,
출력은 서빙 대상 벡터DB/플랫폼이 기대하는 필드로 채운 dict 목록이다.

2. 새 빌더를 만든다
---------------------

예를 들어 GenOS가 아닌 다른 플랫폼에 서빙할 때 필요한 필드만 최소로
담는다면:

``facade/metadata/my_metadata.py`` 에 저장한다:

.. code-block:: python

   from typing import List


   class MyMetadata:
       """청커가 만든 {text, i_page, e_page} 청크를 <내 플랫폼> 스키마로 변환한다."""

       def __call__(self, chunks: List[dict]) -> List[dict]:
           return [
               {
                   "chunk_id": i,
                   "content": chunk["text"],
                   "page_range": [chunk["i_page"], chunk["e_page"]],
               }
               for i, chunk in enumerate(chunks)
           ]

클래스 이름은 자유롭게 지어도 된다 - ``config.yaml`` 로 선택되는
로더/청커와 달리, 메타데이터 빌더는 3단계처럼 코드에서 직접 불러와
조립하기 때문이다.

3. DocumentProcessor에 연결한다
-----------------------------------

:class:`preprocessor.DocumentProcessor` 는 지금 메타데이터 빌더를
``config.yaml`` 이 아니라 ``__init__`` 안에 ``importlib.import_module("metadata.genos").GenosMetadata()``\
로 직접 고정해뒀다. 이 줄을 바꾸면 GenOS 배포 전체에 영향을 주므로, 대신
:doc:`custom_preprocessor` 와 같은 패턴으로 ``BaseProcessor`` 를 상속한
전용 ``DocumentProcessor`` 를 만들어 ``__init__`` 에서
``self.metadata_builder`` 에 새 빌더를 채워 넣는 편이 안전하다. 앞서
2단계에서 만든 ``MyMetadata`` 구현을 그대로 가져와서:

.. code-block:: python

   from typing import List

   from base_processor import BaseProcessor
   from chunker.smart_chunker import Chunker
   from loader.pdf.pymupdf import Loader as PdfLoader

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


   class MyMetadata:
       """청커가 만든 {text, i_page, e_page} 청크를 <내 플랫폼> 스키마로 변환한다."""

       def __call__(self, chunks: List[dict]) -> List[dict]:
           return [
               {
                   "chunk_id": i,
                   "content": chunk["text"],
                   "page_range": [chunk["i_page"], chunk["e_page"]],
               }
               for i, chunk in enumerate(chunks)
           ]


   class DocumentProcessor(BaseProcessor):
       max_page_split = 50

       def __init__(self):
           self.loader = {"pdf": PdfLoader(LAYOUT_CONFIG, OCR_CONFIG)}
           self.chunker = Chunker(chunk_size=1000, chunk_overlap=100)
           self.metadata_builder = MyMetadata()

       # __call__(file_path) -> List[dict] 은 base_processor.BaseProcessor 의
       # 구현을 그대로 쓴다 - 동기 (file_path) 진입점이면 오버라이드할 필요가 없다.

새로 만든 빌더(``MyMetadata``)만 바뀌었을 뿐, 로더/청커는
:mod:`custom_preprocessor` 의 조합을 그대로 가져다 썼다. 실제로는
``MyMetadata`` 를 ``facade/metadata/my_metadata.py`` 에 저장해두고
``from metadata.my_metadata import MyMetadata`` 로 임포트해도 되지만,
여기서는 클래스와 조립을 한 곳에서 보여주기 위해 같은 코드 블록에 뒀다.

4. 테스트한다
--------------

``tests/unit/test_genos_metadata.py`` 처럼, 청크 dict 목록을 직접 만들어
빌더를 호출하고 반환된 dict의 필드를 검증하면 된다(``pytest.mark.unit``).

더 보기
-------

- 파이프라인 각 단계가 정확히 뭘 하는지는 :doc:`architecture`
- 클래스/함수 시그니처는 :doc:`api`
- 조합 자체를 코드에 고정하는 법은 :doc:`custom_preprocessor`
