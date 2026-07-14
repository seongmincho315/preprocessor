시작하기
========

파이프라인
----------

문서 하나가 파일 핸들링 -> 로더(레이아웃/OCR) -> 청킹 -> 메타데이터, 4단계를
거쳐 GenOS 서빙용 벡터 dict 목록이 된다. 각 단계는 ``resource/config.yaml``\
로 구현체를 갈아 끼울 수 있다:

- **파일 핸들링** - PDF가 ``max_page_split``\ (기본 50) 페이지를 넘으면
  여러 파일로 분할한다.
- **로더** (``ext.<확장자>``\ ) - 페이지 텍스트를 추출하고, 레이아웃
  전략(``layout.type``\ : rule/detr)으로 카테고리를 매기고, 필요하면
  OCR(``ocr.type: paddle``\ )로 대체한다.
- **청킹** (``chunker.type``\ ) - ``smart_chunker``\ (기본)/
  ``hierarchical_chunker``\ /``hybrid_chunker`` 중 하나로 아이템을 청크로
  묶는다.
- **메타데이터** - 청크를 GenOS Weaviate 컬렉션 스키마로 변환한다.

yaml로 조합을 바꾸는 법은 :doc:`facade_usage`\ , 자세한 흐름은
:doc:`architecture`\ 를 참고.

서빙해야 할 이미지
------------------

파이프라인이 실제로 동작하려면 아래 이미지들이 함께 떠 있어야 한다:

- **preprocessor** (``doc-parser-preprocessor``\ ) - 이 저장소. ``/run`` 등
  GenOS API를 노출하는 메인 서비스.
- **detr** (``doc-parser-detr``\ ) - 레이아웃 분석 서비스. ``layout.type: detr``\
  선택 시 호출된다.
- **paddle** (``doc-parser-ocr``\ ) - OCR 서비스. ``ocr.type: paddle``\ 선택 시
  호출된다.
- **dots-mocr** - ``layout.type: dots_mocr``\ 용 레이아웃 분석 서비스.
  ``resource/dots_mocr.yaml``\ 에 접속 설정(``url``\ /``api_key``\ 등)만 있고
  로더 쪽 분기(:meth:`loader.base_loader.BaseLoader.get_layout`\ )는 아직
  TODO 상태 - 이 저장소에서 직접 빌드/배포하는 이미지가 아니라 외부 API로
  붙이는 구조로 보인다.

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
