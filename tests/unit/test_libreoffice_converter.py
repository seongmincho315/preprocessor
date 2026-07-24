from pathlib import Path

import fitz
import pytest

from converter.libreoffice import Loader, soffice_available, soffice_binary

pytestmark = pytest.mark.unit


def test_soffice_binary_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("SOFFICE_BIN", raising=False)
    assert soffice_binary() == Path("/usr/bin/soffice")


def test_soffice_binary_blank_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SOFFICE_BIN", "   ")
    assert soffice_binary() == Path("/usr/bin/soffice")


def test_soffice_binary_respects_env_override(monkeypatch, tmp_path):
    fake = tmp_path / "soffice"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("SOFFICE_BIN", str(fake))

    assert soffice_binary() == fake
    assert soffice_available() is True


def test_missing_binary_raises_runtime_error(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFFICE_BIN", str(tmp_path / "no-such-soffice"))

    with pytest.raises(RuntimeError, match="soffice\\(LibreOffice\\) 바이너리를 찾을 수 없습니다"):
        Loader._convert_to_pdf(str(tmp_path / "sample.pptx"))


def test_conversion_failure_raises_runtime_error(monkeypatch, tmp_path):
    fake = tmp_path / "soffice"
    fake.write_text("#!/bin/sh\nexit 1\n")
    fake.chmod(0o755)
    monkeypatch.setenv("SOFFICE_BIN", str(fake))

    pptx_path = tmp_path / "broken.pptx"
    pptx_path.write_bytes(b"not a real pptx")

    with pytest.raises(RuntimeError, match="LibreOffice 변환 실패"):
        Loader._convert_to_pdf(str(pptx_path))


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "converted_by_soffice.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello soffice")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def fake_soffice(tmp_path, sample_pdf, monkeypatch):
    # 실제 soffice 대신, "--outdir <dir>" 인자를 스캔해 준비된 샘플 pdf를 그 디렉터리에
    # <원본이름>.pdf로 복사하는 스텁. 실제 커맨드라인은 rhwp보다 인자가 많아 위치 고정
    # 대신 --outdir 뒤 값을 찾는다.
    script = tmp_path / "soffice"
    script.write_text(
        "#!/bin/sh\n"
        'outdir=""\n'
        'prev=""\n'
        'for arg in "$@"; do\n'
        '  if [ "$prev" = "--outdir" ]; then outdir="$arg"; fi\n'
        '  prev="$arg"\n'
        "done\n"
        f'cp "{sample_pdf}" "$outdir/fake.pdf"\n'
    )
    script.chmod(0o755)
    monkeypatch.setenv("SOFFICE_BIN", str(script))
    return script


def test_extract_pages_converts_via_soffice_then_reads_with_pymupdf(fake_soffice, tmp_path):
    pptx_path = tmp_path / "sample.pptx"
    pptx_path.write_bytes(b"fake pptx content")

    loader = Loader()
    pages = list(loader._extract_pages(str(pptx_path)))

    assert len(pages) == 1
    lines, image, words = pages[0]
    assert image is None
    assert words is None
    assert lines[0][0] == "hello soffice"


def test_extract_pages_cleans_up_temp_dir(fake_soffice, tmp_path, monkeypatch):
    pptx_path = tmp_path / "sample.pptx"
    pptx_path.write_bytes(b"fake pptx content")

    created_dirs = []
    import tempfile as tempfile_module

    original_mkdtemp = tempfile_module.mkdtemp

    def _tracking_mkdtemp(*args, **kwargs):
        created = original_mkdtemp(*args, **kwargs)
        created_dirs.append(Path(created))
        return created

    monkeypatch.setattr(tempfile_module, "mkdtemp", _tracking_mkdtemp)

    list(Loader()._extract_pages(str(pptx_path)))

    assert len(created_dirs) == 1
    assert not created_dirs[0].exists()


@pytest.mark.skipif(not soffice_available(), reason="soffice(LibreOffice) 바이너리가 로컬에 없음")
def test_real_soffice_converts_sample_pptx(sample_dir):
    loader = Loader(layout_config={"type": "rule"}, ocr_config={"mode": "disable"})
    items = loader(str(sample_dir / "pptx" / "pptx_sample.pptx"))

    assert len(items) > 0
    assert any(item["text"].strip() for item in items)
