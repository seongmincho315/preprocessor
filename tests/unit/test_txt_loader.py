import pytest

from loader.txt.plain import Loader
from util.passthrough_layout import PassthroughLayout

pytestmark = pytest.mark.unit


@pytest.fixture
def txt_file(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("First paragraph.\n\n\nSecond paragraph,\nstill second.\n\nThird.", encoding="utf-8")
    return str(path)


def test_get_layout_and_ocr(txt_file):
    loader = Loader(layout_config={"type": "detr"}, ocr_config={"type": "paddle"})
    assert isinstance(loader.layout, PassthroughLayout)
    assert loader.ocr is None


def test_splits_on_blank_lines_and_categorizes_as_text(txt_file):
    loader = Loader()
    items = loader(txt_file)

    assert [item["text"] for item in items] == [
        "First paragraph.",
        "Second paragraph,\nstill second.",
        "Third.",
    ]
    assert all(item["category"] == "text" for item in items)
    assert all(item["page"] == 1 for item in items)
