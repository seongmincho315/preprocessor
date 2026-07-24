# json, 뷰어 결과 저장소

`.html`을 브라우저로 열면 bbox 오버레이 + 청크 리스트 뷰어. `.chunks.json`은 그 원본 데이터.

## Information Theory.pdf (92p, 영어 논문)

| 파일 | 파이프라인 | 실행 위치 |
|---|---|---|
| `Information Theory.docparser.html` | legacy `doc_parser`(docling) intelligent_processor | komipo (실제 원격 실행) |
| `Information Theory.dots_mocr.html` | my_preprocessor, `layout.type: dots_mocr` | 로컬 |
| `Information Theory.detr.html` | my_preprocessor, `layout.type: detr` + tableformer | 로컬 |

## pdf_sample.pdf (11p, 영어 A2 시험지)

| 파일 | 파이프라인 |
|---|---|
| `pdf_sample.dots_mocr.html` | my_preprocessor, `layout.type: dots_mocr` |
| `pdf_sample.detr.html` | my_preprocessor, `layout.type: detr` + tableformer |

## 알려진 이슈

- my_preprocessor는 92페이지짜리 PDF에서 `max_page_split`(50) 분할 후 **두 번째 분할 파일(51~92p)의
  아이템을 하나도 못 뽑는 버그**가 있음 (`Information Theory.dots_mocr/.detr` 둘 다 50페이지까지만
  커버됨). `load()`가 분할된 두 번째 파일을 처리하는 경로 확인 필요 — 아직 미수정.
