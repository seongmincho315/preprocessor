"""로컬에서 파싱 결과를 GenOS 청크에디터처럼(PDF + bbox 오버레이 + 청크 리스트) 눈으로 보기 위한 도구.

사용법:
    # 1) PDF를 파싱/청킹해서 청크(JSON)를 떨군다
    uv run python tools/visualize_chunks.py dump sample/pdf/long(eng)/Information\\ Theory.pdf

    # 2) 그 JSON을 자체완결 HTML 뷰어로 렌더링한다 (원본 PDF 경로는 JSON에 저장돼 있어 자동으로 찾음)
    uv run python tools/visualize_chunks.py view Information_Theory.chunks.json

둘 다 한 번에: `visualize_chunks.py dump <pdf>` 뒤에 바로 `view`를 실행해도 되고,
`dump`가 끝나면 다음에 실행할 `view` 명령을 안내해준다.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
FACADE_DIR = TOOLS_DIR.parent / "facade"
if str(FACADE_DIR) not in sys.path:
    sys.path.insert(0, str(FACADE_DIR))


def _dump(pdf_path: str, out_path: str | None) -> Path:
    """PDF를 파싱/청킹해서 ``{source_file, chunks}`` 형태의 JSON으로 저장한다.

    Args:
        pdf_path: 파싱할 PDF 경로.
        out_path: 저장할 JSON 경로. 생략하면 PDF와 같은 위치에 ``<이름>.chunks.json``.

    Returns:
        저장된 JSON 파일 경로.
    """
    from preprocessor import DocumentProcessor

    pdf_path = str(Path(pdf_path).resolve())
    processor = DocumentProcessor()

    file_paths = processor.file_handling(pdf_path)
    items = processor.load(file_paths)
    items = processor.pre_enrich(processor.preprocess(items))
    chunks = processor.chunking(items)

    out = Path(out_path) if out_path else Path(pdf_path).with_suffix("").with_suffix(".chunks.json")
    out.write_text(
        json.dumps({"source_file": pdf_path, "chunks": chunks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[dump] {len(chunks)}개 청크 -> {out}")
    print(f"[dump] 뷰어로 보려면: uv run python tools/visualize_chunks.py view {out}")
    return out


def _render_pages(pdf_path: str, page_numbers: set[int], dpi: int) -> dict[int, str]:
    """필요한 페이지만 PNG로 렌더링해서 base64 문자열로 반환한다.

    Args:
        pdf_path: 원본 PDF 경로.
        page_numbers: 렌더링할 1-indexed 페이지 번호 집합.
        dpi: 렌더링 해상도. bbox는 PDF point(72dpi) 좌표라, 오버레이할 때
            ``dpi / 72`` 배율로 스케일한다.

    Returns:
        ``{page_no: base64_png}``.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    try:
        images = {}
        for page_no in sorted(page_numbers):
            if not (1 <= page_no <= doc.page_count):
                continue
            page = doc[page_no - 1]
            png_bytes = page.get_pixmap(dpi=dpi).tobytes("png")
            images[page_no] = base64.b64encode(png_bytes).decode("ascii")
        return images
    finally:
        doc.close()


_CHUNK_COLORS = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080",
]


