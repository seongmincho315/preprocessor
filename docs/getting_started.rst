시작하기
========

설치
----

.. code-block:: bash

   uv sync --group dev

테스트
------

.. code-block:: bash

   uv run pytest              # unit + integration + regression (update_baseline 제외)
   uv run pytest -m unit      # 네트워크/파일 없이 순수 로직만
   uv run pytest -m integration  # 로컬 detr(:30881)/paddle(:30880) 파드 필요, 없으면 자동 skip
   uv run pytest -m regression   # tests/regression/baselines/*.json 과 비교
   uv run pytest -m update_baseline  # baseline (재)생성

샘플 문서 파싱해보기
--------------------

.. code-block:: python

   import sys
   sys.path.insert(0, "facade")

   from preprocessor import DocumentProcessor

   processor = DocumentProcessor()
   file_paths = processor.file_handling("sample/pdf/long(eng)/Information Theory.pdf")
   items = processor.load(file_paths)
   chunks = processor.chunking(items)
   vectors = processor.build_metadata(chunks, file_paths[0])

문서 빌드
---------

.. code-block:: bash

   uv run sphinx-build docs docs/_build/html
   # docs/_build/html/index.html 을 브라우저로 열기
