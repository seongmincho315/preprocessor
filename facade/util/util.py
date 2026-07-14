# docling_core.types.doc.labels.DocItemLabel 값 목록
# https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/labels.py
import zipfile
from pathlib import Path
from typing import List, Tuple

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
    사용자가 pdf 파일의 확장자를 .txt 등으로 바꿔서 올리는 경우를 대비한 것."""
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
    저장방식: <base_dir>/<파일이름>/1.pdf, 2.pdf ......"""
    ext = get_ext(file_path)
    if ext != "pdf":
        raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}")

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
    return sum(
        1 for ch in text if any(lo <= ord(ch) <= hi for lo, hi in _BAD_CHAR_RANGES)
    )


def has_glyph_corruption(
    lines: List[Tuple[str, Tuple[float, float, float, float], float]],
    threshold: int = 3,
) -> bool:
    """페이지의 줄들에서 매핑되지 않은 글리프 문자 수가 threshold를 넘으면 True."""
    return sum(_count_bad_chars(text) for text, _, _ in lines) > threshold
