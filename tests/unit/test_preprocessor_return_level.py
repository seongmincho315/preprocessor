import asyncio

import pytest

from preprocessor import DocumentProcessor

pytestmark = pytest.mark.unit


def test_default_return_level_read_from_config():
    dp = DocumentProcessor()
    assert dp.default_return_level in dp.RETURN_LEVELS


def test_call_uses_config_default_return_level(monkeypatch):
    dp = DocumentProcessor()
    dp.default_return_level = "chunker"

    seen = {}

    def fake_super_call(self, file_path, return_level="build_metadata"):
        seen["return_level"] = return_level
        return "ok"

    monkeypatch.setattr(DocumentProcessor.__mro__[1], "__call__", fake_super_call)
    result = asyncio.run(dp(None, "sample.pdf"))

    assert seen["return_level"] == "chunker"
    assert result == "ok"


def test_call_param_overrides_config_default(monkeypatch):
    dp = DocumentProcessor()
    dp.default_return_level = "chunker"

    seen = {}

    def fake_super_call(self, file_path, return_level="build_metadata"):
        seen["return_level"] = return_level
        return "ok"

    monkeypatch.setattr(DocumentProcessor.__mro__[1], "__call__", fake_super_call)
    asyncio.run(dp(None, "sample.pdf", return_level="loader"))

    assert seen["return_level"] == "loader"
