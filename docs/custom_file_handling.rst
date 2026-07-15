나만의 파일 핸들링 만들기
============================

파일 핸들링은 :meth:`~base_processor.BaseProcessor.file_handling` 이
파이프라인 맨 앞에서 호출되는 단계로, PDF가 ``max_page_split`` 페이지를
넘으면 여러 파일로 잘라 경로 목록을 반환한다. 로더/청커와 달리 갈아
끼울 "구현체"가 따로 있는 게 아니라, ``BaseProcessor`` 가 이미 구현해둔
:func:`util.util.file_split` 를 그대로 물려 쓰는 클래스 속성
(``max_page_split``) 하나로 대부분 충분하다.

1. 기존 계약 확인하기
------------------------

.. literalinclude:: ../facade/base_processor.py
   :language: python
   :pyobject: BaseProcessor.file_handling

확인할 계약은 딱 하나다: ``file_handling(self, file_path: str) ->
List[str]``. 분할이 필요 없으면 원본 경로 하나만 담긴 리스트를, 필요하면
``<base_dir>/<파일이름>/1.pdf, 2.pdf ...`` 로 잘린 경로 목록을 반환한다.
PDF가 아닌 포맷은 페이지 개념이 없어 분할 없이 그대로 반환된다
(:func:`util.util.file_split`).

2. max_page_split만 바꾼다
------------------------------

대부분은 이 정도로 충분하다:

.. code-block:: python

   class DocumentProcessor(BaseProcessor):
       max_page_split = 20  # 기본 50보다 작게 잘라서 페이지당 처리 부담을 줄인다

3. 분할 로직 자체를 바꿔야 한다면
------------------------------------

예를 들어 PDF가 아닌 포맷도 크기 기준으로 잘라야 하거나, 분할 파일을
다른 위치에 저장해야 한다면 :meth:`~base_processor.BaseProcessor.file_handling`
자체를 오버라이드한다:

.. code-block:: python

   from pathlib import Path

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

       def file_handling(self, file_path: str):
           return my_custom_split(file_path, self.max_page_split)

오버라이드할 때 :meth:`~base_processor.BaseProcessor.__call__` 이
파이프라인이 끝나면 :meth:`~base_processor.BaseProcessor._cleanup_split_files`
로 ``file_handling`` 이 만든 분할 디렉터리를 정리한다는 점을 기억한다 -
반환값이 ``[file_path]`` 와 다르면(즉 실제로 분할했다면) 첫 경로의 부모
디렉터리를 통째로 지운다.

4. 테스트한다
--------------

``tests/unit/test_base_processor.py`` 처럼, 실제 PDF 없이 ``max_page_split``
값과 더미 ``file_handling`` 오버라이드만으로 파이프라인 오케스트레이션을
검증하면 된다(``pytest.mark.unit``).

더 보기
-------

- 파이프라인 각 단계가 정확히 뭘 하는지는 :doc:`architecture`
- 조합 자체를 코드에 고정하는 법은 :doc:`custom_preprocessor`
- yaml로 조합을 바꾸는 법은 :doc:`facade_usage`
