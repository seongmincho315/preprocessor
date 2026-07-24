# eval

## pdf sample.pdf

| layout.type | ocr.type | chunks | 유사도(태그 벗김) | 비고 |
|---|---|---|---|---|
| `dots_mocr` | `paddle` | 27 | **0.858** | Answer Key 전체 일치. footer 문장 누락(아래 참고), 매칭 표 텍스트 degeneration |
| `detr` + `table_structure: tableformer` | `paddle` | 38 | **0.935** | 매칭 표 옵션(a~g) 전부 정상 복구. footer 문장은 여전히 누락 |
