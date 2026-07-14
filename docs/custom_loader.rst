나만의 로더 만들기
========================

로더는 :meth:`~base_processor.BaseProcessor.load` 가 확장자별로 호출하는
컴포넌트로, 파일 하나를 읽어 ``{text, category, bbox, page}`` 아이템
목록으로 바꾼다. ``pdf`` 확장자는 이미
:mod:`loader.pdf.pymupdf`/:mod:`loader.pdf.pypdf` 두 구현체가 있고,
``config.yaml`` 의 ``ext.<확장자>`` 값으로 선택된다.

1. BaseLoader가 이미 해주는 것
--------------------------------

:class:`loader.base_loader.BaseLoader` 가 로더 공통 흐름을 전부
구현해뒀다:

- ``__init__(layout_config, ocr_config)`` - 두 설정으로 :meth:`~loader.base_loader.BaseLoader.get_layout`/
  :meth:`~loader.base_loader.BaseLoader.get_ocr` 를 호출해 레이아웃/OCR
  전략 인스턴스를 만들어둔다.
- ``needs_image`` - 레이아웃 전략(``NEEDS_IMAGE``)이나 OCR 중 하나라도
  페이지 이미지를 필요로 하는지 알려주는 프로퍼티. 새 로더가 이미지 렌더링
  비용을 아낄지 판단할 때 쓴다.
- :meth:`~loader.base_loader.BaseLoader.__call__` - 페이지마다
  :meth:`_extract_pages` 를 호출하고, ``_needs_ocr`` 판단에 따라 OCR로
  줄을 대체한 뒤, 레이아웃 전략으로 카테고리를 매겨 최종 아이템을 조립한다.

서브클래스가 구현해야 하는 건 :meth:`~loader.base_loader.BaseLoader._extract_pages`
하나뿐이다(추상 메서드라 오버라이드하지 않으면 인스턴스화 시점에
``TypeError``\ 가 난다):

.. code-block:: python

   @abstractmethod
   def _extract_pages(
       self, file_path: str
   ) -> Iterable[Tuple[List[Tuple[str, Tuple[float, float, float, float], float]], Optional[bytes]]]:
       """페이지 단위로 ((text, bbox, font_size) 줄 목록, 페이지 이미지 PNG bytes|None)을 순서대로 반환한다."""

2. 기존 구현체로 계약 확인하기
--------------------------------

이미지 렌더링을 지원하지 않는(항상 ``None``) 가장 단순한 예로
:mod:`loader.pdf.pypdf` 를 보면 계약이 뭘 요구하는지 감이 온다:

.. literalinclude:: ../facade/loader/pdf/pypdf.py
   :language: python
   :linenos:

페이지 이미지가 필요한 레이아웃/OCR 전략과 같이 쓰려면
:mod:`loader.pdf.pymupdf` 처럼 ``self.needs_image`` 일 때만 이미지를
렌더링해서 두 번째 값으로 반환하면 된다.

3. 새 확장자 로더를 만든다
----------------------------

``loader/<확장자>/<이름>.py`` 에 ``Loader`` 클래스로 저장한다(클래스 이름은
항상 ``Loader`` 로 고정 - :class:`preprocessor.DocumentProcessor` 가
``loader.<확장자>.<이름>`` 모듈에서 이 이름을 ``importlib`` 로 찾는다):

.. code-block:: python

   from loader.base_loader import BaseLoader


   class Loader(BaseLoader):
       """설명: 이 포맷에서 텍스트/이미지를 어떻게 뽑는지."""

       def _extract_pages(self, file_path: str):
           for page in my_parse(file_path):
               lines = [(text, bbox, font_size) for text, bbox, font_size in page.lines]
               image = page.render_png() if self.needs_image else None
               yield lines, image

pdf로 변환 후 기존 pdf 로더에 넘기는 방식(예: 오피스 문서)이 더 간단하다면
로더 대신 :mod:`converter.libreoffice` 처럼 ``converter.<이름>`` 밑에
같은 ``Loader`` 인터페이스로 만들어도 된다 - ``config.yaml`` 이 ``loader.<확장자>.<이름>``
을 못 찾으면 ``converter.<이름>`` 으로 대체 시도한다.

4. config.yaml에 등록한다
---------------------------

.. code-block:: yaml

   ext:
     pdf: pymupdf
     my_ext: my_loader   # loader/my_ext/my_loader.py

5. 테스트한다
--------------

``tests/unit/test_base_loader.py`` 처럼, 실제 레이아웃/OCR 서버 없이
``layout_config``/``ocr_config`` 를 비우거나 ``rule``/``disable`` 로 둬서
순수 로직만 검증하면 된다(``pytest.mark.unit``).

더 보기
-------

- 레이아웃/OCR이 어떻게 조립되는지는 :doc:`architecture`
- 조합 자체를 코드에 고정하는 법은 :doc:`custom_preprocessor`
