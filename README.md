# <img src="docs/_static/logo.png" alt="logo" width="25"> doc-parser-preprocessor[해적판]


[[docs](https://seongmincho315.github.io/preprocessor/)]

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

## 로컬 실행

```bash
uv sync  # pyproject.toml에 default-groups 설정이 없어 dev 그룹(pytest 등)도 기본 포함됨
source .venv/bin/activate

pytest -m unit         # 네트워크/외부 파드 없이 도는 순수 로직 테스트
pytest -m integration  # 로컬 detr(:30881)/paddle(:30880) 파드 필요, 없으면 자동 skip
pytest -m regression   # tests/regression/baselines/*.json 과 비교
```

샘플 문서 하나를 직접 파싱해보려면:

```python
import sys
sys.path.insert(0, "facade")

from preprocessor import DocumentProcessor

processor = DocumentProcessor()
file_paths = processor.file_handling("sample/pdf/long(eng)/Information Theory.pdf")
items = processor.load(file_paths)
items = processor.pre_enrich(processor.preprocess(items))  # 기본은 항등 함수(스텁)
chunks = processor.chunking(items)
chunks = processor.post_enrich(processor.postprocess(chunks))  # 기본은 항등 함수(스텁)
vectors = processor.build_metadata(chunks, file_paths[0])
```

`facade/resource/config.yaml`의 기본값(`layout.type: detr`, `ocr.type: paddle`)은 별도
파드가 떠 있어야 동작한다. 파드 없이 로컬에서만 확인하려면 `layout.type: rule`,
`ocr.mode: disable`로 바꿔서 실행하면 된다.

`main.py`는 GenOS 서빙용 FastAPI 엔트리포인트로, `logger`/`utils`/`common.*` 등 GenOS 이미지
안에서만 주입되는 모듈에 의존하므로 로컬에서 직접 실행할 수 없다 — 로컬 확인은 항상 위처럼
`DocumentProcessor`를 직접 호출하는 방식으로 한다.


## 시각화: ./tools/visualize_chunks.py

## TODO
- 리턴 레벨: 각 파이프라인 별로 리턴할 수 있게
- yaml 제너레이터: 사용자가 원하는 config yaml을 화면에서 만들면 더 좋을거같다
- 개행/띄어쓰기: 나는 이거 형태소 분석기 토크나이져 타도 안고쳐질거같은데;;
- 기존 전처리기는 성능 측정 어떻게 하는거지
- docling은 성능 측정 어떻게 하는거지
- 배포해보기