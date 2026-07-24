import io

import pytest
from PIL import Image

from loader.png.pillow import Loader

pytestmark = pytest.mark.unit


@pytest.fixture
def png_file(tmp_path):
    path = tmp_path / "sample.png"
    Image.new("RGB", (20, 10), color="red").save(path, format="PNG")
    return str(path)


def test_extract_pages_yields_one_page_with_empty_lines_and_png_bytes(png_file):
    loader = Loader(layout_config={"type": "rule"}, ocr_config={"mode": "disable"})
    pages = list(loader._extract_pages(png_file))

    assert len(pages) == 1
    lines, image, words = pages[0]
    assert lines == []
    assert image is not None
    assert words is None
    with Image.open(io.BytesIO(image)) as img:
        assert img.format == "PNG"
        assert img.size == (20, 10)


def test_empty_lines_trigger_ocr_need(png_file):
    loader = Loader(layout_config={"type": "rule"}, ocr_config={"mode": "auto"})
    lines, _, _ = next(loader._extract_pages(png_file))
    assert loader._needs_ocr(lines) is True