def _view(json_path: str, pdf_override: str | None, out_path: str | None, dpi: int) -> Path:
    """청크 JSON(+ 원본 PDF)으로 bbox 오버레이가 있는 자체완결 HTML 뷰어를 만든다.

    Args:
        json_path: :func:`_dump` 가 만든 JSON 경로.
        pdf_override: 원본 PDF 경로를 강제로 지정(생략하면 JSON의 ``source_file`` 사용).
        out_path: 저장할 HTML 경로. 생략하면 JSON과 같은 위치에 ``.html``.
        dpi: 페이지 렌더링 해상도.

    Returns:
        저장된 HTML 파일 경로.
    """
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    chunks = data["chunks"]
    pdf_path = pdf_override or data["source_file"]
    if not Path(pdf_path).exists():
        raise FileNotFoundError(
            f"원본 PDF를 찾을 수 없습니다: {pdf_path} (--pdf 로 위치를 직접 지정하세요)"
        )

    page_numbers = set()
    for chunk in chunks:
        for entry in chunk.get("bboxes", []):
            page_numbers.add(entry["page"])
        page_numbers.add(chunk["i_page"])
        page_numbers.add(chunk["e_page"])

    page_images = _render_pages(pdf_path, page_numbers, dpi)
    scale = dpi / 72  # bbox는 PDF point(72dpi) 좌표라 렌더링 dpi에 맞춰 스케일

    view_chunks = []
    for idx, chunk in enumerate(chunks):
        boxes = []
        for entry in chunk.get("bboxes", []):
            bbox = entry.get("bbox")
            if not bbox:
                continue
            boxes.append(
                {
                    "page": entry["page"],
                    "l": bbox["x0"] * scale,
                    "t": bbox["y0"] * scale,
                    "w": (bbox["x1"] - bbox["x0"]) * scale,
                    "h": (bbox["y1"] - bbox["y0"]) * scale,
                }
            )
        view_chunks.append(
            {
                "idx": idx,
                "text": chunk["text"],
                "i_page": chunk["i_page"],
                "e_page": chunk["e_page"],
                "boxes": boxes,
                "color": _CHUNK_COLORS[idx % len(_CHUNK_COLORS)],
            }
        )

    out = Path(out_path) if out_path else Path(json_path).with_suffix("").with_suffix(".html")
    out.write_text(
        _render_html(Path(pdf_path).name, page_images, view_chunks),
        encoding="utf-8",
    )
    print(f"[view] {len(view_chunks)}개 청크, {len(page_images)}개 페이지 -> {out}")
    return out


