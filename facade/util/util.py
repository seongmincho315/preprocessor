"""파일 형식 판별, PDF 페이지 분할, 레이아웃 카테고리 목록, 글리프 손상 감지 등
여러 모듈에서 공통으로 쓰는 유틸리티 함수 모음."""

# docling_core.types.doc.labels.DocItemLabel 값 목록
# https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/labels.py
import re
import struct
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

from pypdf import PdfReader, PdfWriter

CATEGORIES = [
    "caption",
    "chart",
    "footnote",
    "formula",
    "list_item",
    "page_footer",
    "page_header",
    "picture",
    "section_header",
    "table",
    "text",
    "title",
    "document_index",
    "code",
    "checkbox_selected",
    "checkbox_unselected",
    "form",
    "key_value_region",
    "grading_scale",
    "handwritten_text",
    "empty_value",
    "paragraph",
    "reference",
    "field_region",
    "field_heading",
    "field_item",
    "field_key",
    "field_value",
    "field_hint",
    "marker",
]


def get_ext(file_path: str) -> str:
    """파일 이름의 확장자가 아니라, 파일 시그니처(매직 바이트)로 실제 형식을 판별해 반환한다.
    사용자가 pdf 파일의 확장자를 .txt 등으로 바꿔서 올리는 경우를 대비한 것.

    Args:
        file_path: 형식을 판별할 파일 경로.

    Returns:
        ``"pdf"``, ``"docx"``, ``"hwpx"``, ``"html"`` 중 하나.

    Raises:
        ValueError: 알 수 없는 zip 기반 형식이거나, 지원하지 않는 파일 형식일 때.
    """
    with open(file_path, "rb") as f:
        head = f.read(64)

    if head.startswith(b"%PDF"):
        return "pdf"

    if head.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(file_path) as zf:
            names = zf.namelist()
        if any(name.startswith("word/") for name in names):
            return "docx"
        if any(name.startswith("Contents/") or name == "mimetype" for name in names):
            return "hwpx"
        raise ValueError(f"알 수 없는 zip 기반 파일 형식입니다: {file_path}")

    text_head = head.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if text_head.startswith(b"<!doctype html") or text_head.startswith(b"<html"):
        return "html"

    raise ValueError(f"알 수 없는 파일 형식입니다: {file_path}")


def file_split(file_path: str, max_page_split: int, base_dir: Path) -> List[str]:
    """PDF가 max_page_split 페이지를 넘으면 여러 파일로 잘라 경로 목록을 반환한다.
    저장방식: <base_dir>/<파일이름>/1.pdf, 2.pdf ......
    페이지 개념이 없는 포맷(html 등)은 분할 없이 원본 경로를 그대로 반환한다.

    Args:
        file_path: 원본 파일 경로.
        max_page_split: 이 페이지 수를 넘으면 분할한다(pdf에만 적용).
        base_dir: 분할된 파일을 저장할 상위 디렉터리.

    Returns:
        처리할 파일 경로 목록. pdf가 아니거나 분할이 필요 없으면 ``[file_path]``.
    """
    ext = get_ext(file_path)
    if ext != "pdf":
        return [file_path]

    reader = PdfReader(file_path)
    num_pages = len(reader.pages)
    if num_pages <= max_page_split:
        return [file_path]

    stem = Path(file_path).stem
    out_dir = base_dir / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    split_paths = []
    for i, start in enumerate(range(0, num_pages, max_page_split), start=1):
        end = min(start + max_page_split, num_pages)
        writer = PdfWriter()
        for page in reader.pages[start:end]:
            writer.add_page(page)

        split_path = out_dir / f"{i}.pdf"
        with open(split_path, "wb") as f:
            writer.write(f)
        split_paths.append(str(split_path))

    return split_paths


# 폰트 인코딩이 깨져 유니코드로 매핑되지 않은 글리프는 대체 문자(U+FFFD)나
# 전용 영역(Private Use Area) 코드포인트로 추출된다. 텍스트 레이어가 있어도
# 이런 문자가 많으면 실제로는 읽을 수 없는 텍스트이므로 OCR로 대체해야 한다.
_BAD_CHAR_RANGES = (
    (0xFFFD, 0xFFFD),
    (0xE000, 0xF8FF),
    (0xF0000, 0xFFFFD),
    (0x100000, 0x10FFFD),
)


def _count_bad_chars(text: str) -> int:
    """text 안에서 :data:`_BAD_CHAR_RANGES` 에 속하는 문자 수를 센다."""
    return sum(
        1 for ch in text if any(lo <= ord(ch) <= hi for lo, hi in _BAD_CHAR_RANGES)
    )


