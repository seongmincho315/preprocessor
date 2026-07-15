hwpx
======

``ext.hwpx`` (``rhwp`` | ``libreoffice``)
   ``loader.hwpx.<이름>`` 모듈을 먼저 찾는데, 지금은 이 모듈이 없어 항상
   ``converter.<이름>``\ 으로 대체된다.

:mod:`converter.rhwp` (기본)
   ``rhwp export-pdf <입력> -o <출력.pdf>`` CLI(이미지 빌드 시 Rust로
   빌드되는 ``genonai/genos-rhwp`` 바이너리)로 HWP/HWPX를 PDF로 변환한
   뒤, :mod:`loader.pdf.pymupdf`\ 로 그 PDF를 읽는다. 외부 서비스/네트워크
   의존 없이 컨테이너 안에서 subprocess로만 동작한다.

   ``RHWP_BIN``\ (환경변수)
      ``rhwp`` 바이너리 경로 override. 기본값은
      ``/usr/local/bin/rhwp``\ (이미지 빌드 시 설치되는 경로) - 로컬에서
      다른 위치에 빌드했다면 이 환경변수로 가리키면 된다.

``libreoffice``
   :mod:`converter.libreoffice`\ 로 대체하는 경로. 아직 실제 변환/로드
   로직이 없는 placeholder라 호출하면 ``NotImplementedError``\ 가 난다.

더 보기
-------

- 로더 설정 개요는 :doc:`facade_loader`
- rhwp 로컬 빌드/설치 방법은 ``facade/resource/README.md``\ 의 ``rhwp`` 섹션
- 새 로더를 직접 만드는 법은 :doc:`custom_loader`
