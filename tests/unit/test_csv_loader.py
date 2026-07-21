import pytest

from loader.csv.stdlib import Loader
from util.passthrough_layout import PassthroughLayout

pytestmark = pytest.mark.unit


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_bytes("﻿name,age\n철수,10\n영희,12\n".encode("utf-8"))
    return str(path)


def test_get_layout_and_ocr(csv_file):
    loader = Loader(layout_config={"type": "detr"}, ocr_config={"type": "paddle"})
    assert isinstance(loader.layout, PassthroughLayout)
    assert loader.ocr is None


def test_strips_bom_and_uses_first_row_as_header(csv_file):
    loader = Loader()
    items = loader(csv_file)

    assert len(items) == 1
    assert items[0]["category"] == "table"
    assert items[0]["page"] == 1
    assert "<th>name</th>" in items[0]["text"]
    assert "﻿" not in items[0]["text"]
    assert "<td>철수</td>" in items[0]["text"]


def test_blank_row_splits_into_multiple_table_items(tmp_path):
    path = tmp_path / "multi.csv"
    path.write_text("a,b\n1,2\n\nc,d\n3,4\n", encoding="utf-8")

    items = Loader()(str(path))

    assert len(items) == 2
    assert "<th>a</th>" in items[0]["text"]
    assert "<th>c</th>" in items[1]["text"]
