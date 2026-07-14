# <img src="docs/_static/logo.png" alt="logo" width="25"> doc-parser-preprocessor[해적판]


[[docs](https://github.com/seongmincho315/preprocessor/tree/main/docs)]

## 파이프라인

```
파일 핸들링 → 로더(레이아웃/OCR) → 전처리 → pre-Enrichment → 청킹 → 후처리 → post-Enrichment → 메타데이터
```

## 프로젝트 구조

```
preprocessor/
├── main.py                # GenOS 서빙 엔트리포인트 (FastAPI)
├── facade/
│   ├── preprocessor.py    # DocumentProcessor — config.yaml로 로더/청커/메타데이터 조립
│   ├── base_processor.py  # 8단계 파이프라인 정의
│   ├── loader/            # 확장자별 로더 (pdf/pymupdf, pdf/pypdf, html/bs4 ...)
│   ├── converter/         # 로더가 없는 확장자를 PDF로 변환 (libreoffice 등)
│   ├── chunker/           # smart / hierarchical / hybrid 청커
│   ├── metadata/          # GenOS 메타데이터 빌더
│   ├── util/              # 레이아웃(rule/detr) / OCR(paddle) 클라이언트
│   └── resource/          # config.yaml + 전략별 세부 설정
├── docs/                  # Sphinx 문서
├── sample/                # 샘플 문서
├── tests/                 # unit / integration / regression
└── build-script/          # 도커 이미지 빌드
```
