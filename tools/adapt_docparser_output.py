"""doc_parser(intelligent_processor)가 반환한 GenOSVectorMeta 목록을
tools/visualize_chunks.py 의 `view` 커맨드가 읽는 ``{source_file, vectors}`` JSON으로 감싼다.

doc_parser의 ``chunk_bboxes`` 는 페이지 크기로 정규화된(0~1) bbox + coord_origin
("BOTTOMLEFT"|"TOPLEFT")을 그대로 담고 있고, 우리 ``metadata/genos.py`` 가 만드는
``chunk_bboxes`` 도 같은 스키마(coord_origin만 항상 "TOPLEFT")라 좌표 변환이 필요 없다 -
``view`` 가 두 coord_origin을 모두 처리한다.

사용법:
    python adapt_docparser_output.py <doc_parser_vectors.json> <source_pdf> -o <out.json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def adapt(vectors_path: str, pdf_path: str, out_path: str) -> Path:
    vectors = json.loads(Path(vectors_path).read_text(encoding="utf-8"))
    out = Path(out_path)
    out.write_text(
        json.dumps({"source_file": str(Path(pdf_path).resolve()), "vectors": vectors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[adapt] {len(vectors)}개 벡터 -> {out}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vectors_json", help="doc_parser DocumentProcessor()가 반환한 vectors를 json.dump한 파일")
    parser.add_argument("pdf_path", help="원본 PDF 경로")
    parser.add_argument("-o", "--out", required=True)
    args = parser.parse_args()
    adapt(args.vectors_json, args.pdf_path, args.out)


if __name__ == "__main__":
    main()
