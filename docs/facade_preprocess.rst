전처리
========

``config.yaml``\ 에 해당하는 키가 없다. :meth:`~base_processor.BaseProcessor.preprocess`\
는 기본이 항등 함수(입력을 그대로 반환)라, 룰 기반 전처리(예: 띄어쓰기
보정)가 필요해지면 yaml 조합이 아니라 :doc:`custom_preprocessor`\ 처럼
서브클래스를 만들어 이 메서드를 오버라이드해야 한다.

더 보기
-------

- 처음부터 직접 만드는 법은 :doc:`custom_preprocess`
- yaml 조합 개요는 :doc:`facade_usage`
- 각 단계가 내부적으로 정확히 뭘 하는지는 :doc:`architecture`
