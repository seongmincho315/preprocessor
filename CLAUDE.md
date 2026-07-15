# 문서 전처리기

## AI 플랫폼 솔루션과 연계되어야 함
- https://github.com/genonai/GenOS

## 기존 전처리기
- https://github.com/genonai/doc_parser
- docling 기반이라 커스텀하기 힘듬
- docling은 문서의 모든 페이지를 메모리에 올리기 때문에 큰 파일은 대처하기 힘듬
- 모듈화가 제대로 이루어지지 않아서 커스터마이즈 하기 쉽지 않음

## 파이프라인
- 파일 핸들링 → 로더(레이아웃/OCR) → 전처리 → pre-Enrichment → 청킹 → 후처리 → post-Enrichment → 메타데이터
### 파일 핸들링:
큰 파일 핸들링: 50페이지 이상일 경우, pdf를 잘라서 진행
### 파일 로더
- 확장자 별로 지정된 로더로 파일 로드하고 파싱
- pdf 외의 파일의 경우 pdf로 컨버팅이 필요할 수도 있음.

### preprocessing: 룰 기반 전처리(전처리기의 전처리....)
- 띄어쓰기(TODO)

### pre-Enrichment: 외부 모델 기반 청크 내용 보강

### 청킹
- 파싱된 텍스트를 청킹

### postprocessing

### post-Enrichment(외부 모델을 이용하여 청크 내용 보강)
- image_description
- table_refiner
- etc..

### Metadata
- Genos 플랫폼에서 사용가능하게 메타데이터 할당
- 사용자가 메타데이터 추가하기 용이해야 함

## 확장자별 로더 or 컨버터
- pdf: 로더만 쓸건데 너가 찾아봐
- hwp, hwpx: rhwp
- 나머지: 기존 전처리기 찾아봐!

## TEST
- uv run
- ./facade/config.yaml 로 ./facade/preprocessor.py 초기화
- ./sample/*

### 로컬 실행
```bash
uv sync  # pyproject.toml에 default-groups 설정이 없어 dev 그룹(pytest 등)도 기본 포함됨
source .venv/bin/activate

# 네트워크/외부 파드 없이 도는 순수 로직 테스트
pytest -m unit

# 로컬 detr(:30881)/paddle(:30880) 파드 있어야 동작, 없으면 자동 skip
pytest -m integration
pytest -m regression
```

샘플 문서 하나를 직접 파싱해보려면 (`facade/resource/config.yaml`의 `layout.type`/`ocr.type`
기본값이 `detr`/`paddle`라 해당 파드가 떠 있어야 함. 파드 없이 로컬에서만 확인하고 싶으면
`layout.type: rule`, `ocr.mode: disable`로 바꿔서 실행):
```bash
python -c "
import sys; sys.path.insert(0, 'facade')
from preprocessor import DocumentProcessor

processor = DocumentProcessor()
file_paths = processor.file_handling('sample/pdf/long(eng)/Information Theory.pdf')
items = processor.load(file_paths)
items = processor.pre_enrich(processor.preprocess(items))
chunks = processor.chunking(items)
chunks = processor.post_enrich(processor.postprocess(chunks))
vectors = processor.build_metadata(chunks, file_paths[0])
print(len(vectors))
"
```
- `main.py`(FastAPI 서빙 엔트리)는 `logger`/`utils`/`config`/`common.*`/`util.minio_resource` 등
  GenOS 이미지 안에서만 주입되는 모듈에 의존하므로 로컬에서 바로 실행 불가 — 로컬 확인은
  항상 `facade/preprocessor.py`의 `DocumentProcessor`를 직접 호출하는 방식으로 한다.

## 실제 사용
- 이미지 빌드(./build-script 참고)
- Genos에서 ./facade/preprocessor.py 를 로드: ./main.py참고
- 사용자가 config.yaml 로드, yaml 세팅에 따라 DocumentProcessor 초기화