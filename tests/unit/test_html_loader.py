import pytest

from loader.html.bs4 import Loader
from util.rule_layout import Layout

pytestmark = pytest.mark.unit

SAMPLE_HTML = """
<html>
  <body>
    <h1>Title</h1>
    <p>First paragraph.</p>
    <h2>Section</h2>
    <p>Second paragraph.</p>
    <script>console.log("skip me");</script>
    <style>.skip { color: red; }</style>
  </body>
</html>
"""


@pytest.fixture
def html_file(tmp_path):
    path = tmp_path / "sample.html"
    path.write_text(SAMPLE_HTML, encoding="utf-8")
    return str(path)


def test_extracts_block_tags_in_order_and_skips_script_style(html_file):
    loader = Loader()
    pages = list(loader._extract_pages(html_file))

    assert len(pages) == 1
    lines, image, words = pages[0]
    assert image is None
    assert [text for text, _, _ in lines] == ["Title", "First paragraph.", "Section", "Second paragraph."]


def test_heading_tags_get_larger_font_size_than_body(html_file):
    loader = Loader()
    lines, _, _ = next(loader._extract_pages(html_file))

    by_text = {text: font_size for text, _, font_size in lines}
    assert by_text["Title"] > by_text["First paragraph."]
    assert by_text["Section"] > by_text["Second paragraph."]


def test_call_classifies_headings_as_section_header_regardless_of_layout_config(html_file):
    # layout.type: detr 이어도 html 로더는 rule 레이아웃으로 강제 고정된다.
    loader = Loader(layout_config={"type": "detr"}, ocr_config={"type": "paddle"})

    assert isinstance(loader.layout, Layout)
    assert loader.ocr is None

    items = loader(html_file)
    categories = {item["text"]: item["category"] for item in items}
    assert categories["Title"] == "section_header"
    assert categories["Section"] == "section_header"
    assert categories["First paragraph."] == "text"
    assert categories["Second paragraph."] == "text"
    assert all(item["page"] == 1 for item in items)
