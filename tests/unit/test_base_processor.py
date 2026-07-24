import pytest

from base_processor import BaseProcessor

pytestmark = pytest.mark.unit


class _DummyProcessor(BaseProcessor):
    """load/chunking을 스텁으로 대체해 실제 파일 없이 __call__ 오케스트레이션만 검증한다."""

    max_page_split = 50

    def __init__(self):
        self.metadata_builder = lambda chunks, file_path=None: [{"final": c["text"]} for c in chunks]

    def file_handling(self, file_path):
        return [file_path]

    def load(self, file_paths):
        return [{"text": f"loaded:{p}"} for p in file_paths]

    def chunking(self, items):
        return [{"text": item["text"]} for item in items]


def test_default_hooks_are_identity():
    dp = _DummyProcessor()
    items = [{"text": "a"}]
    chunks = [{"text": "b"}]

    assert dp.preprocess(items) is items
    assert dp.pre_enrich(items) is items
    assert dp.postprocess(chunks) is chunks
    assert dp.post_enrich(chunks) is chunks


def test_call_runs_full_pipeline_with_default_hooks():
    dp = _DummyProcessor()

    assert dp("sample.pdf") == [{"final": "loaded:sample.pdf"}]


def test_call_applies_overridden_hooks_in_order():
    class _WithHooks(_DummyProcessor):
        def preprocess(self, items):
            return [{"text": item["text"].upper()} for item in items]

        def postprocess(self, chunks):
            return [{"text": chunk["text"] + "!"} for chunk in chunks]

    dp = _WithHooks()

    assert dp("sample.pdf") == [{"final": "LOADED:SAMPLE.PDF!"}]


def test_return_level_loader_stops_before_chunking():
    dp = _DummyProcessor()
    assert dp("sample.pdf", return_level="loader") == [{"text": "loaded:sample.pdf"}]


def test_return_level_chunker_stops_before_postprocess():
    class _WithHooks(_DummyProcessor):
        def postprocess(self, chunks):
            raise AssertionError("postprocess가 호출되면 안 된다(return_level=chunker)")

    dp = _WithHooks()
    assert dp("sample.pdf", return_level="chunker") == [{"text": "loaded:sample.pdf"}]


def test_return_level_postprocess_stops_before_build_metadata():
    class _WithHooks(_DummyProcessor):
        def __init__(self):
            super().__init__()
            self.metadata_builder = lambda chunks, file_path=None: (_ for _ in ()).throw(
                AssertionError("build_metadata가 호출되면 안 된다(return_level=postprocess)")
            )

        def postprocess(self, chunks):
            return [{"text": chunk["text"] + "!"} for chunk in chunks]

    dp = _WithHooks()
    assert dp("sample.pdf", return_level="postprocess") == [{"text": "loaded:sample.pdf!"}]


def test_return_level_build_metadata_is_default_and_full_pipeline():
    dp = _DummyProcessor()
    assert dp("sample.pdf") == dp("sample.pdf", return_level="build_metadata")


def test_return_level_rejects_unknown_value():
    dp = _DummyProcessor()
    with pytest.raises(ValueError):
        dp("sample.pdf", return_level="nonsense")


def test_return_level_cleans_up_split_files_even_on_early_return():
    cleanup_calls = []

    class _WithHooks(_DummyProcessor):
        def _cleanup_split_files(self, file_path, file_paths):
            cleanup_calls.append((file_path, file_paths))

    dp = _WithHooks()
    dp("sample.pdf", return_level="loader")
    assert cleanup_calls == [("sample.pdf", ["sample.pdf"])]
