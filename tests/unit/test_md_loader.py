import pytest

from loader.md.regex import Loader
from util.passthrough_layout import PassthroughLayout

pytestmark = pytest.mark.unit

SAMPLE_MD = """\
# Title

Intro paragraph.

## Section

- item one
- item two

1. first
2. second

| a | b |
|---|---|
| 1 | 2 |

```
code line
```
"""


@pytest.fixture
def md_file(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text(SAMPLE_MD, encoding="utf-8")
    return str(path)


def test_get_layout_and_ocr(md_file):
    loader = Loader(layout_config={"type": "detr"}, ocr_config={"type": "paddle"})
    assert isinstance(loader.layout, PassthroughLayout)
    assert loader.ocr is None


def test_classifies_structural_elements(md_file):
    loader = Loader()
    items = loader(md_file)

    categories = [(item["text"], item["category"]) for item in items]
    assert ("Title", "section_header") in categories
    assert ("Intro paragraph.", "text") in categories
    assert ("Section", "section_header") in categories
    assert ("item one", "list_item") in categories
    assert ("item two", "list_item") in categories
    assert ("first", "list_item") in categories
    assert ("second", "list_item") in categories
    assert all(item["page"] == 1 for item in items)


def test_pipe_table_becomes_single_table_item(md_file):
    items = Loader()(md_file)

    table_items = [item for item in items if item["category"] == "table"]
    assert len(table_items) == 1
    assert "<th>a</th>" in table_items[0]["text"]
    assert "<td>1</td>" in table_items[0]["text"]


def test_fenced_code_block_becomes_code_item(md_file):
    items = Loader()(md_file)

    code_items = [item for item in items if item["category"] == "code"]
    assert len(code_items) == 1
    assert "code line" in code_items[0]["text"]
