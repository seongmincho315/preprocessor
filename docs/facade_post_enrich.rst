post-Enrichment
==================

``config.yaml``\ 에 해당하는 키가 없다. :meth:`~base_processor.BaseProcessor.post_enrich`\
도 기본이 항등 함수다. image_description/table_refiner 등 외부 모델 기반
청크 보강이 필요하면 :doc:`custom_preprocessor`\ 처럼 서브클래스에서
오버라이드한다.

더 보기
-------

- 처음부터 직접 만드는 법은 :doc:`custom_post_enrich`
- yaml 조합 개요는 :doc:`facade_usage`
- 각 단계가 내부적으로 정확히 뭘 하는지는 :doc:`architecture`