def _render_html(pdf_name: str, page_images: dict[int, str], view_chunks: list[dict]) -> str:
    pages_json = json.dumps(page_images, ensure_ascii=False)
    chunks_json = json.dumps(view_chunks, ensure_ascii=False)
    title = html.escape(pdf_name)

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>청크 뷰어 — {title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; display: flex; height: 100vh; font-family: system-ui, sans-serif;
    background: #1e1e1e; color: #ddd;
  }}
  #viewer {{ flex: 3; display: flex; flex-direction: column; min-width: 0; }}
  #toolbar {{
    display: flex; align-items: center; gap: 10px; padding: 8px 16px;
    border-bottom: 1px solid #444; flex: none;
  }}
  #toolbar button {{
    background: #333; color: #ddd; border: 1px solid #555; border-radius: 4px;
    padding: 4px 12px; cursor: pointer; font-size: 13px;
  }}
  #toolbar button:disabled {{ opacity: .4; cursor: default; }}
  #page-indicator {{ font-size: 13px; color: #aaa; }}
  #page-wrap {{ flex: 1; overflow: auto; display: flex; justify-content: center; padding: 16px; }}
  #page {{ position: relative; box-shadow: 0 0 8px rgba(0,0,0,.5); height: fit-content; }}
  #page img {{ display: block; max-width: 100%; }}
  .bbox {{
    position: absolute; border: 2px solid; border-radius: 2px; cursor: pointer;
    box-sizing: border-box; transition: border-width .1s, filter .1s;
  }}
  .bbox.selected {{ border-width: 3px; filter: brightness(1.5); z-index: 2; }}
  #chunks {{ flex: 2; overflow-y: auto; border-left: 1px solid #444; padding: 12px; min-width: 260px; }}
  #chunks h2 {{ font-size: 14px; color: #aaa; margin: 0 0 8px; }}
  .chunk {{
    border: 1px solid #333; border-left: 5px solid transparent; border-radius: 4px;
    padding: 8px 10px; margin-bottom: 8px; cursor: pointer; font-size: 13px; white-space: pre-wrap;
  }}
  .chunk:hover {{ background: #2a2a2a; }}
  .chunk.selected {{ background: #333; }}
  .chunk .meta {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
</style>
</head>
<body>
<div id="viewer">
  <div id="toolbar">
    <button id="prev-btn">◀ 이전</button>
    <span id="page-indicator"></span>
    <button id="next-btn">다음 ▶</button>
  </div>
  <div id="page-wrap"><div id="page"><img id="page-img"></div></div>
</div>
<div id="chunks"><h2>이 페이지의 청크 (<span id="chunk-count"></span>)</h2><div id="chunk-list"></div></div>
<script>
const PAGE_IMAGES = {pages_json};
const CHUNKS = {chunks_json};

const pageNos = Object.keys(PAGE_IMAGES).map(Number).sort((a, b) => a - b);
let pageIdx = 0;
let selectedChunkIdx = null;

const pageImgEl = document.getElementById('page-img');
const pageEl = document.getElementById('page');
const chunkListEl = document.getElementById('chunk-list');
const chunkCountEl = document.getElementById('chunk-count');
const indicatorEl = document.getElementById('page-indicator');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');

function chunksOnPage(pageNo) {{
  return CHUNKS.filter(c => c.boxes.some(b => b.page === pageNo));
}}

function selectChunk(idx) {{
  selectedChunkIdx = (selectedChunkIdx === idx) ? null : idx;
  render();
}}

function render() {{
  const pageNo = pageNos[pageIdx];
  pageImgEl.src = 'data:image/png;base64,' + PAGE_IMAGES[pageNo];
  indicatorEl.textContent = `${{pageIdx + 1}} / ${{pageNos.length}} (p.${{pageNo}})`;
  prevBtn.disabled = pageIdx === 0;
  nextBtn.disabled = pageIdx === pageNos.length - 1;

  // 이 페이지에 걸린 청크들의 bbox를 항상 그리되(카테고리 단위), 같은 청크는 같은 색으로 칠한다.
  // 선택된 청크만 굵게/밝게 강조.
  pageEl.querySelectorAll('.bbox').forEach(el => el.remove());
  const onPage = chunksOnPage(pageNo);
  for (const chunk of onPage) {{
    for (const box of chunk.boxes) {{
      if (box.page !== pageNo) continue;
      const el = document.createElement('div');
      el.className = 'bbox' + (chunk.idx === selectedChunkIdx ? ' selected' : '');
      el.style.left = box.l + 'px';
      el.style.top = box.t + 'px';
      el.style.width = box.w + 'px';
      el.style.height = box.h + 'px';
      el.style.borderColor = chunk.color;
      el.style.background = chunk.color + '33';
      el.title = '청크 #' + (chunk.idx + 1);
      el.addEventListener('click', () => selectChunk(chunk.idx));
      pageEl.appendChild(el);
    }}
  }}

  chunkCountEl.textContent = onPage.length;
  chunkListEl.innerHTML = '';
  for (const chunk of onPage) {{
    const item = document.createElement('div');
    item.className = 'chunk' + (chunk.idx === selectedChunkIdx ? ' selected' : '');
    item.style.borderLeftColor = chunk.color;
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = `#${{chunk.idx + 1}} · p.${{chunk.i_page}}-${{chunk.e_page}}`;
    const text = document.createElement('div');
    text.textContent = chunk.text;
    item.appendChild(meta);
    item.appendChild(text);
    item.addEventListener('click', () => selectChunk(chunk.idx));
    chunkListEl.appendChild(item);
    if (chunk.idx === selectedChunkIdx) item.scrollIntoView({{ block: 'nearest' }});
  }}
}}

prevBtn.addEventListener('click', () => {{ if (pageIdx > 0) {{ pageIdx--; selectedChunkIdx = null; render(); }} }});
nextBtn.addEventListener('click', () => {{ if (pageIdx < pageNos.length - 1) {{ pageIdx++; selectedChunkIdx = null; render(); }} }});
document.addEventListener('keydown', (e) => {{
  if (e.key === 'ArrowLeft') prevBtn.click();
  if (e.key === 'ArrowRight') nextBtn.click();
}});

render();
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    dump_p = sub.add_parser("dump", help="PDF를 파싱/청킹해서 JSON으로 저장")
    dump_p.add_argument("pdf_path")
    dump_p.add_argument("-o", "--out")

    view_p = sub.add_parser("view", help="청크 JSON을 bbox 오버레이 HTML 뷰어로 렌더링")
    view_p.add_argument("json_path")
    view_p.add_argument("--pdf", help="원본 PDF 경로 강제 지정 (기본: JSON의 source_file)")
    view_p.add_argument("-o", "--out")
    view_p.add_argument("--dpi", type=int, default=150)

    args = parser.parse_args()

    if args.command == "dump":
        _dump(args.pdf_path, args.out)
    elif args.command == "view":
        _view(args.json_path, args.pdf, args.out, args.dpi)


if __name__ == "__main__":
    main()
