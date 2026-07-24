import io

import pytest
from PIL import Image

from loader.jpeg.pillow import Loader

pytestmark = pytest.mark.unit


@pytest.fixture
def jpeg_file(tmp_path):
    path = tmp_path / "sample.jpeg"
    Image.new("RGB", (20, 10), color="blue").save(path, format="JPEG")
    return str(path)


def test_extract_pages_yields_one_page_with_empty_lines_and_png_bytes(jpeg_file):
    loader = Loader(layout_config={"type": "rule"}, ocr_config={"mode": "disable"})
    pages = list(loader._extract_pages(jpeg_file))

    assert len(pages) == 1
    lines, image, words = pages[0]
    assert lines == []
    assert image is not None
    assert words is None
    with Image.open(io.BytesIO(image)) as img:
        assert img.format == "PNG"
        assert img.size == (20, 10)
