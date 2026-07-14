# 문서 전처리기

## AI 플랫폼 솔루션과 연계되어야 함
- https://github.com/genonai/GenOS

## 기존 전처리기
- https://github.com/genonai/doc_parser
- docling 기반이라 커스텀하기 힘듬
- docling은 문서의 모든 페이지를 메모리에 올리기 때문에 큰 파일은 대처하기 힘듬
- 모듈화가 제대로 이루어지지 않아서 커스터마이즈 하기 쉽지 않음

## 파이프라인
- 파일 핸들링 -> 파일 로더 -> 청킹 -> Metatata
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

## 실제 사용
- 이미지 빌드(./build-script 참고)
- Genos에서 ./facade/preprocessor.py 를 로드: ./main.py참고
- 사용자가 config.yaml 로드, yaml 세팅에 따라 DocumentProcessor 초기화