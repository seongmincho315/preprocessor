docx
======

``ext.docx: test``
   ``config.yaml``\ 에 자리는 있지만 아직 미구현 상태다. ``loader.docx.test``\
   모듈도, 대체 경로인 ``converter.test``\ 모듈도 존재하지 않아서 지금
   ``docx``\ 파일을 넣으면 :func:`importlib.import_module`\ 이 실패한다
   (:func:`util.util.get_ext`\ 는 매직 바이트로 ``docx``\ 를 정상 인식하지만,
   그 뒤 로더를 못 찾는다).

:mod:`converter.libreoffice`\ 도 아직 ``NotImplementedError``\ 만 내는
placeholder라 대체 경로로 쓸 수 없다 - docx를 지원하려면 둘 중 하나가
먼저 구현돼야 한다.

docx가 필요하면
------------------

- 레거시 전처리기(``doc_parser``)에 docx 처리 로직이 있으니 참고
  (자세한 위치는 이 프로젝트의 ``CLAUDE.md`` 참고).
- 새 로더/컨버터를 직접 만드는 법은 :doc:`custom_loader`\ 를 참고 -
  ``loader/docx/<이름>.py``\ 에 ``Loader`` 클래스를 만들고
  ``ext.docx: <이름>``\ 으로 바꾸면 된다.

더 보기
-------

- 로더 설정 개요는 :doc:`facade_loader`
