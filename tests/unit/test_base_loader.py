import pytest

from loader.base_loader import OCR_MODES, BaseLoader

pytestmark = pytest.mark.unit

CLEAN_LINES = [("hello world", (0, 0, 1, 1), 10.0)]
CORRUPTED_LINES = [("���� broken", (0, 0, 1, 1), 10.0)]


class _DummyLoader(BaseLoader):
    """_extract_pages는 실제 파일을 읽지 않는 스텁. 생성자(get_layout/get_ocr)는
    네트워크를 타지 않으므로 그대로 실행해 ocr_mode 분기를 있는 그대로 검증한다."""

    def _extract_pages(self, file_path):
        return iter([])


def _make_loader(mode: str) -> _DummyLoader:
    return _DummyLoader(layout_config={}, ocr_config={"type": "paddle", "mode": mode, "url": "http://localhost:1"})


@pytest.mark.parametrize(
    "mode, lines, expected",
    [
        ("disable", [], False),
        ("disable", CORRUPTED_LINES, False),
        ("force", CLEAN_LINES, True),
        ("auto", [], True),
        ("auto", CLEAN_LINES, False),
        ("auto", CORRUPTED_LINES, True),
    ],
)
def test_needs_ocr_respects_mode(mode, lines, expected):
    loader = _make_loader(mode)
    assert loader._needs_ocr(lines) is expected


def test_invalid_ocr_mode_falls_back_to_auto():
    loader = _make_loader("bogus")
    assert loader.ocr_mode == "auto"
    assert "bogus" not in OCR_MODES


def test_disable_mode_skips_ocr_client_construction():
    loader = _make_loader("disable")
    assert loader.ocr is None


class _ItemsLayout:
    """PRODUCES_ITEMS=True 전략 스텁: lines는 무시하고 자체 아이템을 직접 반환한다."""

    NEEDS_IMAGE = True
    PRODUCES_ITEMS = True

    def __call__(self, lines, image=None):
        return [{"text": "override", "category": "title", "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}}]


class _ItemsLoader(BaseLoader):
    def __init__(self):
        super().__init__(layout_config={}, ocr_config={})

    def get_layout(self):
        return _ItemsLayout()

    def get_ocr(self):
        return None

    def _extract_pages(self, file_path):
        yield ([("ignored", (0, 0, 1, 1), 10.0)], b"fake-image-bytes", None)


def test_produces_items_layout_bypasses_line_zip_and_stamps_page():
    loader = _ItemsLoader()
    items = loader("irrelevant.path")
    assert items == [{"text": "override", "category": "title", "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}, "page": 1}]
