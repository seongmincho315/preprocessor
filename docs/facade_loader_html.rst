html
======

``ext.html`` (``bs4`` | ``libreoffice``)
   ``loader.html.<이름>`` 모듈에서 ``Loader`` 클래스를 찾고, 없으면
   ``converter.<이름>``\ 으로 대체한다.

:mod:`loader.html.bs4` (기본)
   BeautifulSoup4로 ``h1``-``h6``/``p``/``li``/``td``/``th``/``blockquote``/``pre``
   같은 block-level 태그를 줄 단위로 뽑는다. HTML은 페이지/이미지 개념이
   없는 텍스트 네이티브 포맷이라, ``layout``/``ocr`` 설정과 무관하게
   레이아웃은 항상 폰트 크기 휴리스틱(:class:`util.rule_layout.Layout`)으로,
   OCR은 항상 미사용으로 고정된다 - 헤딩 태그(``h1``-``h6``)에는 가상
   폰트 크기를 매겨 이 휴리스틱이 헤딩으로 인식하게 만든다.

``libreoffice``
   :mod:`converter.libreoffice`\ 로 대체하는 경로. 아직 실제 변환/로드
   로직이 없는 placeholder라 호출하면 ``NotImplementedError``\ 가 난다.

더 보기
-------

- 로더 설정 개요는 :doc:`facade_loader`
- 새 html 로더를 직접 만드는 법은 :doc:`custom_loader`