# docling의 PagePreprocessingModel.rate_text_quality 그대로. 폰트 인코딩이 깨지면
# 유니코드 대체 문자/PUA 코드포인트뿐 아니라, 파서가 글리프를 이름으로 풀어쓰지
# 못해 "GLYPH<0041>"이나 "/G12/G34" 같은 원시 토큰을 그대로 텍스트에 남기는 경우도
# 있다. 이런 패턴은 유니코드 범위 검사로는 안 잡히므로 별도로 감지한다.
#
# docling 원본에서 이 넷 중 앞의 세 개(GLYPH/SLASH_G/SLASH_NUMBER_GARBAGE)만 즉시
# score=0.0 처리되는 hard fail이고, FRAG_RE(단어가 잘게 쪼개진 패턴)는 3번 이상
# 나와도 score에 0.1×횟수만큼 페널티를 주는 것뿐(3번이면 score=0.7)이라 그 자체로는
# "손상"으로 보지 않는다 - docling도 이 FRAG_RE 페널티를 OCR 여부 결정에 쓰지 않고
# 그냥 신뢰도 지표로만 남긴다(OCR은 페이지의 비트맵 커버리지로 따로 결정).
# 그래서 boolean 판정에는 FRAG_RE를 넣지 않는다.
_GLYPH_TAG_RE = re.compile(r"GLYPH<[0-9A-Fa-f]+>")
_SLASH_GLYPH_RE = re.compile(r"(?:/G\d+){2,}")
_SLASH_TOKEN_GARBAGE_RE = re.compile(r"(?:/\w+\s*){2,}")


def _has_garbled_glyph_pattern(text: str) -> bool:
    """폰트 인코딩이 깨졌을 때 나오는 원시 글리프 토큰 패턴(docling의 hard-fail 조건)이 있으면 True."""
    return bool(
        _GLYPH_TAG_RE.search(text) or _SLASH_GLYPH_RE.search(text) or _SLASH_TOKEN_GARBAGE_RE.match(text)
    )


def has_glyph_corruption(
    lines: List[Tuple[str, Tuple[float, float, float, float], float]],
    threshold: int = 3,
) -> bool:
    """페이지의 줄들에서 매핑되지 않은 글리프 문자 수가 threshold를 넘거나, 원시
    글리프 토큰 패턴(:func:`_has_garbled_glyph_pattern`)이 섞인 줄이 있으면 True.

    Args:
        lines: ``(text, bbox, font_size)`` 튜플 목록(로더가 뽑은 한 페이지 분량).
        threshold: 이 값을 초과하는 글리프 손상 문자 수가 나오면 손상으로 판단한다.

    Returns:
        글리프 손상으로 판단되면 ``True``.
    """
    if any(_has_garbled_glyph_pattern(text) for text, _, _ in lines):
        return True
    return sum(_count_bad_chars(text) for text, _, _ in lines) > threshold


def is_glyph_corrupted(text: str, threshold: int = 1) -> bool:
    """줄 하나의 텍스트에 매핑되지 않은 글리프 문자가 threshold개 이상이거나, 원시
    글리프 토큰 패턴이 섞여 있으면 True.

    :func:`has_glyph_corruption` 은 페이지 전체를 한 번에 판단해 OCR로 통째로 대체할지
    정하는 용도고, 이 함수는 줄 단위로 판단해 그 줄만 개별적으로 재추출할지 정하는 용도다
    (예: ``util.dots_mocr_auto_layout`` 이 글리프 깨진 줄만 골라 grounding OCR로 재추출).

    Args:
        text: 판단할 줄 하나의 텍스트.
        threshold: 이 값 이상의 글리프 손상 문자가 있으면 손상으로 판단한다.

    Returns:
        글리프 손상으로 판단되면 ``True``.
    """
    return _count_bad_chars(text) >= threshold or _has_garbled_glyph_pattern(text)


# docling의 PageAssembleModel.sanitize_text가 하는 타이포그래피 정규화. PDF 텍스트
# 레이어에 남아있는 구두점 변형(둥근 따옴표, 분수 슬래시, 불릿 기호 등)을 검색/청킹에서
# 다루기 편한 표준 문자로 통일한다.
_TYPOGRAPHY_NORMALIZE_MAP = {
    "⁄": "/",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "•": "·",
}


def normalize_typography(text: str) -> str:
    """docling이 통일하는 타이포그래피 문자(둥근 따옴표/분수 슬래시/불릿 등)를 표준 문자로 바꾼다.

    Args:
        text: 정규화할 텍스트.

    Returns:
        치환된 텍스트.
    """
    for old, new in _TYPOGRAPHY_NORMALIZE_MAP.items():
        text = text.replace(old, new)
    return text


def png_size(data: bytes) -> Optional[Tuple[int, int]]:
    """PNG bytes의 IHDR 청크에서 ``(width, height)`` 픽셀 크기를 읽는다.

    Pillow 등 이미지 라이브러리 없이, PNG 포맷 스펙(시그니처 8바이트 + IHDR 청크)만으로
    직접 파싱한다. PNG가 아니거나 형식이 예상과 다르면 ``None``.
    """
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height
