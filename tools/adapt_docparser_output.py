"""doc_parser(intelligent_processor)의 GenOSVectorMeta 목록을
tools/visualize_chunks.py 의 `view` 커맨드가 읽는 {source_file, chunks} JSON으로 변환한다.

doc_parser의 chunk_bboxes는 페이지 크기로 정규화된(0~1) bbox + coord_origin
("BOTTOMLEFT"|"TOPLEFT")을 담고 있어, 우리 뷰어가 기대하는 PDF-point(72dpi,
top-left origin) 절대좌표로 다시 변환해야 한다.

사용법:
    python adapt_docparser_output.py <doc_parser_vectors.json> <source_pdf> -o <out.json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _page_sizes_pt(pdf_path: str) -> dict[int, tuple[float, float]]:
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    try:
        return {i + 1: (page.rect.width, page.rect.height) for i, page in enumerate(doc)}
    finally:
        doc.close()


def _to_topleft_pt(bbox: dict, page_w_pt: float, page_h_pt: float) -> dict:
    """정규화된 bbox(+coord_origin)를 PDF-point, top-left origin 절대좌표로 변환."""
    l, t, r, b = bbox["l"], bbox["t"], bbox["r"], bbox["b"]
    origin = bbox.get("coord_origin", "BOTTOMLEFT")

    x0 = l * page_w_pt
    x1 = r * page_w_pt

    if origin == "BOTTOMLEFT":
        # PDF native: t(위쪽 경계)가 b보다 값이 큼(바닥 원점 기준). top-left로 뒤집는다.
        y0 = (1 - t) * page_h_pt
        y1 = (1 - b) * page_h_pt
    else:  # TOPLEFT
        y0 = t * page_h_pt
        y1 = b * page_h_pt

    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


def adapt(vectors_path: str, pdf_path: str, out_path: str) -> Path:
    vectors = json.loads(Path(vectors_path).read_text(encoding="utf-8"))
    page_sizes = _page_sizes_pt(pdf_path)

    chunks = []
    for v in vectors:
        bboxes_raw = v.get("chunk_bboxes")
        if isinstance(bboxes_raw, str):
            bboxes_raw = json.loads(bboxes_raw) if bboxes_raw else []
        bboxes_raw = bboxes_raw or []

        bboxes = []
        pages = set()
        for entry in bboxes_raw:
            page_no = entry["page"]
            pages.add(page_no)
            page_w, page_h = page_sizes.get(page_no, (612.0, 792.0))
            bboxes.append(
                {
                    "page": page_no,
                    "bbox": _to_topleft_pt(entry["bbox"], page_w, page_h),
                    "category": entry.get("type"),
                }
            )

        i_page = v.get("i_page") or (min(pages) if pages else 1)
        e_page = v.get("e_page") or (max(pages) if pages else i_page)

        chunks.append(
            {
                "text": v.get("text", ""),
                "i_page": i_page,
                "e_page": e_page,
                "bboxes": bboxes,
            }
        )

    out = Path(out_path)
    out.write_text(
        json.dumps({"source_file": str(Path(pdf_path).resolve()), "chunks": chunks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[adapt] {len(chunks)}개 청크 -> {out}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vectors_json", help="doc_parser DocumentProcessor()가 반환한 vectors를 json.dump한 파일")
    parser.add_argument("pdf_path", help="원본 PDF 경로 (페이지 크기 조회용)")
    parser.add_argument("-o", "--out", required=True)
    args = parser.parse_args()
    adapt(args.vectors_json, args.pdf_path, args.out)


if __name__ == "__main__":
    main()
