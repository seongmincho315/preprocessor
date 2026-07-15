# Resource Configuration Reference

이 디렉터리는 전처리기가 실행 시점에 읽어 들이는 모든 설정 파일을 담습니다. 배포 환경에서는
`main.py`가 `PREPROCESSOR_ID`를 기준으로 MinIO의 `preprocessor` 버킷 리소스를 내려받아
`/app/resource`에 풀어놓고, 로컬 개발에서는 이 디렉터리(`facade/resource/`)가 같은 역할을 합니다.

설정은 두 계층으로 나뉩니다.

- **`config.yaml`** — 파이프라인 전체의 스위치보드. 각 단계(`layout`, `ocr`, `ext`, `chunker`)에서
  어떤 전략(`type`)을 쓸지 고르고, 전략별 세부 설정은 별도 파일로 위임합니다.
- **전략별 설정 파일** (`<전략 이름>.yaml` / `.py`) — `config.yaml`이 고른 전략 하나에 대한 세부 파라미터.

> **Status**: `rule`과 `detr`은 실제로 연결되어 있습니다. `layout.type`이 `rule`이 아니면
> `DocumentProcessor`가 `resource/<type>.yaml`을 읽어 `config.yaml`의 `layout` 설정과 병합하고,
> `BaseLoader.get_layout()`이 그 값에 따라 `Layout`(rule) 또는 `DetrLayout`(detr)을 반환합니다.
> `dots_mocr`은 아직 스키마 정의 단계이며 분기 로직이 없습니다.

## `config.yaml`

| Key | Type | Default | Description |
|---|---|---|---|
| `max_page_split` | int | `50` | PDF 페이지 수가 이 값을 넘으면 `file_split`이 여러 파일로 잘라 순차 처리한다. |
| `layout.type` | str | `rule` | 레이아웃(카테고리/bbox) 분석 전략. `rule`(폰트 크기 휴리스틱, 서빙 불필요) / `detr`(RT-DETR 기반 원격 서빙) / `dots_mocr`(VLM 프롬프트 기반 원격 서빙) 중 선택. |
| `ocr.type` | str | `paddle` | OCR 전략. 현재 `paddle` 하나만 정의되어 있다. |
| `ext.<확장자>` | str | — | 확장자별로 쓸 로더/컨버터 전략 모듈 이름 (`loader.<ext>.<이름>` 우선, 없으면 `converter.<이름>`으로 폴백). |
| `chunker.type` | str | `smart_chunker` | 청킹 전략. `smart_chunker`(섹션 헤더 기준) / `hierarchical_chunker`(아이템당 1청크) / `hybrid_chunker`(피어 병합 후 크기 분할). |
| `chunker.chunk_size` | int | `1000` | 청크 최대 문자 수. `0`이면 분할 없이 섹션/아이템을 통째로 반환. |
| `chunker.over_lap` | int | `100` | 청크를 문자 단위로 분할할 때의 겹침 길이. |

## `layout` 전략

### `rule` — 폰트 크기 휴리스틱 (`util/rule_layout.py`)

원격 서빙이 필요 없는 기본 전략. 별도 설정 파일이 필요 없다 (`rule.yaml`은 현재 비어 있다).

| Key | Type | Default | Description |
|---|---|---|---|
| `HEADER_FONT_SIZE_RATIO`(모듈 상수) | float | `1.2` | 페이지 내 최빈 폰트 크기 대비 이 배수 이상이면 `section_header`로 분류. |

### `detr` — RT-DETR 기반 원격 레이아웃 서버 (`resource/detr.yaml`)

[docling](https://github.com/docling-project/docling)이 쓰는 것과 같은 계열의 RT-DETR object
detection 모델(`docling-project/docling-layout-*`)을 직접 서빙한다고 가정할 때의 클라이언트 설정.

| Key | Type | Default | Description |
|---|---|---|---|
| `url` | str | `null` | 레이아웃 서버 엔드포인트 (`/detect`에 POST). 필수. |
| `api_key` | str | `null` | 인증이 필요하면 설정 (detr 서버에 아직 인증 미구현이라 현재는 사용 안 함). |
| `batch_size` | int | `64` | 아직 미사용 — 현재는 페이지당 1장씩 호출한다. |
| `image_dpi` | int | `150` | detr에 보낼 페이지 렌더링 해상도. 서버가 돌려주는 bbox는 이 dpi 기준 픽셀 좌표라, 줄 bbox(72dpi 포인트)와 스케일 변환해 매칭한다. |
| `timeout` | int | `60` | `/detect` 호출 타임아웃(초). |

`model_name`/`confidence_threshold`/`device`는 detr 서버(container) 쪽 배포 설정(env)이라 클라이언트인
이 config엔 없다 — 서버가 이미 필터링한 region만 내려준다.

### `dots_mocr` — VLM 프롬프트 기반 원격 레이아웃 서버 (`resource/dots_mocr.yaml`)

| Key | Type | Default | Description |
|---|---|---|---|
| `url` | str | `null` | 레이아웃 서버 엔드포인트. |
| `api_key` | str | `null` | 인증이 필요하면 설정. |
| `batch_size` | int | `64` | 한 번의 호출에 묶어 보낼 페이지 이미지 수. |
| `prompt` | str | `null` | VLM에 넘길 레이아웃 분석 프롬프트. |

## `ocr` 전략

### `paddle` (`resource/paddle.yaml`)

아직 스키마가 정의되지 않았다 (`paddle.yaml`이 비어 있음).

## `ext` 전략

### `bs4` — HTML 파서 (`loader/html/bs4.py`)

설정 파일이 아니라 로더 구현체(이 디렉터리가 아니라 `loader/html/bs4.py`에 있다).
HTML은 페이지/이미지 개념이 없는 텍스트 네이티브 포맷이라, `layout.type`/`ocr.type`
설정과 무관하게 레이아웃은 항상 `rule`(폰트 크기 휴리스틱), OCR은 항상 미사용으로
고정한다. 태그별로 가상 폰트 크기(h1~h6은 크게, 나머지는 본문 크기)를 매겨 `rule`
레이아웃이 `section_header`/`text`를 구분하게 한다.

### `rhwp` — HWP/HWPX → PDF 변환 컨버터 (`converter/rhwp.py`)

`ext.hwpx: rhwp`로 선택하면 `loader.hwpx.rhwp` 모듈이 없어 `converter.rhwp`로 대체된다.
설정 파일이 아니라 컨버터 구현체다. `PdfLoader`(`loader/pdf/pymupdf.py`)를 상속해서,
`rhwp export-pdf <입력> -o <출력.pdf>` CLI로 HWP/HWPX를 PDF로 변환한 뒤 부모의
pymupdf 추출 로직을 그대로 재사용한다 - 외부 서비스 호출 없이 컨테이너에 설치된
`rhwp` 바이너리(이미지 빌드 시 Rust로 빌드, `genonai/genos-rhwp`)만 있으면 동작한다.

| Key | Description |
|---|---|
| `RHWP_BIN`(환경변수) | `rhwp` 바이너리 경로 override. 기본값은 `/usr/local/bin/rhwp`(이미지 빌드 시 설치되는 경로). |

바이너리가 없거나 변환에 실패하면(`rc != 0` 또는 출력 파일 미생성) `RuntimeError`를 낸다.
