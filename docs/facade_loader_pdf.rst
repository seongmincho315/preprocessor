pdf
=====

``ext.pdf`` (``pymupdf`` | ``pypdf``)
   ``loader.pdf.<이름>`` 모듈에서 ``Loader`` 클래스를 찾아 쓴다.

:mod:`loader.pdf.pymupdf` (기본)
   PyMuPDF(``fitz``)로 텍스트 레이어와 페이지 이미지를 함께 뽑는다.
   ``layout.type: detr``\ 처럼 이미지가 필요한 레이아웃/OCR 전략과 같이
   쓸 수 있다.

:mod:`loader.pdf.pypdf`
   pypdf의 텍스트 추출 visitor로 줄 단위 텍스트만 뽑고, 페이지 이미지는
   항상 ``None``\ 이다. ``layout.type: rule``\ 처럼 이미지가 필요 없는
   전략에서만 쓸 수 있다.

레이아웃/OCR 자체를 어떻게 조립하는지는 :doc:`facade_loader`\ 를 참고.

더 보기
-------

- 로더 설정 개요는 :doc:`facade_loader`
- 새 pdf 로더를 직접 만드는 법은 :doc:`custom_loader`
