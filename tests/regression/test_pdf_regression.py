"""PDF 처리 결과(GenOS 메타데이터)를 baseline과 비교해 의도치 않은 변경을 감지한다.
Baseline은 자동 생성되지 않는다 - `pytest -m update_baseline`으로만 (재)생성한다.
tests/regression/baselines/는 .gitignore 대상(로컬 전용 산출물)이라 처음 체크아웃한
환경에는 baseline이 없을 수 있으며, 그 경우 테스트는 fail이 아니라 skip된다.
sample/pdf/ 아래 모든 *.pdf 파일을 자동으로 찾아 테스트한다."""

import difflib
import json
from pathlib import Path

import pytest

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample" / "pdf"
BASELINE_DIR = Path(__file__).resolve().parent / "baselines"
PDF_FILES = sorted(SAMPLE_DIR.rglob("*.pdf"))


def _run_pipeline(document_processor, pdf_path: Path) -> dict:
    dp = document_processor
    file_paths = dp.file_handling(str(pdf_path))
    try:
        items = dp.load(file_paths)
        items = dp.pre_enrich(dp.preprocess(items))
        chunks = dp.chunking(items)
        chunks = dp.post_enrich(dp.postprocess(chunks))
        vectors = dp.build_metadata(chunks, str(pdf_path))
    finally:
        dp._cleanup_split_files(str(pdf_path), file_paths)

    return {
        "num_vectors": len(vectors),
        "total_characters": sum(v["n_chars"] for v in vectors),
        "vectors": vectors,
    }


def _baseline_path(pdf_path: Path) -> Path:
    return BASELINE_DIR / f"pdf_{pdf_path.stem}.json"


@pytest.mark.regression
@pytest.mark.parametrize("pdf_path", PDF_FILES, ids=lambda p: p.stem)
def test_pdf_regression(document_processor, pdf_path):
    baseline_path = _baseline_path(pdf_path)
    if not baseline_path.exists():
        pytest.skip(f"baseline 없음: {baseline_path}. `pytest -m update_baseline`로 로컬에 생성하세요.")

    current = _run_pipeline(document_processor, pdf_path)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    assert current["num_vectors"] == baseline["num_vectors"], (
        f"[{pdf_path.name}] 벡터 개수 불일치: {current['num_vectors']} != {baseline['num_vectors']}"
    )

    char_diff = abs(current["total_characters"] - baseline["total_characters"])
    char_ratio = char_diff / max(baseline["total_characters"], 1)
    assert char_ratio < 0.05, (
        f"[{pdf_path.name}] 전체 글자 수 변화가 너무 큼: {char_diff}자 ({char_ratio:.1%})"
    )

    for i, (cur, base) in enumerate(zip(current["vectors"], baseline["vectors"])):
        similarity = difflib.SequenceMatcher(None, cur["text"], base["text"]).ratio()
        assert similarity > 0.85, f"[{pdf_path.name}] 벡터 {i} 텍스트 유사도 낮음: {similarity:.1%}"


@pytest.mark.update_baseline
@pytest.mark.parametrize("pdf_path", PDF_FILES, ids=lambda p: p.stem)
def test_update_pdf_baseline(document_processor, pdf_path):
    """baseline (재)생성 유틸리티. 일반 pytest 실행에서는 제외되며 명시적으로만 실행한다."""
    result = _run_pipeline(document_processor, pdf_path)
    baseline_path = _baseline_path(pdf_path)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"baseline 저장됨: {baseline_path}")
